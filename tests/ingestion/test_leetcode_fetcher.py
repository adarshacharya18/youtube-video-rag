"""
Tests for LeetCode Fetcher and IngestionNode LeetCode integration.

Tests the GraphQL client, submission fetching, and IngestionNode
wiring with both live and mock scenarios.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch

from src.core.ingestion.leetcode_fetcher import (
    LeetCodeFetcher,
    LeetCodeFetchError,
    LeetCodeProblem,
)



# ── LeetCodeFetcher Unit Tests ────────────────────────────────────────


class TestLeetCodeFetcher:
    """Unit tests for LeetCodeFetcher with mocked HTTP responses."""

    @patch("src.core.ingestion.leetcode_fetcher.urllib.request.urlopen")
    def test_fetch_problem_metadata(self, mock_urlopen):
        """Verify problem metadata is parsed correctly from GraphQL response."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "question": {
                    "questionId": "1",
                    "questionFrontendId": "1",
                    "title": "Two Sum",
                    "titleSlug": "two-sum",
                    "content": "<p>Given an array...</p><li>2 <= nums.length <= 10^4</li>",
                    "isPaidOnly": False,
                    "difficulty": "Easy",
                    "topicTags": [{"name": "Array"}, {"name": "Hash Table"}],
                    "hints": ["Try using a hash map."],
                    "codeSnippets": [
                        {"lang": "Python3", "langSlug": "python3", "code": "class Solution:..."},
                        {"lang": "C++", "langSlug": "cpp", "code": "class Solution {...};"},
                    ],
                    "exampleTestcaseList": ["[2,7,11,15]\n9"],
                }
            }
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher = LeetCodeFetcher(session_cookie="", rate_limit_seconds=0)
        problem = fetcher._fetch_problem_metadata("two-sum")

        assert problem.title == "Two Sum"
        assert problem.difficulty == "Easy"
        assert problem.frontend_id == "1"
        assert "Array" in problem.tags
        assert "Hash Table" in problem.tags
        assert len(problem.code_snippets) == 2
        assert "python3" in problem.code_snippets

    @patch("src.core.ingestion.leetcode_fetcher.urllib.request.urlopen")
    def test_fetch_problem_not_found_raises(self, mock_urlopen):
        """Verify error when problem slug doesn't exist."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {"question": None}
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        fetcher = LeetCodeFetcher(session_cookie="", rate_limit_seconds=0)

        with pytest.raises(LeetCodeFetchError, match="not found"):
            fetcher._fetch_problem_metadata("nonexistent-problem")

    @patch("src.core.ingestion.leetcode_fetcher.urllib.request.urlopen")
    def test_attach_accepted_submission(self, mock_urlopen):
        """Verify accepted submission code is attached to the problem."""
        # Two sequential API calls: submission list, then submission details
        responses = [
            # Call 1: submission list
            json.dumps({
                "data": {
                    "questionSubmissionList": {
                        "submissions": [
                            {
                                "id": "12345",
                                "statusDisplay": "Accepted",
                                "lang": "python3",
                                "runtime": "40 ms",
                                "memory": "14.5 MB",
                                "timestamp": "1700000000",
                            }
                        ]
                    }
                }
            }).encode("utf-8"),
            # Call 2: submission details
            json.dumps({
                "data": {
                    "submissionDetails": {
                        "code": "class Solution:\n    def twoSum(self, nums, target):\n        seen = {}\n        for i, n in enumerate(nums):\n            if target - n in seen:\n                return [seen[target - n], i]\n            seen[n] = i",
                        "lang": {"name": "Python3"},
                        "statusDisplay": "Accepted",
                        "runtime": "40 ms",
                        "memory": "14.5 MB",
                        "timestamp": "1700000000",
                    }
                }
            }).encode("utf-8"),
        ]

        call_count = [0]
        def side_effect(*args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.read.return_value = responses[call_count[0]]
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            call_count[0] += 1
            return mock_resp

        mock_urlopen.side_effect = side_effect

        problem = LeetCodeProblem(
            slug="two-sum",
            title="Two Sum",
            frontend_id="1",
            difficulty="Easy",
            description_html="<p>Given an array...</p>",
            tags=["Array"],
            hints=[],
            constraints=["2 <= nums.length <= 10^4"],
            examples=[],
            code_snippets={},
        )

        fetcher = LeetCodeFetcher(session_cookie="test_cookie", rate_limit_seconds=0)
        fetcher._attach_accepted_submission(problem)

        assert problem.accepted_code is not None
        assert "twoSum" in problem.accepted_code
        assert problem.accepted_lang == "Python3"
        assert problem.accepted_runtime == "40 ms"
        assert problem.submission_id == 12345

    @patch("src.core.ingestion.leetcode_fetcher.urllib.request.urlopen")
    def test_no_accepted_submissions_graceful(self, mock_urlopen):
        """Verify graceful handling when user has no accepted submissions."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "questionSubmissionList": {
                    "submissions": []
                }
            }
        }).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        problem = LeetCodeProblem(
            slug="hard-problem",
            title="Hard Problem",
            frontend_id="999",
            difficulty="Hard",
            description_html="",
            tags=[],
            hints=[],
            constraints=[],
            examples=[],
            code_snippets={},
        )

        fetcher = LeetCodeFetcher(session_cookie="test_cookie", rate_limit_seconds=0)
        fetcher._attach_accepted_submission(problem)

        # Should not crash, code stays None
        assert problem.accepted_code is None


