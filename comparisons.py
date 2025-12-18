# =============================================================================
# ThinkTwice - Comparison Runner
# =============================================================================
"""
Comparison execution system for evaluating different reasoning modes.

This module provides a framework for running side-by-side comparisons between
three distinct execution modes:
    - Raw: Direct API call without any reasoning enhancements
    - DeepThink: Native model reasoning via include_reasoning parameter
    - ThinkTwice: Our custom speculative execution engine

The system executes the same prompts across all three modes and saves the
outputs to organized directories for later analysis.

Output Structure:
    outputs/
    └── YYYY-MM-DD_HH-MM-SS/
        ├── Raw.md                  # Standard model output
        ├── DeepThink.md            # Output with native reasoning
        ├── DeepThinkArtifacts.md   # Reasoning artifacts from DeepThink
        ├── ThinkTwice.md           # ThinkTwice final answer
        └── ThinkTwiceArtifacts.md  # Full reasoning process + JSON

Requirements:
    - API key must be configured in config.py (see config.template.py)
    - Prompts must be added to the PROMPTS array below
"""

# =============================================================================
# PROMPTS CONFIGURATION
# =============================================================================
# Add your prompts to this array. Each prompt will be executed across all three
# comparison modes (Raw, DeepThink, ThinkTwice).
#
# We have placed this configuration at the top of the file for quick access.
#
# Example:
#   PROMPTS = [
#       "Explain the theory of relativity in simple terms.",
#       "Write a Python function to calculate the Fibonacci sequence.",
#       "What are the main differences between TCP and UDP?",
#   ]

PROMPTS = [
    # TEST 1: The "Winter Lipogram" (Negative Constraint)
    # Objective: Force the model to avoid a common letter ('a'). 
    # Standard LLMs often fail this because tokens containing 'a' look valid to them.
    """
    Write a 3-sentence description of a snowy winter scene.
    
    HARD CONSTRAINT: You are **STRICTLY FORBIDDEN** from using the letter 'a' (case-insensitive).
    
    ADDITIONAL RULES:
    1. Do not use the words: "and", "flake", "dark", "play", "day", "clear".
    2. If you use a forbidden letter or word, you must correct it immediately.
    3. Output the final 3 sentences clearly.
    """
]

import asyncio
import sys
import os
import io
import json
from datetime import datetime
from typing import Optional
from contextlib import redirect_stdout
import colorama

# Enable ANSI color codes on Windows terminals
colorama.init()

# Import color definitions for consistent terminal output
from thinktwice_config import Colors

# =============================================================================
# Configuration Import Guard
# =============================================================================
# Attempt to import user configuration file.
# The config.py file must be manually created from config.template.py to ensure
# that API keys are never accidentally committed to version control.
try:
    import config
except ImportError:
    # Display detailed error message if configuration is missing
    print(f"\n{Colors.Red}{Colors.Bold}╔════════════════════════════════════════════════════════════╗{Colors.Reset}")
    print(f"{Colors.Red}{Colors.Bold}║                   CONFIGURATION ERROR                      ║{Colors.Reset}")
    print(f"{Colors.Red}{Colors.Bold}╚════════════════════════════════════════════════════════════╝{Colors.Reset}\n")
    print(f"{Colors.Red}❌ Error: Configuration file not found.{Colors.Reset}\n")
    print(f"{Colors.Yellow}To fix this:{Colors.Reset}")
    print(f"  1. Rename {Colors.Bold}config.template.py{Colors.Reset} to {Colors.Bold}config.py{Colors.Reset}")
    print(f"  2. Edit {Colors.Bold}config.py{Colors.Reset} and add your API Key")
    print(f"  3. Run this script again\n")
    sys.exit(1)

# Import ThinkTwice engine components after successful configuration validation
from engine import ThinkTwiceEngine
from openai import AsyncOpenAI


