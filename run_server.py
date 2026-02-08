#!/usr/bin/env python3
"""
Server Entry Point.

FastAPI backend server and frontend.
"""

import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
SRC_PATH = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_PATH))

from prompt_optimizer.api import app

def main():
    """Entry point to run the server."""
    # Load environment variables
    load_dotenv()

    # Check for API key
    if not os.getenv("MISTRAL_API_KEY"):
        print("Warning: MISTRAL_API_KEY not set.")
        print("   Please set it before running:")
        print("   export MISTRAL_API_KEY=your_key_here")
        print()

    print("Starting server")
    print("   Open http://localhost:8000")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    main()
