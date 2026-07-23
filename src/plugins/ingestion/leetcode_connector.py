"""
LeetCode GraphQL Connector.

Extracts rich algorithmic problem data from LeetCode's official GraphQL API.
Inherits from BaseSourceConnector to utilize native Rate Limiting and Exponential Backoff.
"""

import json
from typing import Dict, List, Optional, Tuple

import aiohttp

from src.plugins.ingestion.connector_base import (
    AuthError,
    BaseSourceConnector,
    ConnectorError,
    PaginationToken,
    RateLimitError,
    RawContent,
)


class LeetCodeConnector(BaseSourceConnector):
    """
    Direct GraphQL bridge to LeetCode's backend servers.
    """
    GRAPHQL_URL = "https://leetcode.com/graphql"
    
    def __init__(self, rate_limit_ms: int = 2000) -> None:
        # Default to a highly polite 2-second delay to avoid LeetCode IP bans
        super().__init__(name="LeetCode", rate_limit_ms=rate_limit_ms)
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies: Dict[str, str] = {}
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazy initialization of the HTTP Client Session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json", 
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                cookies=self._cookies
            )
        return self._session

    async def authenticate(self, credentials: Dict[str, str]) -> None:
        """
        Injects session cookies to bypass paywalls for Premium 'Locked' questions.
        Requires `LEETCODE_SESSION` and `csrf_token`.
        """
        session_cookie = credentials.get("LEETCODE_SESSION")
        csrf_token = credentials.get("csrf_token")
        
        if session_cookie and csrf_token:
            self._cookies = {
                "LEETCODE_SESSION": session_cookie,
                "csrftoken": csrf_token
            }
            if self._session:
                self._session.cookie_jar.update_cookies(self._cookies) # type: ignore
            self._logger.info("LeetCode premium authentication cookies loaded.")

    async def _do_health_check(self) -> bool:
        """Pings the GraphQL server to ensure it is online."""
        query = """
        query {
            user {
                username
            }
        }
        """
        session = await self._get_session()
        async with session.post(self.GRAPHQL_URL, json={"query": query}) as resp:
            return resp.status == 200

    async def discover(self, query: str) -> List[str]:
        """
        Uses GraphQL `problemsetQuestionList` to search for problems by keyword.
        Example: discover("binary tree") -> ["binary-tree-inorder-traversal", ...]
        """
        gql_query = """
        query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
            problemsetQuestionList: questionList(
                categorySlug: $categorySlug
                limit: $limit
                skip: $skip
                filters: $filters
            ) {
                data {
                    titleSlug
                }
            }
        }
        """
        variables = {
            "categorySlug": "",
            "skip": 0,
            "limit": 10,
            "filters": {"searchKeywords": query}
        }
        
        session = await self._get_session()
        await self._apply_rate_limit() # Manually apply protection for direct queries
        
        async with session.post(self.GRAPHQL_URL, json={"query": gql_query, "variables": variables}) as resp:
            if resp.status == 429:
                raise RateLimitError("Rate limited during Discovery phase.")
            resp.raise_for_status()
            data = await resp.json()
            
            questions = data.get("data", {}).get("problemsetQuestionList", {}).get("data", [])
            return [q["titleSlug"] for q in questions if "titleSlug" in q]

    async def _do_fetch(self, uri: str) -> RawContent:
        """
        Fetches the complete algorithmic payload using the `titleSlug` URI.
        Called by the Base class `fetch()` wrapper, guaranteeing Retries and Limits.
        """
        # Accept either "two-sum" or "https://leetcode.com/problems/two-sum"
        title_slug = uri.strip("/").split("/")[-1] if "/" in uri else uri
        
        query = """
        query questionData($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                questionFrontendId
                title
                titleSlug
                content
                isPaidOnly
                difficulty
                topicTags {
                    name
                }
                hints
                codeSnippets {
                    lang
                    langSlug
                    code
                }
            }
        }
        """
        
        session = await self._get_session()
        async with session.post(self.GRAPHQL_URL, json={"query": query, "variables": {"titleSlug": title_slug}}) as resp:
            if resp.status == 429:
                raise RateLimitError(f"LeetCode HTTP 429 Rate Limit hit for slug: {title_slug}")
            if resp.status in (401, 403):
                raise AuthError(f"Premium required (or cookies expired) for {title_slug}.")
            resp.raise_for_status()
            
            json_data = await resp.json()
            question_data = json_data.get("data", {}).get("question")
            
            if not question_data:
                raise ConnectorError(f"Question '{title_slug}' missing or GraphQL malformed.")
                
            # Extract rich metadata for the Database
            metadata = {
                "id": question_data.get("questionId"),
                "frontend_id": question_data.get("questionFrontendId"),
                "title": question_data.get("title"),
                "difficulty": question_data.get("difficulty"),
                "tags": [t.get("name") for t in question_data.get("topicTags", [])],
                "is_paid_only": question_data.get("isPaidOnly")
            }
            
            # Pack tightly into the unified interface
            return RawContent(
                uri=title_slug,
                content_body=json.dumps(question_data),
                content_type="application/json",
                metadata=metadata
            )

    async def _do_fetch_page(self, uri: str, token: PaginationToken) -> Tuple[RawContent, PaginationToken]:
        """
        Streams problems exactly 50 at a time using GraphQL offsets.
        Supports Incremental Syncs and Deduplication on massive imports.
        """
        limit = 50
        skip = (token.current_page - 1) * limit
        
        query = """
        query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
            problemsetQuestionList: questionList(
                categorySlug: $categorySlug
                limit: $limit
                skip: $skip
                filters: $filters
            ) {
                totalNum
                data {
                    titleSlug
                }
            }
        }
        """
        
        session = await self._get_session()
        async with session.post(self.GRAPHQL_URL, json={"query": query, "variables": {"limit": limit, "skip": skip, "filters": {}}}) as resp:
            if resp.status == 429:
                raise RateLimitError("Rate limited during Pagination Stream.")
            resp.raise_for_status()
            data = await resp.json()
            
            problem_list = data.get("data", {}).get("problemsetQuestionList", {})
            total_num = problem_list.get("totalNum", 0)
            questions = problem_list.get("data", [])
            
            raw_content = RawContent(
                uri=f"page_{token.current_page}",
                content_body=json.dumps(questions),
                content_type="application/json",
                metadata={"total_num": total_num, "count": len(questions)}
            )
            
            next_skip = skip + limit
            has_more = next_skip < total_num
            
            next_token = PaginationToken(
                next_cursor=str(next_skip),
                has_more=has_more,
                current_page=token.current_page + 1
            )
            
            return raw_content, next_token

    async def close(self) -> None:
        """Safely disconnects TCP sockets to prevent asyncio warnings."""
        if self._session and not self._session.closed:
            await self._session.close()
