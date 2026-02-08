"""
Prompt Store - SQLite-based persistence for prompts.

Database initialization, models, and repository.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import Engine


class Prompt(SQLModel, table=True):
    """
    Prompt entity representing a single version of a prompt.

    Attributes:
        id: Unique identifier.
        content: The prompt text.
        metadata_json: JSON string storing additional metadata.
        created_at: Timestamp of creation.
        parent_id: ID of the parent prompt (if any).
        is_baseline: Whether this is the original user input.
        score: Evaluation score (0-10).
        critique: Critique from the evaluator.
        model_name: Name of the model that generated this prompt.
        domain: Domain of the prompt (e.g., 'general', 'code').
    """
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Content
    content: str = Field(index=True)
    
    # Metadata
    metadata_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Lineage
    parent_id: Optional[int] = Field(default=None, foreign_key="prompt.id")
    is_baseline: bool = Field(default=False)

    # Evaluation & Origin
    score: Optional[float] = Field(default=None)
    critique: Optional[str] = Field(default=None)
    model_name: Optional[str] = Field(default=None)
    domain: Optional[str] = Field(default="general")
    
    @property
    def prompt_metadata(self) -> Dict[str, Any]:
        """Parse stored JSON metadata"""
        try:
            return json.loads(self.metadata_json)
        except json.JSONDecodeError:
            return {}
    
    def set_prompt_metadata(self, data: Dict[str, Any]) -> None:
        """Store dictionary as JSON"""
        self.metadata_json = json.dumps(data)


def init_db(database_url: str = "sqlite:///prompt_store.db") -> Engine:
    """
    Initialize the database and create tables.

    Args:
        database_url: The database connection URL.

    Returns:
        The Engine.
    """
    engine = create_engine(database_url, echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


class PromptRepository:
    """
    Managing Prompt entities.
    """
    
    def __init__(self, engine: Engine):
        """
        Initialize the repository.

        Args:
           The database engine.
        """
        self.engine = engine
    
    def create(self, content: str, 
               metadata: Optional[Dict[str, Any]] = None, 
               parent_id: Optional[int] = None, 
               is_baseline: bool = False,
               score: Optional[float] = None, 
               critique: Optional[str] = None,
               model_name: Optional[str] = None, 
               domain: Optional[str] = "general") -> Prompt:
        """
        Create and persist new prompts.

        Args:
            content: Prompt text.
            metadata: Optional metadata dictionary.
            parent_id: Optional ID of the parent prompt.
            is_baseline: Whether this is a baseline prompt.
            score: Evaluation score.
            critique: Evaluation critique.
            model_name: Model that generated this prompt.
            domain: Domain of the prompt.

        Returns:
            The created Prompts instance.
        """
        prompt = Prompt(
            content=content,
            parent_id=parent_id,
            is_baseline=is_baseline,
            score=score,
            critique=critique,
            model_name=model_name,
            domain=domain
        )
        if metadata:
            prompt.set_prompt_metadata(metadata)
        
        with Session(self.engine) as session:
            session.add(prompt)
            session.commit()
            session.refresh(prompt)
            return prompt
    
    def get_by_id(self, prompt_id: int) -> Optional[Prompt]:
        """Retrieve a prompt by its ID."""
        with Session(self.engine) as session:
            return session.get(Prompt, prompt_id)
    
    def get_all(self) -> List[Prompt]:
        """Retrieve all prompts, ordered by creation time (most recent first)."""
        with Session(self.engine) as session:
            statement = select(Prompt).order_by(Prompt.created_at.desc())
            return list(session.exec(statement))
    
    def get_baseline(self) -> Optional[Prompt]:
        """Retrieve the baseline prompt."""
        with Session(self.engine) as session:
            statement = select(Prompt).where(Prompt.is_baseline == True)
            return session.exec(statement).first()
    
    def get_children(self, parent_id: int) -> List[Prompt]:
        """Retrieve all prompts that are children of the given parent ID."""
        with Session(self.engine) as session:
            statement = select(Prompt).where(Prompt.parent_id == parent_id)
            return list(session.exec(statement))
    
    def update(self, prompt: Prompt) -> Prompt:
        """Update an existing prompt in the database."""
        with Session(self.engine) as session:
            session.add(prompt)
            session.commit()
            session.refresh(prompt)
            return prompt
    
    def delete(self, prompt_id: int) -> bool:
        """Delete a prompt by ID"""
        with Session(self.engine) as session:
            prompt = session.get(Prompt, prompt_id)
            if prompt:
                session.delete(prompt)
                session.commit()
                return True
            return False
