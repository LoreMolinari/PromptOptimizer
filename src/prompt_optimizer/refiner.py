"""
Prompt Refiner Module.

Refine rough prompts using an LLM (Mistral) through a branching and self-evaluation strategy.
"""

import os
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from mistralai import Mistral


@dataclass
class RefinementResult:
    """Result of a single refinement step."""
    iteration: int
    original_prompt: str
    refined_prompt: str
    improvements: List[str]
    tokens_used: int = 0


@dataclass
class RefinementOutput:
    """Final output"""
    original_prompt: str
    final_prompt: str
    iterations: int
    all_versions: List[Dict[str, Any]]
    total_tokens: int


class PromptRefiner:
    """
    Refines prompts using LLM guidance with branching and self-evaluation.
    """

    def __init__(self, model: str = "mistral-small-latest", 
                 api_key: Optional[str] = None):
        """
        Initialize the PromptRefiner.

        Args:
            model: Mistral model to use.
            api_key: Optional API key.
        """
        self.model = model
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self._client: Optional[Mistral] = None

    @property
    def client(self) -> Mistral:
        """Initialize Mistral client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("MISTRAL_API_KEY is not set.")
            self._client = Mistral(api_key=self.api_key)
        return self._client

    def _build_refinement_prompt(self, rough_prompt: str, 
                                  context: Optional[str] = None) -> str:
        """Build the prompt for asking the LLM to refine."""
        context_section = f"\nCONTEXT: {context}" if context else ""
        
        return f"""You are an expert prompt engineer. Your task is to improve and refine a prompt to make it more effective.

ORIGINAL PROMPT:
"{rough_prompt}"
Context: {context_section}

Improve this prompt by making it:
1. More specific and clear about what output is expected
2. Better structured with clear instructions
3. More effective at getting the desired response from an AI

CRITICAL: Output ONLY the improved prompt text. No explanations, no emojis, no markdown, no "Here is the improved version:", just the raw improved prompt.
"""

    def _build_iterative_refinement_prompt(self, current_prompt: str,
                                           original_prompt: str,
                                           iteration: int) -> str:
        """Build prompt for iterative refinement."""
        return f"""You are an expert prompt engineer doing iteration {iteration} of prompt refinement.

ORIGINAL (rough) prompt: "{original_prompt}"

CURRENT prompt after {iteration-1} refinements: "{current_prompt}"

Further improve this prompt. Focus on:
- Adding more specific guidance
- Improving clarity
- Adding edge case handling
- Better formatting instructions

CRITICAL: Output ONLY the improved prompt text. No explanations, no emojis, no markdown, no "Here is the improved version:", just the raw improved prompt.
"""

    def _evaluate_prompt(self, prompt: str, original_task: str) -> Tuple[float, str]:
        """
        Evaluate a prompt on a scale of 0-10 using Mistral Large as the judge.

        Returns:
            Tuple containing (score, critique).
        """
        eval_prompt = f"""Rate this prompt on a scale of 0 to 10 based on clarity, specificity, and robustness.
Be EXTREMELY CRITICAL. Most "good" prompts should only score a 6 or 7.
Deduct points for:
- Vague terms (e.g., "briefly", "expertly") (-1 point)
- Lack of specific output format (-2 points)
- Missing constraints on length or tone (-1 point)
- No edge case handling (-1 point)

Only score above 9 if the prompt is PERFECT, includes rigorous constraints, and handles all possible ambiguities.

Task Description: "{original_task}"

Prompt Candidate:
"{prompt}"