def load_api_key() -> str:
    """
    Retrieves the API key from configuration or prompts the user to enter it.
    
    This function attempts to load the API key from config.py. If the key
    is not configured or appears invalid, it prompts the user to enter it manually.
    For security, only a partial key preview is displayed when loaded from config.
    
    Returns:
        str: A valid API key for authentication with the language model provider.
    """
    # Attempt to retrieve API key from configuration file
    api_key = config.API_KEY
    
    # Validate that the key exists and has a reasonable length
    if api_key and len(api_key.strip()) > 5:
        print(f"{Colors.Green}✓ API Key loaded from config.py{Colors.Reset}")
        
        # Display partial key for verification (security measure)
        mask_len = min(4, len(api_key) - 4)
        print(f"{Colors.Dim}Key: {api_key[:mask_len]}...{Colors.Reset}\n")
        return api_key
    
    # If key is not configured, prompt user for manual entry
    print(f"{Colors.Cyan}{Colors.Bold}╔════════════════════════════════════════════════════════════╗{Colors.Reset}")
    print(f"{Colors.Cyan}{Colors.Bold}║             API Key Configuration (Required)               ║{Colors.Reset}")
    print(f"{Colors.Cyan}{Colors.Bold}╚════════════════════════════════════════════════════════════╝{Colors.Reset}")
    print()
    print(f"{Colors.Yellow}API_KEY not found in config.py{Colors.Reset}")
    print(f"{Colors.Dim}You can set it permanently in `config.py`{Colors.Reset}")
    print()
    
    # Loop until a valid key is provided
    while True:
        api_key = input(f"{Colors.Bold}Enter your API Key: {Colors.Reset}").strip()
        
        if not api_key:
            print(f"{Colors.Red}Error: API Key cannot be empty.{Colors.Reset}")
            continue
            
        print(f"{Colors.Green}✓ Valid API Key provided{Colors.Reset}\n")
        return api_key


async def execute_raw(client: AsyncOpenAI, prompt: str) -> str:
    """
    Executes a prompt using the standard API call without reasoning enhancements.
    
    This mode represents the baseline model behavior without any special
    reasoning mechanisms or prompt engineering.
    
    Args:
        client: Initialized AsyncOpenAI client.
        prompt: The user prompt to send to the model.
        
    Returns:
        str: The raw model response.
    """
    print(f"{Colors.Blue}[RAW] Executing standard API call...{Colors.Reset}")
    
    response = await client.chat.completions.create(
        model=config.MODEL_ID_GENERATOR,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=4096
    )
    
    return response.choices[0].message.content


async def execute_deepthink(client: AsyncOpenAI, prompt: str) -> tuple[str, str]:
    """
    Executes a prompt with native model reasoning enabled.
    
    This mode activates the model's built-in reasoning capabilities via the
    include_reasoning parameter, which instructs the API to return both
    the reasoning process and the final answer.
    
    Args:
        client: Initialized AsyncOpenAI client.
        prompt: The user prompt to send to the model.
        
    Returns:
        tuple[str, str]: A tuple containing (final_answer, reasoning_artifacts).
    """
    print(f"{Colors.Magenta}[DEEPTHINK] Executing with native reasoning...{Colors.Reset}")
    
    # Call API with reasoning enabled via extra_body parameter
    response = await client.chat.completions.create(
        model=config.MODEL_ID_GENERATOR,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=16384,
        extra_body={"include_reasoning": True}
    )
    
    # Extract content and reasoning from response
    choice = response.choices[0]
    final_content = choice.message.content or ""
    
    # Attempt to extract reasoning artifacts if available
    reasoning_artifacts = ""
    if hasattr(choice.message, 'reasoning') and choice.message.reasoning:
        reasoning_artifacts = choice.message.reasoning
    elif hasattr(choice.message, 'reasoning_content') and choice.message.reasoning_content:
        reasoning_artifacts = choice.message.reasoning_content
    
    return final_content, reasoning_artifacts


