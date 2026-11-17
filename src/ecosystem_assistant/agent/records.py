"""What a turn returns: the reply and a record of every tool call (design.md D-8)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str
    error: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentReply:
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    messages: list[BaseMessage] = field(default_factory=list)  # the new messages of the turn, to append to a history

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "tool_calls": [c.to_dict() for c in self.tool_calls]}


def message_text(message: BaseMessage) -> str:
    """The text of a message whose content is a string or a list of content blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(block if isinstance(block, str) else str(block.get("text", "")) for block in content)


def records_from_messages(new_messages: Sequence[BaseMessage]) -> list[ToolCallRecord]:
    """Pair every tool call the model asked for with the tool message that answered it, in order."""
    results = {m.tool_call_id: m for m in new_messages if isinstance(m, ToolMessage)}
    records: list[ToolCallRecord] = []
    for message in new_messages:
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            answer = results.get(call["id"])
            records.append(ToolCallRecord(
                name=call["name"],
                arguments=dict(call["args"]),
                result=message_text(answer) if answer is not None else "",
                error=answer is not None and answer.status == "error",
            ))
    return records
