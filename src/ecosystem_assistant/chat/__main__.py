"""Entry point: ``uv run python -m ecosystem_assistant.chat`` (design.md D-2).

Starts the agent (and with it the MCP server) on the workspace, runs the terminal loop, and stops everything on exit.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.chat.terminal import run_chat


def main(
    argv: list[str] | None = None,
    agent_factory: Callable[[Path | None], Any] = lambda workspace: Agent.open(workspace=workspace),
    read: Callable[[str], str] = input,
    write: Callable[[str], Any] = print,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecosystem_assistant.chat", description=__doc__)
    parser.add_argument("--workspace", type=Path, default=None,
                        help="the workspace to read and write (default: AGENT_DATA_ROOT or var/workspace)")
    args = parser.parse_args(argv)

    async def session() -> None:
        async with agent_factory(args.workspace) as agent:
            await run_chat(agent, read, write)

    try:
        asyncio.run(session())
    except FileNotFoundError as error:  # the workspace is missing; the message says how to create it
        write(str(error))
        return 2
    except KeyboardInterrupt:
        write("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