async def execute_thinktwice(api_key: str, prompt: str) -> tuple[str, str]:
    """
    Executes a prompt using the ThinkTwice speculative execution engine.
    
    This mode utilizes our custom reasoning architecture with:
        - Streaming idea generation
        - Parallel auditing
        - History takeover for error correction
    
    The function captures both the final answer and the complete reasoning
    process (console output) for artifact collection.
    
    Args:
        api_key: User's API key for authentication.
        prompt: The user prompt to send to the engine.
        
    Returns:
        tuple[str, str]: A tuple containing (final_answer, full_reasoning_process).
    """
    print(f"{Colors.Cyan}[THINKTWICE] Executing speculative reasoning engine...{Colors.Reset}")
    
    # Capture console output for artifacts
    captured_output = io.StringIO()
    
    # Initialize ThinkTwice engine
    engine = ThinkTwiceEngine(
        api_key=api_key,
        model_id_generator_override=config.MODEL_ID_GENERATOR,
        model_id_auditor_override=config.MODEL_ID_AUDITOR
    )
    
    # Execute with output capture
    # We need to capture stdout while still allowing some output
    original_stdout = sys.stdout
    
    # Create a tee-like writer that writes to both console and buffer
    class TeeWriter:
        def __init__(self, original, buffer):
            self.original = original
            self.buffer = buffer
        
        def write(self, text):
            self.original.write(text)
            self.buffer.write(text)
        
        def flush(self):
            self.original.flush()
    
    sys.stdout = TeeWriter(original_stdout, captured_output)
    
    try:
        final_result = await engine.run(prompt)
    finally:
        sys.stdout = original_stdout
    
    # Initialize the artifact collection container.
    # We will accumulate the full context, reasoning logs, and history here
    # to create a comprehensive audit trail of the model's thought process.
    artifacts = []
    
    # 1. Task Context:
    # Preserve the original task context (user input) at the top of the log
    # to ensure the reasoning process can be understood in isolation.
    artifacts.append("## Task Context\n")
    artifacts.append(f"```\n{engine.task_context}\n```\n\n")
    
    # Add the complete reasoning process (cleaned of ANSI codes)
    artifacts.append("## Reasoning Process (Console Output)\n")
    artifacts.append("```\n")
    # Strip ANSI color codes for clean markdown rendering
    clean_output = strip_ansi_codes(captured_output.getvalue())
    artifacts.append(clean_output)
    artifacts.append("\n```\n")
    
    # Add the conversation history
    artifacts.append("\n## Conversation History\n")
    for i, msg in enumerate(engine.history):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:500]  # Truncate for readability
        artifacts.append(f"### Message {i+1} ({role})\n```\n{content}\n```\n\n")
    
    return final_result, "".join(artifacts)


def create_output_directory() -> str:
    """
    Creates a timestamped output directory for storing comparison results.
    
    The directory structure follows the pattern:
        outputs/YYYY-MM-DD_HH-MM-SS/
    
    Returns:
        str: Absolute path to the created output directory.
    """
    # Generate timestamp for directory name
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Construct output path
    output_dir = os.path.join(os.path.dirname(__file__), "outputs", timestamp)
    
    # Create directory structure (including parent 'outputs' if needed)
    os.makedirs(output_dir, exist_ok=True)
    
    return output_dir


def strip_ansi_codes(text: str) -> str:
    """
    Strips ANSI color codes from text for clean markdown output.
    
    Console output contains ANSI escape sequences for coloring terminal text.
    These codes break markdown rendering and must be removed from artifact files.
    
    Args:
        text: Text containing ANSI codes like '\u001b[94m' for colors.
        
    Returns:
        str: Clean text without ANSI codes.
    """
    import re
    # Pattern matches ANSI escape sequences: ESC[...m
    ansi_pattern = r'\x1b\[[0-9;]*m'
    return re.sub(ansi_pattern, '', text)