Output specific JSON format:
{{
  "score": <float 0-10>,
  "critique": "<short critique explanation>"
}}
"""
        try:
            # Use mistral-large for judging
            response = self.client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": eval_prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if not content:
                 return 0.0, "Empty response from evaluator"

            data = json.loads(content)
            return float(data.get("score", 0)), data.get("critique", "No critique provided")
        except Exception as e:
            print(f"Evaluation failed: {e}")
            return 0.0, f"Evaluation failed: {e}"

    def _clean_response(self, text: str) -> str:
        """Clean up LLM response to extract just the prompt."""
        if not text:
            return ""
            
        cleaned = text.strip()
        
        # Remove common prefixes
        prefixes = [
            "IMPROVED PROMPT:",
            "Improved Prompt:",
            "Here is the improved prompt:",
            "Here's the improved version:",
        ]
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        # Remove surrounding quotes if present and they wrap the entire string
        if len(cleaned) >= 2:
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1]
            elif cleaned.startswith("'") and cleaned.endswith("'"):
                cleaned = cleaned[1:-1]
        
        return cleaned.strip()

    def refine(self, rough_prompt: str, 
               max_iterations: int = 3,
               alternatives_per_iteration: int = 3,
               context: Optional[str] = None,
               domain: str = "general") -> RefinementOutput:
        """
        Refine a prompt using a Multi-Model Arena strategy.
        Generates candidates from Small, Medium, and Large models (or Codestral if specified).
        """
        all_versions: List[Dict[str, Any]] = []
        
        # Initial State
        current_best_prompt = rough_prompt
        parent_idx = 0 
        total_tokens = 0
        
        # Add baseline to history
        all_versions.append({
            "content": rough_prompt,
            "iteration": 0,
            "score": 0.0,
            "critique": "Baseline",
            "parent_idx": None,
            "is_best": True,
            "model_name": "human",
            "domain": domain
        })

        # Define Arena Models based on Domain
        if domain == "code":
            # Code Arena: Compares specialized Codestral vs Smartest Generalist
            arena_models = [
                "codestral-latest", 
                "codestral-latest", 
                "mistral-large-latest"
            ]
        else:
            # General Arena
            arena_models = [
                "mistral-small-latest",
                "mistral-medium-latest",
                "mistral-large-latest"
            ]

        iterations_run = 0
        for iteration in range(1, max_iterations + 1):
            iterations_run = iteration
            candidates = []
            
            # 1. Generate Alternatives from different models
            for i, model_name in enumerate(arena_models):
                # Build prompt
                if iteration == 1:
                    system_prompt = self._build_refinement_prompt(rough_prompt, context)
                else:
                    system_prompt = self._build_iterative_refinement_prompt(
                        current_best_prompt, rough_prompt, iteration
                    )
                
                try:
                    # Call specific LLM in the arena
                    temperature = 0.7
                    if domain == "code" and model_name == "codestral-latest":
                         # Vary temperature: one strict, one creative
                         temperature = 0.2 if i == 0 else 0.8 

                    response = self.client.chat.complete(
                        model=model_name,
                        messages=[{"role": "user", "content": system_prompt}],
                        temperature=temperature 
                    )
                    
                    content = response.choices[0].message.content
                    if not content:
                        continue
                        
                    refined = self._clean_response(content)
                    
                    usage = response.usage
                    total_tokens += usage.total_tokens if usage else 0
                    
                    # 2. Evaluate using Mistral Large (Judge)
                    score, critique = self._evaluate_prompt(refined, rough_prompt)
                    
                    candidates.append({
                        "content": refined,
                        "iteration": iteration,
                        "score": score,
                        "critique": critique,
                        "parent_idx": parent_idx,
                        "is_best": False,
                        "model_name": model_name,
                        "domain": domain
                    })
                except Exception as e:
                    print(f"Generation for {model_name} failed: {e}")
            
            if not candidates:
                break

            # 3. Select Best
            best_candidate = max(candidates, key=lambda x: x["score"])
            best_candidate["is_best"] = True
            current_best_prompt = best_candidate["content"]
            
            # Add all candidates to history
            start_idx = len(all_versions)
            all_versions.extend(candidates)
            
            # Update parent_idx for next iteration (points to the best candidate)
            # Find the index of best_candidate in the newly extended all_versions
            # It should be start_idx + index within candidates
            best_idx_in_candidates = candidates.index(best_candidate)
            parent_idx = start_idx + best_idx_in_candidates
            
            # Stop early if score is near perfect
            if best_candidate["score"] >= 9.8:
                break
        
        return RefinementOutput(
            original_prompt=rough_prompt,
            final_prompt=current_best_prompt,
            iterations=iterations_run,
            all_versions=all_versions,
            total_tokens=total_tokens
        )
    
    def test_prompt(self, prompt: str, user_input: str) -> str:
        """Test a prompt with a user input."""
        full_prompt = f"{prompt}\n\n{user_input}"
        
        response = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": full_prompt}]
        )
        
        # Ensure content is not None before returning
        content = response.choices[0].message.content
        return content if content else ""
