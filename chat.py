# =============================================================================
# ThinkTwice - Interactive Chat Interface
# =============================================================================
"""
Interactive chat interface for the ThinkTwice reasoning engine.

This module provides a command-line interface for conversing with ThinkTwice
in DEEP mode, which displays the complete reasoning process in real-time,
including idea generation, auditing, corrections, and final answers.

Features:
    - Real-time streaming of reasoning process
    - Visual feedback through color-coded output
    - Stateless conversation (no memory between messages)
    - Graceful error handling and recovery
    - Configurable model selection via config.py

Color Coding:
    - Blue: Generated text streaming from the model
    - Yellow: Audit operations in progress
    - Green: Validated ideas and final answers
    - Magenta: Takeover events (surgical corrections)
    - Red: Errors and failures

Requirements:
    - API key must be configured in config.py (see config.template.py)
    - All dependencies must be installed (see requirements.txt)
"""

import asyncio
import sys
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


def load_api_key():
    """
    Retrieves the API key from configuration or prompts the user to enter it.
    
    This function first attempts to load the API key from config.py. If the key
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


async def main():
    """
    Main entry point for the interactive chat interface.
    
    This asynchronous function manages the chat loop, handling user input,
    engine initialization, and output display. Each message is processed
    independently without conversation history, ensuring stateless operation.
    
    The function handles:
        - Initial setup and API key loading
        - Continuous message processing loop
        - Error recovery and graceful degradation
        - Clean shutdown on user request
    """
    # Display application banner
    print(f"{Colors.Cyan}{Colors.Bold}")
    print("╔═══════════════════════════════════════════╗")
    print("║         Chat with ThinkTwice              ║")
    print("╚═══════════════════════════════════════════╝")
    print(f"{Colors.Reset}")
    
    # Load and validate API key
    api_key = load_api_key()
    
    # Display color legend for user reference
    print(f"{Colors.Dim}Color Legend:{Colors.Reset}")
    print(f"  {Colors.Blue}■ Blue:{Colors.Reset} Generated Text (Streaming)")
    print(f"  {Colors.Yellow}■ Yellow:{Colors.Reset} Audit in Progress")
    print(f"  {Colors.Green}■ Green:{Colors.Reset} Validated Idea (OK)")
    print(f"  {Colors.Magenta}■ Magenta:{Colors.Reset} Takeover (Correction)")
    print(f"  {Colors.Red}■ Red:{Colors.Reset} Error Detected")
    print()
    
    # Main conversation loop - continues until user exits
    while True:
        # Prompt for user input
        print(f"{Colors.Cyan}Enter your message (or 'exit' to quit):{Colors.Reset}")
        user_input = input(f"{Colors.Bold}> {Colors.Reset}")
        
        # Check for exit commands
        if user_input.lower() in ['exit', 'quit', 'q']:
            print(f"{Colors.Yellow}Exiting chat...{Colors.Reset}")
            break
        
        # Validate input is not empty
        if not user_input.strip():
            print(f"{Colors.Red}Error: Empty input.{Colors.Reset}")
            continue
        
        print()
        
        # Initialize a fresh engine instance for this message (stateless design)
        # The model ID is taken from config.py to allow user customization
        engine = ThinkTwiceEngine(
            api_key=api_key,
            model_id_generator_override=config.MODEL_ID_GENERATOR,
            model_id_auditor_override=config.MODEL_ID_AUDITOR
        )
        
        try:
            # Execute the reasoning engine with the user's input
            final_result = await engine.run(user_input)
            
            # Display the final answer in a formatted box
            print()
            print(f"{Colors.Green}{Colors.Bold}")
            print("╔════════════════════════════════════════════════════════════╗")
            print("║                    FINAL RESULT                            ║")
            print("╚════════════════════════════════════════════════════════════╝")
            print(f"{Colors.Reset}")
            print(final_result)
            print()
            
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully without terminating the chat session
            print(f"\n{Colors.Yellow}Message interrupted by user (Ctrl+C){Colors.Reset}")
            print(f"{Colors.Dim}You can continue chatting or type 'exit' to quit.{Colors.Reset}\n")
            continue
        except Exception as e:
            # Handle any other errors gracefully, allowing the user to retry
            print(f"\n{Colors.Red}Error: {e}{Colors.Reset}")
            print(f"{Colors.Dim}You can try again with a different message.{Colors.Reset}\n")
            continue


if __name__ == "__main__":
    # Run the async main function using asyncio
    asyncio.run(main())