def extract_final_answer(text: str) -> str:
    """
    Extracts the clean final answer from ThinkTwice output.
    
    Handles edge cases where the <final_answer> tag may be split by streaming
    or audit messages. Uses progressive fallback patterns to reconstruct.
    
    Args:
        text: The raw ThinkTwice output containing idea tags and final answer.
        
    Returns:
        str: The extracted final answer, or an error message if not found.
    """
    import re
    
    # 1. Try standard extraction: <final_answer>...</final_answer>
    match = re.search(r'<final_answer>(.*?)</final_answer>', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 2. Fallback: Look for </final_answer> and reconstruct backwards
    # This handles cases where <final_answer was split by streaming
    end_tag_match = re.search(r'</final_answer>', text)
    if not end_tag_match:
        return "[ERROR: No </final_answer> tag found. Generation incomplete.]"
    
    # Find the position of </final_answer>
    end_pos = end_tag_match.start()
    text_before_end = text[:end_pos]
    
    # 3. Progressive search for start boundary (going backwards)
    # Try increasingly shorter suffixes to find where content starts
    start_patterns = [
        ('</idea>', 'after last </idea>'),
        ('/idea>', 'after partial /idea>'),
        ('idea>', 'after partial idea>'),
        ('dea>', 'after partial dea>'),
        ('ea>', 'after partial ea>'),
        ('a>', 'after partial a>'),
        ('>', 'after last >'),
    ]
    
    for pattern, description in start_patterns:
        last_match = text_before_end.rfind(pattern)
        if last_match != -1:
            # Extract content after this pattern
            content_start = last_match + len(pattern)
            extracted = text_before_end[content_start:].strip()
            
            # Clean up any stray newlines or system messages
            # Remove lines that look like system output
            lines = extracted.split('\n')
            clean_lines = [
                line for line in lines 
                if not line.strip().startswith('[') and line.strip()
            ]
            clean_content = '\n'.join(clean_lines).strip()
            
            if clean_content:
                return f"[RECONSTRUCTED {description}]\n{clean_content}"
    
    return "[ERROR: Could not reconstruct final answer from malformed tags.]"


def save_main_output(output_dir: str, filename: str, content: str, prompt: str):
    """
    Saves main comparison output (Raw, DeepThink, ThinkTwice answers) to a markdown file.
    
    These files contain the FINAL ANSWERS only, without artifacts or reasoning traces.
    Format includes header with metadata and the clean response.
    
    Args:
        output_dir: Path to the output directory.
        filename: Name of the output file (e.g., 'Raw.md', 'ThinkTwice.md').
        content: The final answer content to save.
        prompt: The original prompt for context.
    """
    filepath = os.path.join(output_dir, filename)
    mode_name = filename.replace('.md', '')
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {mode_name} Output\n\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Generator Model:** {config.MODEL_ID_GENERATOR}\n")
        if mode_name == "ThinkTwice":
            f.write(f"**Auditor Model:** {config.MODEL_ID_AUDITOR}\n")
        f.write(f"\n## Prompt\n\n```\n{prompt}\n```\n\n")
        f.write(f"## Final Answer\n\n{content}\n")


def save_artifact(output_dir: str, filename: str, content: str, prompt: str):
    """
    Saves artifact files (reasoning traces, console logs, conversation history).
    
    Artifact files contain the full reasoning process and debug information.
    They do NOT include a "## Response" header - only the artifact content itself.
    
    Args:
        output_dir: Path to the output directory.
        filename: Name of the artifact file (e.g., 'ThinkTwiceArtifacts.md').
        content: The artifact content (reasoning logs, history, etc.).
        prompt: The original prompt for context.
    """
    filepath = os.path.join(output_dir, filename)
    mode_name = filename.replace('Artifacts.md', '').replace('.md', '')
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {mode_name} Artifacts\n\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write(f"**Generator Model:** {config.MODEL_ID_GENERATOR}\n")
        if "ThinkTwice" in mode_name:
            f.write(f"**Auditor Model:** {config.MODEL_ID_AUDITOR}\n")
        f.write(f"\n## Original Prompt\n\n```\n{prompt}\n```\n\n")
        # Write artifact content directly without additional headers
        f.write(content)


async def run_comparison(api_key: str, prompt: str, output_dir: str):
    """
    Executes a single prompt across all three comparison modes.
    
    This function orchestrates the execution of Raw, DeepThink, and ThinkTwice
    modes sequentially, saving all outputs and artifacts to the specified
    output directory.
    
    Args:
        api_key: User's API key for authentication.
        prompt: The prompt to execute across all modes.
        output_dir: Directory where outputs will be saved.
    """
    # Initialize OpenAI client for Raw and DeepThink modes
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=config.BASE_URL
    )
    
    print(f"\n{Colors.Bold}{'='*60}{Colors.Reset}")
    print(f"{Colors.Cyan}Executing comparison for prompt:{Colors.Reset}")
    print(f"{Colors.Dim}{prompt[:100]}{'...' if len(prompt) > 100 else ''}{Colors.Reset}")
    print(f"{Colors.Bold}{'='*60}{Colors.Reset}\n")
    
    # Execute Raw mode
    try:
        raw_result = await execute_raw(client, prompt)
        save_main_output(output_dir, "Raw.md", raw_result, prompt)
        print(f"{Colors.Green}✓ Raw output saved{Colors.Reset}")
    except Exception as e:
        print(f"{Colors.Red}✗ Raw execution failed: {e}{Colors.Reset}")
        save_main_output(output_dir, "Raw.md", f"ERROR: {e}", prompt)
    
    # Execute DeepThink mode
    try:
        deepthink_result, deepthink_artifacts = await execute_deepthink(client, prompt)
        # Save clean final answer
        save_main_output(output_dir, "DeepThink.md", deepthink_result, prompt)
        # Save reasoning artifacts (if any)
        if deepthink_artifacts.strip():
            save_artifact(output_dir, "DeepThinkArtifacts.md", deepthink_artifacts, prompt)
        print(f"{Colors.Green}✓ DeepThink output saved{Colors.Reset}")
    except Exception as e:
        print(f"{Colors.Red}✗ DeepThink execution failed: {e}{Colors.Reset}")
        save_main_output(output_dir, "DeepThink.md", f"ERROR: {e}", prompt)
    
    # Execute ThinkTwice mode
    try:
        thinktwice_raw_result, thinktwice_artifacts = await execute_thinktwice(api_key, prompt)
        # Extract clean final answer from <final_answer> tags
        thinktwice_clean = extract_final_answer(thinktwice_raw_result)
        # Save clean final answer
        save_main_output(output_dir, "ThinkTwice.md", thinktwice_clean, prompt)
        # Save full reasoning artifacts
        save_artifact(output_dir, "ThinkTwiceArtifacts.md", thinktwice_artifacts, prompt)
        print(f"{Colors.Green}✓ ThinkTwice output saved{Colors.Reset}")
    except Exception as e:
        print(f"{Colors.Red}✗ ThinkTwice execution failed: {e}{Colors.Reset}")
        save_main_output(output_dir, "ThinkTwice.md", f"ERROR: {e}", prompt)
        save_artifact(output_dir, "ThinkTwiceArtifacts.md", f"ERROR: {e}", prompt)