# ── IngestionNode Integration Tests ───────────────────────────────────


@pytest.fixture
def IngestionNode():
    """Lazy import to avoid circular import at collection time."""
    from src.pipeline.nodes.ingestion_node import IngestionNode as _Node
    return _Node


class TestIngestionNodeLeetCode:
    """Tests for IngestionNode's LeetCode integration."""

    def _make_mock_ledger(self, slug: str, metadata: dict = None):
        """Create a mock StateLedger with a run record."""
        mock_ledger = MagicMock()
        mock_run = MagicMock()
        mock_run.slug = slug
        mock_run.metadata = metadata or {}
        mock_ledger.get_run.return_value = mock_run
        return mock_ledger

    def test_leetcode_data_used_when_available(self, IngestionNode):
        """Verify LeetCode data is the primary source when fetch succeeds."""
        with patch.object(IngestionNode, "_fetch_from_leetcode") as mock_fetch:
            mock_fetch.return_value = {
                "title": "Two Sum",
                "frontend_id": "1",
                "difficulty": "Easy",
                "description_html": "<p>Given an array of integers...</p>",
                "tags": ["Array", "Hash Table"],
                "hints": ["Use a hash map"],
                "constraints": ["2 <= nums.length <= 10^4"],
                "examples": ["[2,7,11,15]\n9"],
                "code_snippets": {"python3": "class Solution:..."},
                "accepted_code": "def twoSum(self, nums, target): ...",
                "accepted_lang": "Python3",
                "accepted_runtime": "40 ms",
                "accepted_memory": "14.5 MB",
                "submission_id": 12345,
            }

            node = IngestionNode(session_cookie="test")
            ledger = self._make_mock_ledger("two-sum")

            result = node.execute("run_001", ledger)

            assert result["title"] == "Two Sum"
            assert result["code"] == "def twoSum(self, nums, target): ..."
            assert result["code_language"] == "Python3"
            assert result["data_source"] == "leetcode_api"
            assert result["submission_id"] == 12345

    def test_fallback_when_leetcode_fails(self, IngestionNode):
        """Verify graceful fallback when LeetCode is unreachable."""
        with patch.object(IngestionNode, "_fetch_from_leetcode", return_value=None):
            node = IngestionNode(session_cookie="")
            ledger = self._make_mock_ledger("two-sum", {"title": "Two Sum", "difficulty": "Easy"})

            result = node.execute("run_001", ledger)

            assert result["title"] == "Two Sum"
            assert result["data_source"] == "fallback"
            assert result["status"] == "completed"

    def test_metadata_overrides_leetcode_when_explicit(self, IngestionNode):
        """Verify that user-provided metadata overrides LeetCode defaults."""
        with patch.object(IngestionNode, "_fetch_from_leetcode") as mock_fetch:
            mock_fetch.return_value = {
                "title": "Two Sum",
                "frontend_id": "1",
                "difficulty": "Easy",
                "description_html": "",
                "tags": [],
                "hints": [],
                "constraints": [],
                "examples": [],
                "code_snippets": {},
                "accepted_code": "some code",
                "accepted_lang": "Python3",
                "accepted_runtime": "",
                "accepted_memory": "",
                "submission_id": None,
            }

            node = IngestionNode(session_cookie="test")
            ledger = self._make_mock_ledger(
                "two-sum",
                {"title": "My Custom Title", "difficulty": "Hard"},
            )

            result = node.execute("run_001", ledger)

            # User metadata should override LeetCode defaults
            assert result["title"] == "My Custom Title"
            assert result["difficulty"] == "Hard"
            # But accepted code still comes from LeetCode
            assert result["code"] == "some code"

