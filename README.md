# Prompt Optimizer

> **Developed for the Moonshot Challenge (MISTRAL)**

Automated prompt refinement system that iteratively improves LLM prompts using self-correction.

## 1. Project Overview

**Problem**: Designing effective prompts for Large Language Models (LLMs) is often a manual, trial-and-error process ("prompt engineering") that is time-consuming and difficult for complex prompts.

**Solution**: Prompt Optimizer automates this process by using an LLM (Mistral) to "refine" a rough prompt. It uses an **Arena Mode Refinement** strategy where each iteration generates candidates from multiple models.

**Key Features**:
*   **Multi-Model Arena**: Compares outputs from **Mistral Small, Medium, and Large** in every step.
*   **Codestral Integration**: Switch to **Code Domain** to use specialized `codestral-latest` models for programming tasks.
*   **Mistral Large Judging**: Uses high-tier reasoning to score (0-10) and critique prompt variations with strict evaluation criteria.
*   **Domain & Context Awareness**: Tailors refinement based on the domain (General or Code) and specific context provided by the user.
*   **Markdown Support**: Visualizes outputs with rich formatting (code blocks, headers, lists).
*   **Real-time Visualization**: Interactive UI showing the refinement history.
*   **Instant Testing**: Built-in playground to immediately test refined prompts with custom inputs.

**Status**: MVP

## 2. Technical Requirements
*   **Python**: Version 3.10 or higher
*   **API Keys**: [Mistral AI API Key](https://console.mistral.ai/)
*   **Dependencies**:
    *   `fastapi`
    *   `uvicorn`
    *   `mistralai`
    *   `sqlmodel`
    *   `pydantic`
    *   `python-dotenv`

## 3. Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone <repository-url>
    cd promptImprovingLLM
    ```

2.  **Create a Virtual Environment**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies**
    Using `pip` and `pyproject.toml`:
    ```bash
    pip install -e .
    ```

4.  **Configuration**
    Create a `.env` file in the project root:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and add your Mistral API key:
    ```ini
    MISTRAL_API_KEY=your_actual_api_key_here
    ```

5.  **Database Setup**
    The SQLite database (`prompt_store.db`) is initialized on the first run. No manual setup required.

## 4. Usage Instructions

### Running the Server
Start the backend server which serves both the API and the frontend UI:

```bash
python run_server.py
```

### Using the Web Interface
1.  Open **http://localhost:8000** in your web browser.
2.  **Dashboard**: Displays the current active prompt and optimization status.
3.  **Refine a Prompt**:
    *   Paste a rough draft of a prompt.
    *   (Optional) Add **Context** to guide the refiner.
    *   Select **Domain** (General or Code) to use specialized models.
    *   Click "Refine Prompt".
4.  **Test**: Use the "Test Refined Prompt" section to test the best-performing prompt with custom inputs.

## 5. Architecture & Design
### Key Components
1.  **Prompt Refiner (`refiner.py`)**:
    *   Takes a rough prompt and iteratively improves it using an LLM.
    *   Focuses on clarity, structure, and effectiveness.

2.  **Prompt Store (`store.py`)**:
    *   Uses `SQLModel` (SQLAlchemy wrapper) to persist Prompts.
    *   Enables genealogy tracking (Parent -> Child prompts).

## 6. API Documentation
The server exposes a RESTful API at `http://localhost:8000/api`.

### Endpoints


#### `POST /api/refine`
Quickly refine a single prompt without a dataset.
*   **Request Body**: 
    ```json
    {
        "rough_prompt": "...",
        "context": "optional context",
        "domain": "general|code",
        "max_iterations": 3
    }
    ```

#### `GET /api/prompts`
List all prompts and their metrics.

#### `POST /api/test`
Test a specific prompt.
*   **Request Body**:
    ```json
    {
        "prompt_content": "...",
        "user_input": "..."
    }
    ```

### Directory Structure
```
src/
└── prompt_optimizer/
    ├── api.py           # FastAPI application
    ├── refiner.py       # Single-pass refinement
    ├── store.py         # Database models & access
    └── static/          # Frontend assets
```

## 8. Contribution & Maintenance
We welcome contributions!

### Third-Party Dependencies
*   **Mistral AI**: Usage subject to Mistral AI Terms of Service.
*   **FastAPI**: MIT License.

## 10. Additional Resources
*   **FastAPI Documentation**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
*   **Mistral AI Docs**: [docs.mistral.ai](https://docs.mistral.ai)
