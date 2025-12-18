# =============================================================================
# ThinkTwice - Engine
# Speculative Execution with Takeover Mechanism
# =============================================================================
"""
ARCHITECTURE: Speculative Execution & Takeover

The system operates like a modern processor with speculative execution:
1. The Generator proceeds assuming everything is correct.
2. The Auditor verifies in parallel (background).
3. If failure detected: TAKEOVER - cancellation, history correction, continuation.

Key difference from traditional "retry" systems:
- We do NOT ask the model to correct itself.
- We insert the fix as if the model had written it.
- The model continues without knowing an error occurred.

ADAPTIVE RECOVERY:
- Dynamic temperature ("Jitter") based on consecutive retries.
- More retries -> higher temperature to explore alternative solutions.
- Controlled abort if retry limit is exceeded.

BYOK (Bring Your Own Key):
- The engine does NOT store a global API Key.
- Each instance requires an `api_key` parameter.
- Allows user-specific OpenRouter/OpenAI keys.
"""

import asyncio
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from openai import AsyncOpenAI

import config  # User Configuration
from thinktwice_config import (
    AuditorPrompt,
    Colors,
    InterventionMessage,
    GeneratorPrompt
)


# =============================================================================
# AUDIT RESULT TRACKING
# =============================================================================
class AuditStatus(Enum):
    """Possible outcomes of an idea audit."""
    PENDING = "PENDING"
    OK = "OK"
    FAIL = "FAIL"


@dataclass
class AuditResult:
    """
    Stores the outcome of an individual idea audit.
    
    Attributes:
        status: The audit verdict (PENDING, OK, or FAIL).
        fix: The corrected reasoning text if status is FAIL.
        start_index: Position in generated_text where the idea began.
    """
    status: AuditStatus
    fix: Optional[str] = None
    start_index: int = 0


# =============================================================================
# EXCEPTION: Controlled Abort
# =============================================================================
class AdaptiveRecoveryAbort(Exception):
    """
    Thrown when the system exceeds the retry limit.
    Indicates the logical path is unstable and cannot be resolved 
    with adaptive recovery.
    """
    def __init__(self, retry_count: int, max_retries: int):
        self.retry_count = retry_count
        self.max_retries = max_retries
        super().__init__(
            f"[SYSTEM] Aborting process. The logical path is unstable and exceeds error limits. "
            f"(Retries: {retry_count}/{max_retries})"
        )


