"""
LeetCode Fetcher — Synchronous GraphQL client for problem data and user submissions.

Fetches:
1. Problem metadata (description, difficulty, tags, constraints, hints)
2. User's latest accepted submission code (requires LEETCODE_SESSION cookie)

This is the legal data source for the video pipeline — the user's own
accepted solution becomes the animation base.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://leetcode.com/graphql"

# ── Data Classes ──────────────────────────────────────────────────────

@dataclass
class LeetCodeProblem:
    """Complete problem payload with user's accepted solution."""

    slug: str
    title: str
    frontend_id: str
    difficulty: str
    description_html: str
    tags: list[str]
    hints: list[str]
    constraints: list[str]
    examples: list[str]
    code_snippets: dict[str, str]

    # User's accepted solution (the legal content base)
    accepted_code: Optional[str] = None
    accepted_lang: Optional[str] = None
    accepted_runtime: Optional[str] = None
    accepted_memory: Optional[str] = None
    submission_id: Optional[int] = None
    submission_timestamp: Optional[str] = None
    
    # User's published solution post (if provided)
    solution_title: Optional[str] = None
    solution_content: Optional[str] = None


# ── GraphQL Queries ───────────────────────────────────────────────────

_QUESTION_DATA_QUERY = """
query questionData($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        questionId
        questionFrontendId
        title
        titleSlug
        content
        isPaidOnly
        difficulty
        topicTags { name }
        hints
        codeSnippets { lang langSlug code }
        exampleTestcaseList
    }
}
"""

_SUBMISSION_LIST_QUERY = """
query questionSubmissionList($questionSlug: String!, $offset: Int!, $limit: Int!, $status: Int) {
    questionSubmissionList(
        questionSlug: $questionSlug
        offset: $offset
        limit: $limit
        status: $status
    ) {
        submissions {
            id
            statusDisplay
            lang
            runtime
            memory
            timestamp
        }
    }
}
"""

_SUBMISSION_DETAIL_QUERY = """
query submissionDetails($submissionId: Int!) {
    submissionDetails(submissionId: $submissionId) {
        code
        lang { name }
        statusDisplay
        runtime
        memory
        timestamp
    }
}
"""

_SOLUTION_ARTICLE_QUERY = """
query solutionArticle($topicId: Int!) {
    topic(id: $topicId) {
        id
        title
        post {
            content
        }
    }
}
"""


# ── Fetcher Class ─────────────────────────────────────────────────────

