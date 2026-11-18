"""How the terminal chat looks: the reply as markdown, notes dimmed, errors in red (polish-terminal-chat D-1).

The text of a reply is handed to the renderer as it is: nothing here looks inside it. Square brackets are never read
as markup (a citation such as [K1] or an error text must come out as written). When the output is not a terminal,
``rich`` writes plain text with no escape sequences.
"""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown


class RichPrinter:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def line(self, text: str) -> None:
        self.console.print(text, markup=False, highlight=False)

    def reply(self, text: str) -> None:
        self.console.print("assistant>", style="bold cyan", markup=False)
        self.console.print(Markdown(text))

    def note(self, text: str) -> None:
        self.console.print(text, style="dim", markup=False, highlight=False)

    def error(self, text: str) -> None:
        self.console.print(text, style="red", markup=False, highlight=False)
