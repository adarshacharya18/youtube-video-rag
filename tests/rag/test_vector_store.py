"""
Integration tests for ChromaVectorStore with synthetic DSA problem fixtures.
"""

import pytest
from src.models import Difficulty, Example, ScrapedProblem
from src.core.config import RAGConfig
from src.core.rag.embedder import Chunk, MockEmbedder
from src.core.rag.vector_store import ChromaVectorStore


def create_sample_problems() -> list[ScrapedProblem]:
    """Helper creating synthetic ScrapedProblem instances across different difficulties and tags."""
    p1 = ScrapedProblem(
        slug="two-sum",
        title="Two Sum",
        number=1,
        difficulty=Difficulty.EASY,
        description="Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        constraints=["2 <= nums.length <= 104"],
        examples=[Example(input="nums = [2,7,11,15], target = 9", output="[0,1]")],
        tags=["Array", "Hash Table"],
        accepted_code="class Solution:\n    def twoSum(self, nums, target):\n        seen = {}\n        for i, n in enumerate(nums):\n            if target - n in seen:\n                return [seen[target - n], i]\n            seen[n] = i\n        return []",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )

    p2 = ScrapedProblem(
        slug="reverse-linked-list",
        title="Reverse Linked List",
        number=206,
        difficulty=Difficulty.EASY,
        description="Given the head of a singly linked list, reverse the list, and return the reversed list.",
        constraints=["0 <= Node.val <= 5000"],
        examples=[Example(input="head = [1,2,3,4,5]", output="[5,4,3,2,1]")],
        tags=["Linked List", "Recursion"],
        accepted_code="class Solution:\n    def reverseList(self, head):\n        prev = None\n        curr = head\n        while curr:\n            nxt = curr.next\n            curr.next = prev\n            prev = curr\n            curr = nxt\n        return prev",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )

    p3 = ScrapedProblem(
        slug="binary-tree-level-order-traversal",
        title="Binary Tree Level Order Traversal",
        number=102,
        difficulty=Difficulty.MEDIUM,
        description="Given the root of a binary tree, return the level order traversal of its nodes' values. (i.e., from left to right, level by level).",
        constraints=["0 <= Node.val <= 1000"],
        examples=[Example(input="root = [3,9,20,null,null,15,7]", output="[[3],[9,20],[15,7]]")],
        tags=["Tree", "Breadth-First Search", "Binary Tree"],
        accepted_code="from collections import deque\nclass Solution:\n    def levelOrder(self, root):\n        if not root: return []\n        res, q = [], deque([root])\n        while q:\n            level = []\n            for _ in range(len(q)):\n                node = q.popleft()\n                level.append(node.val)\n                if node.left: q.append(node.left)\n                if node.right: q.append(node.right)\n            res.append(level)\n        return res",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )

    return [p1, p2, p3]


@pytest.fixture
def store() -> ChromaVectorStore:
    """Fixture providing an ephemeral in-memory ChromaVectorStore with MockEmbedder."""
    config = RAGConfig(collection_name="test_dsa_knowledge")
    embedder = MockEmbedder()
    return ChromaVectorStore(config=config, embedder=embedder, is_test=True)


# ============================================================================
# Vector Store Tests
# ============================================================================

def test_vector_store_initialization(store: ChromaVectorStore):
    assert store.collection_name == "test_dsa_knowledge"
    stats = store.get_stats()
    assert stats["total_chunks"] == 0
    assert stats["total_problems"] == 0


def test_add_problem_and_query(store: ChromaVectorStore):
    problems = create_sample_problems()
    two_sum = problems[0]

    chunk_ids = store.add_problem(two_sum)
    assert len(chunk_ids) >= 2  # Text chunk + Code chunk

    # Query without filter
    results = store.query("Find two numbers that add up to target", top_k=5)
    assert len(results) > 0
    first = results[0]
    assert "id" in first
    assert "document" in first
    assert "metadata" in first
    assert "score" in first
    assert first["metadata"]["slug"] == "two-sum"


def test_metadata_filtering_by_difficulty(store: ChromaVectorStore):
    problems = create_sample_problems()
    for p in problems:
        store.add_problem(p)

    # Query Easy problems
    easy_results = store.query("Search query", top_k=10, where={"difficulty": "Easy"})
    assert len(easy_results) > 0
    for r in easy_results:
        assert r["metadata"]["difficulty"] == "Easy"

    # Query Medium problems
    med_results = store.query("Search query", top_k=10, where={"difficulty": "Medium"})
    assert len(med_results) > 0
    for r in med_results:
        assert r["metadata"]["difficulty"] == "Medium"


def test_metadata_filtering_by_tags(store: ChromaVectorStore):
    problems = create_sample_problems()
    for p in problems:
        store.add_problem(p)

    # Query Tree tag
    tree_results = store.query("tree traversal", top_k=10, where={"tags": "Tree"})
    assert len(tree_results) > 0
    for r in tree_results:
        assert "Tree" in r["metadata"]["tags"]
        assert r["metadata"]["slug"] == "binary-tree-level-order-traversal"


def test_metadata_filtering_by_chunk_type(store: ChromaVectorStore):
    problems = create_sample_problems()
    for p in problems:
        store.add_problem(p)

    # Query only code chunks
    code_results = store.query("def twoSum", top_k=10, where={"chunk_type": "code"})
    assert len(code_results) > 0
    for r in code_results:
        assert r["metadata"]["chunk_type"] == "code"


def test_delete_by_slug(store: ChromaVectorStore):
    problems = create_sample_problems()
    for p in problems:
        store.add_problem(p)

    initial_stats = store.get_stats()
    assert initial_stats["total_problems"] == 3

    # Delete two-sum
    deleted = store.delete_by_slug("two-sum")
    assert deleted is True

    # Try deleting non-existent slug
    deleted_again = store.delete_by_slug("non-existent-slug")
    assert deleted_again is False

    new_stats = store.get_stats()
    assert new_stats["total_problems"] == 2
    assert "two-sum" not in new_stats["unique_slugs"]

    # Verify query for two-sum returns no chunks
    results = store.query("two sum", top_k=5, where={"slug": "two-sum"})
    assert len(results) == 0


def test_get_stats_and_delete_collection(store: ChromaVectorStore):
    problems = create_sample_problems()
    for p in problems:
        store.add_problem(p)

    stats = store.get_stats()
    assert stats["total_problems"] == 3
    assert stats["total_chunks"] > 0
    assert stats["chunk_types"]["text"] > 0
    assert stats["chunk_types"]["code"] > 0

    # Wipe collection
    store.delete_collection()
    wiped_stats = store.get_stats()
    assert wiped_stats["total_chunks"] == 0
    assert wiped_stats["total_problems"] == 0
