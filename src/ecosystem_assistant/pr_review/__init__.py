"""Documentation review of a merged pull request (openspec: pr-documentation-review).

The package gives a pull request to the agent and reports what happened. It decides nothing itself: whether
documentation exists, is missing or is out of date is the model's call, made with the agent's tools.
"""
from ecosystem_assistant.pr_review.pull_request import Change, PullRequest, PullRequestError, load_pull_request
from ecosystem_assistant.pr_review.review import ReviewReport, review_pull_request

__all__ = ["Change", "PullRequest", "PullRequestError", "ReviewReport", "load_pull_request", "review_pull_request"]
