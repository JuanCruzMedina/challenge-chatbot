"""Re-export of the scripted chat model, which lives in the package so documentation can use it too."""
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool, ai_tools

__all__ = ["ScriptedChat", "ai_text", "ai_tool", "ai_tools"]
