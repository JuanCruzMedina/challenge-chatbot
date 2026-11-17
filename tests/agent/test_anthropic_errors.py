"""Spec: Anthropic failures and the spending cap reach the person as AgentModelError that says what to do."""
from __future__ import annotations

import anthropic
import httpx2
import pytest

from ecosystem_assistant.agent.settings import AgentModelError
from ecosystem_assistant.llm.ledger import BudgetExceededError
from tests.agent.fake_chat import ScriptedChat
from tests.agent.test_model_errors import one_turn


def api_error(cls: type, status: int) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize(("error", "advice"), [
    (api_error(anthropic.AuthenticationError, 401), "ant auth login"),
    (api_error(anthropic.RateLimitError, 429), "wait"),
    (api_error(anthropic.InternalServerError, 529), "overloaded"),
    (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "connection"),
])
def test_a_service_failure_becomes_an_agent_model_error_with_advice(
    error: Exception, advice: str, workspace_dir, audit_file, tmp_path
) -> None:
    with pytest.raises(AgentModelError) as exc:
        one_turn(ScriptedChat(script=[error]), workspace_dir, audit_file, tmp_path)
    assert advice in str(exc.value).lower()


def test_the_spending_cap_becomes_an_agent_model_error_that_names_the_cap(workspace_dir, audit_file, tmp_path) -> None:
    error = BudgetExceededError("The Anthropic spending cap is reached: $1 of $1. Raise it with ANTHROPIC_MAX_USD.")

    with pytest.raises(AgentModelError, match="ANTHROPIC_MAX_USD"):
        one_turn(ScriptedChat(script=[error]), workspace_dir, audit_file, tmp_path)


def test_a_bad_request_is_a_bug_and_is_not_disguised(workspace_dir, audit_file, tmp_path) -> None:
    with pytest.raises(anthropic.BadRequestError):
        one_turn(ScriptedChat(script=[api_error(anthropic.BadRequestError, 400)]), workspace_dir, audit_file, tmp_path)
