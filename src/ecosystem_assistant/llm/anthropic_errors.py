"""What to tell a person when the Anthropic API fails, shared by the flow and the agent (design.md D-6)."""
from __future__ import annotations

import anthropic


def explain_anthropic_error(exc: BaseException, model: str) -> str | None:
    """A message that says what to do for failures of the service or the connection; ``None`` for anything else.

    Anything else (a bad request, a bug) is not translated: it must not be disguised as a service problem.
    """
    if isinstance(exc, anthropic.AuthenticationError):
        return ("Anthropic rejected the credentials (401). Log in with `ant auth login`, or set ANTHROPIC_API_KEY "
                "to a valid key.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return ("Anthropic denied permission (403). Check the account or workspace of the credentials: run "
                "`ant auth login` again, or set ANTHROPIC_API_KEY to a key with access.")
    if isinstance(exc, anthropic.RateLimitError):
        return "Anthropic's rate limit was reached. Wait a moment and try again."
    if isinstance(exc, anthropic.InternalServerError):
        status = getattr(exc, "status_code", "5xx")
        return f"Anthropic is overloaded or failing (HTTP {status}). Try again in a moment."
    if isinstance(exc, anthropic.NotFoundError):
        return f"Anthropic does not know the model {model!r}. Check ANTHROPIC_MODEL."
    if isinstance(exc, anthropic.APIConnectionError):  # includes timeouts
        return f"Cannot reach the Anthropic API ({exc}). Check your internet connection and try again."
    return None