class ThinkTwiceEngine:
    """
    Orchestration Engine with Speculative Execution.
    
    Critical Attributes:
    - history: List of messages sent to the API.
    - generated_text: Accumulated assistant text in the current response.
    - idea_markers: List of tuples (start, end) for each detected <idea>.
    
    Adaptive Recovery:
    - _current_retry_count: Consecutive retries on the same idea.
    - _base_temperature: Base temperature for generation.
    """
    
    def __init__(self, api_key: str, max_takeovers: int = 100, model_id_generator_override: Optional[str] = None, model_id_auditor_override: Optional[str] = None):
        """
        Initialize the ThinkTwice engine with configuration.
        
        Args:
            api_key: User's API Key (Required).
            max_takeovers: Maximum number of corrections before aborting.
            model_id_generator_override: Optional override for the generator model ID.
            model_id_auditor_override: Optional override for the auditor model ID.
        """
        if not api_key:
            raise ValueError("API Key is required. ThinkTwiceEngine uses BYOK model.")
        
        self.max_takeovers = max_takeovers
        
        # Determine Model IDs: Override > Config
        self.model_id_generator = model_id_generator_override or config.MODEL_ID_GENERATOR
        self.model_id_auditor = model_id_auditor_override or config.MODEL_ID_AUDITOR
        
        # Store the system prompt directly from configuration
        self.system_prompt = GeneratorPrompt
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.BASE_URL
        )
        
        # Chat history: The source of truth sent to the API
        self.history: list[dict] = []
        
        # Generated text in current stream
        self.generated_text: str = ""
        
        # Position markers for ideas: [(start, end), ...]
        self.idea_markers: list[tuple[int, int]] = []
        
        # Async Control
        self.audit_tasks: list[asyncio.Task] = []
        self.takeover_triggered: bool = False
        self.takeover_lock = asyncio.Lock()
        
        # === FINAL ANSWER GUARDRAIL ===
        # Tracks whether we have detected the start of <final_answer> in the stream.
        # When True, we suspend output and await all pending audits before proceeding.
        self._final_answer_pending: bool = False
        
        # Maps idea index -> AuditResult for tracking audit outcomes.
        # Populated by speculative_audit as audits complete.
        self._audit_results: dict[int, AuditResult] = {}
        
        # Task Context (for Auditor)
        self.task_context: str = ""
        
        # === ADAPTIVE RECOVERY ===
        self._current_retry_count: int = 0
        self._base_temperature: float = 0.0
    
    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    async def run(self, user_input: str) -> str:
        """
        Executes the full engine process.
        
        Args:
            user_input: The user's query.
            
        Returns:
            The final generated text (content of <final_answer>).
        """
        self._print_system("ThinkTwice Engine starting...")
        
        self.task_context = user_input
        
        # Initialize history with system prompt and user query
        self.history = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        takeover_count = 0
        self._current_retry_count = 0
        
        while takeover_count < self.max_takeovers:
            # Reset state for this iteration
            self.generated_text = ""
            self.idea_markers = []
            self.audit_tasks = []
            self.takeover_triggered = False
            self._final_answer_pending = False
            self._audit_results = {}
            
            try:
                # Run generator with dynamic temperature
                await self.stream_generator()
                
                # If no takeover, wait for pending audits
                if self.audit_tasks and not self.takeover_triggered:
                    self._print_system("Waiting for final audits...")
                    await asyncio.gather(*self.audit_tasks, return_exceptions=True)
                
                # If valid completion
                if not self.takeover_triggered:
                    self._print_system("Generation completed without errors.")
                    break
                    
            except asyncio.CancelledError:
                # Stream cancelled by Takeover - expected
                pass
            
            takeover_count += 1
            dynamic_temp = self._calculate_dynamic_temperature()
            self._print_system(
                f"Restarting after Takeover ({takeover_count}/{self.max_takeovers}) "
                f"[Temp: {dynamic_temp:.2f}]..."
            )
        
        # Abort if limit reached
        if takeover_count >= self.max_takeovers:
            self._print_error(
                f"[SYSTEM] Aborting process. The logical path is unstable "
                f"and exceeds error limits. (Retries: {takeover_count}/{self.max_takeovers})"
            )
            raise AdaptiveRecoveryAbort(takeover_count, self.max_takeovers)
        
        return self._extract_final_answer()
    
    # =========================================================================
    # GENERATOR
    # =========================================================================
    async def stream_generator(self):
        """
        Consumes API tokens and launches speculative audits on </idea> detection.
        Implements the Final Answer Guardrail: blocks on <final_answer> until all
        pending audits resolve, then branches based on their outcomes.
        """
        self._print_system("Generator: Starting stream...")
        
        try:
            dynamic_temp = self._calculate_dynamic_temperature()
            
            stream = await self.client.chat.completions.create(
                model=self.model_id_generator,
                messages=self.history,
                temperature=dynamic_temp,
                stream=True
            )
            
            async for chunk in stream:
                if self.takeover_triggered:
                    self._print_warning("Stream interrupted by Takeover")
                    return
                
                delta = chunk.choices[0].delta
                if delta.content:
                    token = delta.content
                    self.generated_text += token
                    
                    # Real-time transparency
                    print(f"{Colors.Blue}{token}{Colors.Reset}", end="", flush=True)
                    
                    # Detect closing tags for ideas
                    await self._detect_and_audit_ideas()
                    
                    # === FINAL ANSWER GUARDRAIL ===
                    # Intercept <final_answer> before completion to ensure all audits pass.
                    if "<final_answer" in self.generated_text and not self._final_answer_pending:
                        await self._handle_final_answer_guardrail()
                        if self.takeover_triggered:
                            return
            
            print()  # Newline
            
            # Commit to history only if no Takeover occurred
            if self.generated_text and not self.takeover_triggered:
                self.history.append({
                    "role": "assistant",
                    "content": self.generated_text
                })
                
        except asyncio.CancelledError:
            self._print_warning("StreamGenerator cancelled")
            raise
        except Exception as e:
            self._print_error(f"Error in StreamGenerator: {e}")
            raise
    
    async def _handle_final_answer_guardrail(self):
        """
        Suspends execution when <final_answer> is detected.
        Awaits all pending audits and branches based on their outcomes:
        - Clean Audit: All OK -> proceed normally.
        - Audit Failure: Discard the final answer attempt, inject fix, restart.
        """
        self._final_answer_pending = True
        self._print_system("Final answer detected. Blocking until pending audits resolve...")
        
        # Wait for all pending audit tasks to complete
        if self.audit_tasks:
            await asyncio.gather(*self.audit_tasks, return_exceptions=True)
        
        # Evaluate audit outcomes
        failed_audits = [
            (idx, result) for idx, result in self._audit_results.items()
            if result.status == AuditStatus.FAIL
        ]
        
        if not failed_audits:
            # Scenario A: Clean Audit - all ideas passed, proceed with final answer
            self._print_success("All pending audits passed. Proceeding with final answer.")
            return
        
        # Scenario B: Audit Failure - discard final answer and trigger Takeover
        # Use the first failure's fix (earliest problematic idea)
        first_failure_idx, first_failure_result = min(failed_audits, key=lambda x: x[0])
        
        self._print_error(
            f"Audit failure detected during final answer. "
            f"Idea #{first_failure_idx + 1} failed. Discarding final answer attempt."
        )
        
        await self.trigger_takeover(
            first_failure_result.start_index,
            first_failure_result.fix or "[Correction required]"
        )

    async def _detect_and_audit_ideas(self):
        """
        Scans buffer for completed ideas.
        Launches background audit for new ones.
        """
        pattern = r"<idea>(.*?)</idea>"
        matches = list(re.finditer(pattern, self.generated_text, re.DOTALL))
        
        num_existing = len(self.idea_markers)
        
        for i in range(num_existing, len(matches)):
            match = matches[i]
            start_index = match.start()
            end_index = match.end()
            idea_content = match.group(1).strip()
            
            self.idea_markers.append((start_index, end_index))
            
            # Launch Audit
            audit_task = asyncio.create_task(
                self.speculative_audit(idea_content, start_index, i)
            )
            self.audit_tasks.append(audit_task)
    
    # =========================================================================
    # AUDITOR
    # =========================================================================
    async def speculative_audit(self, idea_text: str, start_index: int, idea_number: int):
        """
        Verifies an idea in background.
        If FAIL and no final_answer is pending, triggers immediate Takeover.
        If FAIL and final_answer IS pending, stores the result for the guardrail to handle.
        """
        self._print_audit(f"Auditing idea #{idea_number + 1}...")
        
        # Initialize as pending in the results tracker
        self._audit_results[idea_number] = AuditResult(
            status=AuditStatus.PENDING,
            start_index=start_index
        )
        
        audit_prompt = f"""TASK CONTEXT:
{self.task_context}

IDEA TO VERIFY:
<idea>{idea_text}</idea>

Verify if this reasoning step is correct."""

        try:
            # Audit uses a separate model (can be faster/cheaper than the generator)
            # This allows using a powerful model for generation and a fast model for auditing.
            response = await self.client.chat.completions.create(
                model=self.model_id_auditor, 
                messages=[
                    {"role": "system", "content": AuditorPrompt},
                    {"role": "user", "content": audit_prompt}
                ],
                temperature=0.1
            )
            
            audit_response = response.choices[0].message.content.strip()
            
            status_match = re.search(r"<status>(OK|FAIL)</status>", audit_response)
            
            if not status_match:
                self._print_warning(f"Auditor returned invalid format: {audit_response[:100]}")
                # Treat unparseable response as OK to avoid blocking indefinitely
                self._audit_results[idea_number] = AuditResult(
                    status=AuditStatus.OK,
                    start_index=start_index
                )
                return
            
            status = status_match.group(1)
            
            if status == "OK":
                self._current_retry_count = 0
                self._print_success(f"Idea #{idea_number + 1}: OK ✓")
                self._audit_results[idea_number] = AuditResult(
                    status=AuditStatus.OK,
                    start_index=start_index
                )
            else:
                fix_match = re.search(r"<fix>(.*?)</fix>", audit_response, re.DOTALL)
                fixed_text = fix_match.group(1).strip() if fix_match else "[No fix provided]"
                
                self._print_error(f"Idea #{idea_number + 1}: FAIL ✗")
                
                # Store the failure result for guardrail evaluation
                self._audit_results[idea_number] = AuditResult(
                    status=AuditStatus.FAIL,
                    fix=fixed_text,
                    start_index=start_index
                )
                
                # If no final_answer is pending, trigger immediate Takeover
                # Otherwise, the guardrail will handle it after awaiting all audits
                if not self._final_answer_pending:
                    self._print_takeover(f"Fix detected: {fixed_text[:80]}...")
                    await self.trigger_takeover(start_index, fixed_text)
                else:
                    self._print_warning(
                        f"Final answer pending. Deferring Takeover to guardrail."
                    )
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._print_error(f"Error in audit: {e}")
    
    # =========================================================================
    # TAKEOVER
    # =========================================================================
    async def trigger_takeover(self, start_index: int, fixed_text: str):
        """
        Executes Takeover using the Append-Only Correction Strategy.
        
        Architectural Decision:
        Rather than slicing or modifying existing history entries (which risks
        corrupting the System/User header and causes "Context Amnesia"), this
        method treats the conversation history as an immutable append-only log.
        
        The flawed assistant reasoning is committed to history as-is, and a new
        "intervention" message is appended. This simulates a conversational
        correction while preserving full context integrity.
        """
        async with self.takeover_lock:
            if self.takeover_triggered:
                return
            
            self.takeover_triggered = True
            self._current_retry_count += 1
        
        self._print_takeover("═══════════════════════════════════════")
        self._print_takeover("TAKEOVER INITIATED (Append-Only Strategy)")
        self._print_takeover("═══════════════════════════════════════")
        
        # Cancel all pending audit tasks to prevent race conditions
        for task in self.audit_tasks:
            if not task.done():
                task.cancel()
        
        # Commit the flawed assistant response to history if not already present.
        # This preserves the conversational flow and provides context for the correction.
        if self.generated_text:
            # Truncate at the point of failure to avoid committing further flawed content
            truncated_response = self.generated_text[:start_index] if start_index > 0 else self.generated_text
            self._print_takeover(f"Committing truncated response ({len(truncated_response)} chars) to history.")
            self.history.append({
                "role": "assistant",
                "content": truncated_response
            })
        
        # Construct and append the Intervention Message.
        # This message contains the correction, protocol reminder, and task re-anchor.
        intervention_content = InterventionMessage.format(
            fix=fixed_text,
            user_task=self.task_context
        )
        
        self.history.append({
            "role": "user",
            "content": intervention_content
        })
        
        self._print_takeover(f"Intervention appended with fix: {fixed_text[:60]}...")
        self._print_takeover("History preserved. Intervention message added. Ready for restart.")
        self._print_takeover("═══════════════════════════════════════")
        
        # Reset idea markers for the next generation cycle
        self.idea_markers = []
    
    # =========================================================================
    # UTILS
    # =========================================================================
    def _calculate_dynamic_temperature(self) -> float:
        """
        Jitter/Dynamic temperature based on retry count.
        """
        temp_increment = max(0, (self._current_retry_count - 1) * 0.1)
        return min(self._base_temperature + temp_increment, 1.0)
    
    def _extract_final_answer(self) -> str:
        """Extracts content inside <final_answer>."""
        assistant_messages = [m for m in self.history if m["role"] == "assistant"]
        if not assistant_messages:
            return self.generated_text
        
        last_assistant = assistant_messages[-1]["content"]
        match = re.search(r"<final_answer>(.*?)</final_answer>", last_assistant, re.DOTALL)
        if match:
            return match.group(1).strip()
        return last_assistant
    
    def _print_system(self, message: str):
        print(f"\n{Colors.Cyan}[SYSTEM] {message}{Colors.Reset}")
    
    def _print_success(self, message: str):
        print(f"\n{Colors.Green}[AUDIT] {message}{Colors.Reset}")
    
    def _print_warning(self, message: str):
        print(f"\n{Colors.Yellow}[WARNING] {message}{Colors.Reset}")
    
    def _print_error(self, message: str):
        print(f"\n{Colors.Red}[ERROR] {message}{Colors.Reset}")
    
    def _print_audit(self, message: str):
        print(f"\n{Colors.Yellow}[AUDIT] {message}{Colors.Reset}")
    
    def _print_takeover(self, message: str):
        print(f"\n{Colors.Magenta}{Colors.Bold}[TAKEOVER] {message}{Colors.Reset}")
