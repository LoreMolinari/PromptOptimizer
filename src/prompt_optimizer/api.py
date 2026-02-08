"""
FastAPI Application (REST API) for the Prompt Optimizer.

Exposes prompt refinement capabilities via a REST API.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from prompt_optimizer.store import init_db, PromptRepository
from prompt_optimizer.refiner import PromptRefiner

# Load environment variables
load_dotenv()

# Global state for tracking refinement
REFINEMENT_STATE: Dict[str, Any] = {
    "running": False,
    "result": None,
    "error": None
}

DB_PATH = "sqlite:///prompt_store.db"

# Initialize FastAPI app
app = FastAPI(
    title="Prompt Optimizer",
    description="Automatic prompt improvement using LLM-driven refinement",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Pydantic Models
# =============================================================================

class RefineRequest(BaseModel):
    """Request to refine a prompt."""
    rough_prompt: str
    max_iterations: int = 3
    context: Optional[str] = None
    model: str = "mistral-small-latest"
    domain: str = "general"


class TestPromptRequest(BaseModel):
    """Request to test a prompt with custom input."""
    prompt_content: str
    user_input: str


class PromptInfo(BaseModel):
    """Response model for prompt."""
    id: int
    content: str
    is_baseline: bool
    created_at: str
    accuracy: Optional[float] = None
    evaluations_count: int = 0


# =============================================================================
# Background Tasks
# =============================================================================

def run_refinement_background(
    rough_prompt: str,
    max_iterations: int,
    context: Optional[str],
    model: str,
    domain: str = "general"
) -> None:
    """
    Background task to run the refinement process.
    
    Updates the global REFINEMENT_STATE with results or errors.
    """
    try:
        refiner = PromptRefiner(model=model)
        result = refiner.refine(
            rough_prompt=rough_prompt,
            max_iterations=max_iterations,
            context=context,
            domain=domain
        )
        
        # Store in database
        engine = init_db(DB_PATH)
        prompt_repo = PromptRepository(engine)
        
        # Map array index in result.all_versions to Database ID
        idx_to_db_id = {}
        final_refined_id = None
        
        for idx, item in enumerate(result.all_versions):
            # Resolve parent ID from mapping
            parent_idx = item["parent_idx"]
            db_parent_id = idx_to_db_id.get(parent_idx) if parent_idx is not None else None
            
            is_baseline = (item["iteration"] == 0)
            is_best = item.get("is_best", False)
            
            # Determine type
            if is_baseline:
                prompt_type = "rough"
            elif is_best and item["iteration"] == result.iterations:
                prompt_type = "refined"
            else:
                prompt_type = "intermediate"

            prompt = prompt_repo.create(
                content=item["content"],
                metadata={
                    "iteration": item["iteration"],
                    "type": prompt_type,
                    "is_best": is_best
                },
                is_baseline=is_baseline,
                parent_id=db_parent_id,
                score=item["score"],
                critique=item["critique"],
                model_name=item.get("model_name"),
                domain=domain
            )
            
            idx_to_db_id[idx] = prompt.id
            
            if is_best and item["iteration"] == result.iterations:
                final_refined_id = prompt.id
        
        # Update state with success result
        REFINEMENT_STATE["result"] = {
            "original_prompt": result.original_prompt,
            "final_prompt": result.final_prompt,
            "iterations": result.iterations,
            "total_tokens": result.total_tokens,
            "all_versions": result.all_versions,
            "refined_prompt_id": final_refined_id
        }
        
    except Exception as e:
        print(f"Refinement Error: {e}")
        REFINEMENT_STATE["error"] = str(e)
    finally:
        REFINEMENT_STATE["running"] = False


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML application."""
    frontend_path = Path(__file__).parent / "static" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return HTMLResponse(
        "<html><body><h1>Frontend not found</h1></body></html>", 
        status_code=404
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/api/refine")
async def start_refinement(
    request: RefineRequest,
    background_tasks: BackgroundTasks
):
    """Start a quick prompt refinement task in the background."""
    if REFINEMENT_STATE["running"]:
        raise HTTPException(status_code=409, detail="Refinement already running")
    
    if not os.getenv("MISTRAL_API_KEY"):
        raise HTTPException(status_code=400, detail="MISTRAL_API_KEY not configured")
    
    # Reset state
    REFINEMENT_STATE["running"] = True
    REFINEMENT_STATE["result"] = None
    REFINEMENT_STATE["error"] = None
    
    # Run in background
    background_tasks.add_task(
        run_refinement_background,
        rough_prompt=request.rough_prompt,
        max_iterations=request.max_iterations,
        context=request.context,
        model=request.model,
        domain=request.domain
    )
    
    return {"message": "Refinement started", "status": "running"}


@app.get("/api/refine/status")
async def get_refinement_status():
    """Get the current status of the running refinement task."""
    return {
        "running": REFINEMENT_STATE["running"],
        "result": REFINEMENT_STATE["result"],
        "error": REFINEMENT_STATE["error"]
    }


@app.get("/api/prompts", response_model=List[PromptInfo])
async def get_all_prompts():
    """Get all prompts."""
    engine = init_db(DB_PATH)
    prompt_repo = PromptRepository(engine)
    
    prompts = prompt_repo.get_all()
    return [
        PromptInfo(
            id=prompt.id,
            content=prompt.content,
            is_baseline=prompt.is_baseline,
            created_at=prompt.created_at.isoformat(),
            accuracy=None,
            evaluations_count=0
        )
        for prompt in prompts
    ]


@app.post("/api/test")
async def test_prompt(request: TestPromptRequest):
    """Test a prompt with custom user input using Mistral."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="MISTRAL_API_KEY not configured")
    
    from mistralai import Mistral
    client = Mistral(api_key=api_key)
    
    full_prompt = f"{request.prompt_content}\n\nInput: {request.user_input}\n\nOutput:"
    
    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": full_prompt}]
        )
        
        return {
            "input": request.user_input,
            "output": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/prompts")
async def clear_all_prompts():
    """Clear all prompts from the database."""
    db_file = Path("prompt_store.db")
    if db_file.exists():
        db_file.unlink()
    return {"message": "Database cleared"}


# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