async def main():
    """
    Main entry point for the comparison runner.
    
    This function handles the complete workflow:
        1. Display banner and load API key
        2. Validate that prompts are configured
        3. Confirm execution with user
        4. Execute comparisons for all prompts
        5. Save results to timestamped output directory
    """
    # Display application banner
    print(f"{Colors.Cyan}{Colors.Bold}")
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║          ThinkTwice - Comparison Runner                   ║")
    print("║       Raw vs DeepThink vs ThinkTwice                      ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print(f"{Colors.Reset}")
    
    # Load and validate API key
    api_key = load_api_key()
    
    # Validate that prompts array is not empty
    if not PROMPTS:
        print(f"{Colors.Yellow}{Colors.Bold}╔════════════════════════════════════════════════════════════╗{Colors.Reset}")
        print(f"{Colors.Yellow}{Colors.Bold}║                    NO PROMPTS CONFIGURED                   ║{Colors.Reset}")
        print(f"{Colors.Yellow}{Colors.Bold}╚════════════════════════════════════════════════════════════╝{Colors.Reset}\n")
        print(f"{Colors.Yellow}The PROMPTS array is empty.{Colors.Reset}")
        print(f"{Colors.Dim}To run comparisons, add your prompts to the PROMPTS array at the top of this file.{Colors.Reset}")
        print(f"\n{Colors.Dim}Example:{Colors.Reset}")
        print(f'PROMPTS = [')
        print(f'    "Explain quantum entanglement in simple terms.",')
        print(f'    "Write a sorting algorithm in Python.",')
        print(f']\n')
        return
    
    # Display configured prompts
    print(f"{Colors.Green}{Colors.Bold}Found {len(PROMPTS)} prompt(s) configured:{Colors.Reset}\n")
    for i, prompt in enumerate(PROMPTS, 1):
        preview = prompt[:80] + "..." if len(prompt) > 80 else prompt
        print(f"  {Colors.Dim}{i}.{Colors.Reset} {preview}")
    
    print()
    
    # Confirm execution
    print(f"{Colors.Cyan}Do you want to execute the comparison? (yes/no):{Colors.Reset}")
    confirmation = input(f"{Colors.Bold}> {Colors.Reset}").strip().lower()
    
    if confirmation not in ['yes', 'y', 'si', 's']:
        print(f"{Colors.Yellow}Comparison cancelled.{Colors.Reset}")
        return
    
    # Create output directory
    output_dir = create_output_directory()
    print(f"\n{Colors.Green}Output directory: {output_dir}{Colors.Reset}\n")
    
    # Execute comparisons for each prompt
    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n{Colors.Cyan}{Colors.Bold}[{i}/{len(PROMPTS)}] Processing prompt...{Colors.Reset}")
        
        # For multiple prompts, create subdirectories
        if len(PROMPTS) > 1:
            prompt_dir = os.path.join(output_dir, f"prompt_{i:02d}")
            os.makedirs(prompt_dir, exist_ok=True)
        else:
            prompt_dir = output_dir
        
        await run_comparison(api_key, prompt, prompt_dir)
    
    # Final summary
    print(f"\n{Colors.Green}{Colors.Bold}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    COMPARISON COMPLETE                     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.Reset}")
    print(f"{Colors.Green}Results saved to: {output_dir}{Colors.Reset}")
    print(f"{Colors.Dim}Open the markdown files to view and compare outputs.{Colors.Reset}\n")


if __name__ == "__main__":
    # Run the async main function using asyncio
    asyncio.run(main())
