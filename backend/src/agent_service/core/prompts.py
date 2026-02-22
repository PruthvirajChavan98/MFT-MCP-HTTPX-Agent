from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import yaml
from pydantic import BaseModel, ValidationError

log = logging.getLogger("prompt_manager")

# --- Pydantic Models for Schema Validation ---


class PromptDef(BaseModel):
    description: str
    template: str


class PromptsSchema(BaseModel):
    agent: Dict[str, PromptDef]
    eval: Dict[str, PromptDef]
    router: Dict[str, PromptDef]
    follow_up: Dict[str, PromptDef]
    knowledge: Dict[str, PromptDef]


# --- Prompt Manager Singleton ---


class PromptManager:
    def __init__(self):
        self._prompts: PromptsSchema | None = None
        self._yaml_path = Path(__file__).parent / "prompts.yaml"

    def load(self) -> None:
        """Loads and strictly validates the YAML prompt registry."""
        if not self._yaml_path.exists():
            raise FileNotFoundError(f"Prompt registry not found: {self._yaml_path}")

        with open(self._yaml_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        try:
            self._prompts = PromptsSchema.model_validate(raw_data)
            log.info(f"✅ Prompt registry loaded successfully from {self._yaml_path.name}")
        except ValidationError as e:
            log.critical(f"❌ Prompt registry validation failed:\n{e}")
            raise RuntimeError(f"Prompt registry validation failed: {e}") from e

    def get_template(self, category: str, prompt_name: str) -> str:
        """Retrieves a Jinja2 template string by category and name."""
        if self._prompts is None:
            raise RuntimeError("PromptManager not initialized. Call load() first.")

        cat_dict = getattr(self._prompts, category, None)
        if cat_dict is None:
            raise ValueError(f"Unknown prompt category: {category}")

        prompt_def = cat_dict.get(prompt_name)
        if prompt_def is None:
            raise ValueError(f"Prompt '{prompt_name}' not found in category '{category}'")

        return prompt_def.template

    def get_default_system_prompt(self) -> str:
        """Returns default system prompt text for session bootstrap."""
        return self.get_template("agent", "system_prompt").strip()


# Export a singleton instance
prompt_manager = PromptManager()
