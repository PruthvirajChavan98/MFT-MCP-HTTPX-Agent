from src.agent_service.core.prompts import PromptManager


def test_prompts_yaml_is_valid() -> None:
    manager = PromptManager()
    manager.load()
    assert manager.get_template("agent", "system_prompt")