class LeetCodeFetcher:
    """Synchronous LeetCode GraphQL client.

    Uses only stdlib (``urllib``) to avoid adding dependencies.
    Requires ``LEETCODE_SESSION`` cookie for fetching user submissions.
    """

    def __init__(
        self,
        session_cookie: Optional[str] = None,
        csrf_token: Optional[str] = None,
        graphql_url: str = GRAPHQL_URL,
        rate_limit_seconds: float = 2.0,
    ) -> None:
        """
        Args:
            session_cookie: LEETCODE_SESSION cookie value.
            csrf_token: csrftoken cookie value (optional, derived from session if absent).
            graphql_url: LeetCode GraphQL endpoint URL.
            rate_limit_seconds: Minimum delay between API calls.
        """
        self._session_cookie = session_cookie or os.getenv("LEETCODE_SESSION", "")
        self._csrf_token = csrf_token or os.getenv("LEETCODE_CSRF", "")
        self._graphql_url = graphql_url
        self._rate_limit = rate_limit_seconds
        self._last_request_time: float = 0.0

    # ── Public API ────────────────────────────────────────────────────

    def fetch_problem(self, slug: str, solution_id: Optional[int] = None) -> LeetCodeProblem:
        """Fetch complete problem data + user's accepted solution.

        Args:
            slug: LeetCode problem slug (e.g. 'two-sum').
            solution_id: Optional ID of a published solution post.

        Returns:
            LeetCodeProblem with all fields populated.

        Raises:
            LeetCodeFetchError: On network/API failures.
        """
        logger.info("Fetching problem metadata from LeetCode", extra={"slug": slug})
        problem = self._fetch_problem_metadata(slug)

        if solution_id:
            logger.info("Fetching user's published solution post", extra={"solution_id": solution_id})
            self._attach_solution_post(problem, solution_id)
        elif self._session_cookie:
            logger.info("Fetching user's accepted submission", extra={"slug": slug})
            self._attach_accepted_submission(problem)
        else:
            logger.warning(
                "No LEETCODE_SESSION cookie and no solution_id — skipping submission fetch. "
                "Only problem metadata will be available.",
                extra={"slug": slug},
            )

        return problem

    # ── Problem Metadata ──────────────────────────────────────────────

    def _fetch_problem_metadata(self, slug: str) -> LeetCodeProblem:
        """Fetch problem description, tags, hints, constraints."""
        data = self._graphql_request(
            _QUESTION_DATA_QUERY,
            {"titleSlug": slug},
        )

        question = data.get("data", {}).get("question")
        if not question:
            raise LeetCodeFetchError(f"Problem '{slug}' not found on LeetCode.")

        # Parse constraints from HTML content
        content = question.get("content", "") or ""
        constraints = self._extract_constraints(content)

        # Parse code snippets into {lang: code} map
        snippets: dict[str, str] = {}
        for snip in question.get("codeSnippets", []) or []:
            snippets[snip.get("langSlug", "unknown")] = snip.get("code", "")

        return LeetCodeProblem(
            slug=slug,
            title=question.get("title", slug),
            frontend_id=question.get("questionFrontendId", ""),
            difficulty=question.get("difficulty", "Medium"),
            description_html=content,
            tags=[t.get("name", "") for t in question.get("topicTags", [])],
            hints=question.get("hints", []) or [],
            constraints=constraints,
            examples=question.get("exampleTestcaseList", []) or [],
            code_snippets=snippets,
        )

    # ── User Submissions & Solutions ──────────────────────────────────

    def _attach_solution_post(self, problem: LeetCodeProblem, topic_id: int) -> None:
        """Fetch a specific published solution post and attach its content."""
        try:
            data = self._graphql_request(
                _SOLUTION_ARTICLE_QUERY,
                {"topicId": topic_id},
            )
            
            topic = data.get("data", {}).get("topic")
            if not topic:
                logger.warning("Published solution topic ID %s not found.", topic_id)
                return

            problem.solution_title = topic.get("title", "")
            post_content = topic.get("post", {}).get("content", "")
            problem.solution_content = post_content
            
            # Use the post content as the accepted_code for generation purposes
            problem.accepted_code = f"# {problem.solution_title}\n\n{post_content}"
            problem.accepted_lang = "markdown" # Since it's a markdown post
            problem.submission_id = topic_id
            
            logger.info("✓ Attached published solution post '%s'", problem.solution_title)
            
        except LeetCodeFetchError as exc:
            logger.error("Failed to fetch published solution post: %s", exc)
        except Exception as exc:
            logger.error("Unexpected error fetching solution post: %s", exc)

    def _attach_accepted_submission(self, problem: LeetCodeProblem) -> None:
        """Find latest accepted submission and fetch its code."""
        try:
            # Step 1: List accepted submissions (status=10 means Accepted)
            data = self._graphql_request(
                _SUBMISSION_LIST_QUERY,
                {
                    "questionSlug": problem.slug,
                    "offset": 0,
                    "limit": 5,
                    "status": 10,
                },
            )

            submissions = (
                data.get("data", {})
                .get("questionSubmissionList", {})
                .get("submissions", [])
            )

            if not submissions:
                logger.warning(
                    "No accepted submissions found for '%s'. "
                    "Using starter code template as fallback.",
                    problem.slug,
                )
                return

            # Pick the latest accepted submission
            latest = submissions[0]
            submission_id = int(latest.get("id", 0))

            logger.info(
                "Found accepted submission",
                extra={
                    "slug": problem.slug,
                    "submission_id": submission_id,
                    "lang": latest.get("lang"),
                    "runtime": latest.get("runtime"),
                },
            )

            # Step 2: Fetch the actual code
            detail_data = self._graphql_request(
                _SUBMISSION_DETAIL_QUERY,
                {"submissionId": submission_id},
            )

            details = detail_data.get("data", {}).get("submissionDetails", {})
            if not details:
                logger.warning("Could not fetch submission details for ID %s", submission_id)
                return

            problem.accepted_code = details.get("code", "")
            lang_info = details.get("lang", {})
            problem.accepted_lang = (
                lang_info.get("name", latest.get("lang", ""))
                if isinstance(lang_info, dict)
                else str(lang_info)
            )
            problem.accepted_runtime = details.get("runtime", latest.get("runtime", ""))
            problem.accepted_memory = details.get("memory", latest.get("memory", ""))
            problem.submission_id = submission_id
            problem.submission_timestamp = details.get("timestamp", latest.get("timestamp", ""))

            logger.info(
                "✓ Attached user's accepted solution (%s, %s)",
                problem.accepted_lang,
                problem.accepted_runtime,
            )

        except LeetCodeFetchError as exc:
            logger.error(
                "Failed to fetch submissions (auth may have expired): %s", exc,
            )
        except Exception as exc:
            logger.error("Unexpected error fetching submissions: %s", exc)

    # ── HTTP / GraphQL ────────────────────────────────────────────────

    def _graphql_request(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a GraphQL POST request with rate limiting.

        Args:
            query: GraphQL query string.
            variables: Query variables dict.

        Returns:
            Parsed JSON response dict.

        Raises:
            LeetCodeFetchError: On HTTP or parsing errors.
        """
        self._apply_rate_limit()

        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        # Auth headers
        cookie_parts = []
        if self._session_cookie:
            cookie_parts.append(f"LEETCODE_SESSION={self._session_cookie}")
        if self._csrf_token:
            cookie_parts.append(f"csrftoken={self._csrf_token}")
            headers["x-csrftoken"] = self._csrf_token

        if cookie_parts:
            headers["Cookie"] = "; ".join(cookie_parts)

        req = urllib.request.Request(
            self._graphql_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise LeetCodeFetchError(
                    f"Rate limited by LeetCode (HTTP 429). Wait and retry."
                ) from exc
            if exc.code in (401, 403):
                raise LeetCodeFetchError(
                    f"Authentication failed (HTTP {exc.code}). "
                    f"Your LEETCODE_SESSION cookie may have expired."
                ) from exc
            raise LeetCodeFetchError(
                f"LeetCode API error (HTTP {exc.code}): {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LeetCodeFetchError(f"Network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise LeetCodeFetchError(f"Invalid JSON response: {exc}") from exc

    def _apply_rate_limit(self) -> None:
        """Enforce minimum delay between requests to avoid bans."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request_time = time.monotonic()

    # ── Parsing Helpers ───────────────────────────────────────────────

    @staticmethod
    def _extract_constraints(html_content: str) -> list[str]:
        """Extract constraint bullet points from LeetCode HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # LeetCode wraps constraints in <li> tags inside a section
            constraints: list[str] = []
            for li in soup.find_all("li"):
                text = li.get_text(strip=True)
                # Heuristic: constraints typically contain ≤, <=, 10^, etc.
                if any(c in text for c in ["<=", "≤", "10^", "10**", "length", "0 <"]):
                    constraints.append(text)

            return constraints if constraints else ["See problem description"]
        except Exception:
            return ["See problem description"]


# ── Exceptions ────────────────────────────────────────────────────────

class LeetCodeFetchError(Exception):
    """Raised when a LeetCode API request fails."""

    pass
