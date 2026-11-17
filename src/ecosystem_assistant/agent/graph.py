"""The agent's loop as a LangGraph graph (design.md D-1, D-2).

APIs confirmed with a throwaway probe against the installed versions (task 1.2):
- ``chat.bind_tools([tool, ...])`` on a ``ChatOllama`` accepts tools whose ``args_schema`` is a JSON Schema
  dictionary and sends that schema as it is. The model's turn is an ``AIMessage`` whose ``tool_calls`` is a list of
  ``{"name", "args", "id", "type": "tool_call"}`` (``content`` is ``""``); a turn that needs no tool has an
  empty ``tool_calls`` and text in ``content``.
- ``langgraph.prebuilt.ToolNode(tools, handle_tool_errors=...)`` only works inside a graph (it needs the runtime
  config). It answers every call with a ``ToolMessage``: ``status="success"`` with the result, ``status="error"``
  with the message of a ``ToolException``, and ``status="error"`` for an unknown name with the text
  "Error: <name> is not a valid tool, try one of [<available>]."
- A ``ChatOllama`` whose server is down raises ``httpx.ConnectError`` (not the builtin ``ConnectionError``).

The graph has two nodes, ``model`` and ``tools``. The only branch is :func:`route`: did the model's last message ask
for tools? Nothing in this module looks at what the person wrote, and no tool is named here.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

MAX_TOOL_CALLS = 6
LIMIT_MESSAGE = (
    "I stopped because I reached the limit of six tool calls in one turn. "
    "Tell me how to continue, or ask again with a narrower request."
)


def tool_calls_used(messages: Sequence[BaseMessage]) -> int:
    """How many tool calls have already been answered in the current turn (since the last human message)."""
    used = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, ToolMessage):
            used += 1
    return used


def route(state: MessagesState) -> str:
    """The loop's one branch: run tools when the model asked for them, otherwise end the turn."""
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_agent_graph(
    chat: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: str,
    max_tool_calls: int = MAX_TOOL_CALLS,
    translate_error: Callable[[Exception], Exception] | None = None,
):
    """Compile the loop for this set of tools. The set can differ from one turn to the next."""
    bound = chat.bind_tools(list(tools))

    async def model(state: MessagesState) -> dict[str, Any]:
        try:
            reply = await bound.ainvoke([SystemMessage(system_prompt), *state["messages"]])
        except Exception as exc:  # noqa: BLE001 - re-raised, translated when the caller knows how
            if translate_error is not None:
                raise translate_error(exc) from exc
            raise
        # The cap lives here so that the loop keeps exactly two nodes and one branch: a request that would pass the
        # limit is replaced by a message that says so, and the turn ends because it asks for no tools.
        if reply.tool_calls and tool_calls_used(state["messages"]) + len(reply.tool_calls) > max_tool_calls:
            reply = AIMessage(content=LIMIT_MESSAGE)
        return {"messages": [reply]}

    builder = StateGraph(MessagesState)
    builder.add_node("model", model)
    # Failures of a tool reach the model as tool messages (the tools raise ToolException); anything else is a bug
    # or an unreachable model and must not be swallowed.
    builder.add_node("tools", ToolNode(list(tools), handle_tool_errors=False))
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route, {"tools": "tools", END: END})
    builder.add_edge("tools", "model")
    return builder.compile()
