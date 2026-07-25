"""
Empirical Stress Test Harness for ChromaVectorStore.
Tests insertion, semantic search precision, metadata filtering edge cases,
deletion by slug, and ephemeral vs persistent behaviors.
"""

import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import Difficulty, Example, ScrapedProblem
from src.core.config import RAGConfig
from src.core.rag.embedder import MockEmbedder, Chunk, TextChunker
from src.core.rag.vector_store import ChromaVectorStore


def build_test_problems() -> List[ScrapedProblem]:
    """Build a rich dataset of 5 synthetic problems across various difficulties and tags."""
    p1 = ScrapedProblem(
        slug="two-sum",
        title="Two Sum",
        number=1,
        difficulty=Difficulty.EASY,
        description="Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        constraints=["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9"],
        examples=[Example(input="nums = [2,7,11,15], target = 9", output="[0,1]")],
        tags=["Array", "Hash Table"],
        accepted_code="class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        seen = {}\n        for i, num in enumerate(nums):\n            if target - num in seen:\n                return [seen[target - num], i]\n            seen[num] = i\n        return []",
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
        description="Given the root of a binary tree, return the level order traversal of its nodes' values.",
        constraints=["0 <= Node.val <= 1000"],
        examples=[Example(input="root = [3,9,20,null,null,15,7]", output="[[3],[9,20],[15,7]]")],
        tags=["Tree", "Breadth-First Search", "Binary Tree"],
        accepted_code="from collections import deque\nclass Solution:\n    def levelOrder(self, root):\n        if not root: return []\n        res, q = [], deque([root])\n        while q:\n            level = []\n            for _ in range(len(q)):\n                node = q.popleft()\n                level.append(node.val)\n                if node.left: q.append(node.left)\n                if node.right: q.append(node.right)\n            res.append(level)\n        return res",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )

    p4 = ScrapedProblem(
        slug="trapping-rain-water",
        title="Trapping Rain Water",
        number=42,
        difficulty=Difficulty.HARD,
        description="Given n non-negative integers representing an elevation map where the width of each bar is 1, compute how much water it can trap after raining.",
        constraints=["n == height.length", "1 <= n <= 2 * 10^4"],
        examples=[Example(input="height = [0,1,0,2,1,0,1,3,2,1,2,1]", output="6")],
        tags=["Array", "Two Pointers", "Dynamic Programming", "Stack"],
        accepted_code="class Solution:\n    def trap(self, height: list[int]) -> int:\n        left, right = 0, len(height) - 1\n        left_max, right_max = 0, 0\n        water = 0\n        while left < right:\n            if height[left] < height[right]:\n                if height[left] >= left_max: left_max = height[left]\n                else: water += left_max - height[left]\n                left += 1\n            else:\n                if height[right] >= right_max: right_max = height[right]\n                else: water += right_max - height[right]\n                right -= 1\n        return water",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )

    p5 = ScrapedProblem(
        slug="valid-anagram",
        title="Valid Anagram",
        number=242,
        difficulty=Difficulty.EASY,
        description="Given two strings s and t, return true if t is an anagram of s, and false otherwise.",
        constraints=["1 <= s.length, t.length <= 5 * 10^4"],
        examples=[Example(input="s = 'anagram', t = 'nagaram'", output="true")],
        tags=["Hash Table", "String", "Sorting"],
        accepted_code="class Solution:\n    def isAnagram(self, s: str, t: str) -> bool:\n        if len(s) != len(t): return False\n        count = {}\n        for char in s:\n            count[char] = count.get(char, 0) + 1\n        for char in t:\n            if char not in count or count[char] == 0: return False\n            count[char] -= 1\n        return True",
        code_language="python",
        scraped_at="2026-07-25T10:00:00Z",
    )

    return [p1, p2, p3, p4, p5]


class StressTestRunner:
    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    def log(self, category: str, test_name: str, status: str, details: str = ""):
        res = {
            "category": category,
            "test_name": test_name,
            "status": status,  # "PASS", "FAIL", "WARN"
            "details": details,
        }
        self.results.append(res)
        symbol = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
        print(f"[{symbol} {status}] [{category}] {test_name}: {details}")

    def run_all(self):
        print("==================================================")
        print("STARTING EMPIRICAL STRESS TEST SUITE")
        print("==================================================")
        self.test_suite_1_insertion_and_precision()
        self.test_suite_2_metadata_filtering()
        self.test_suite_3_deletion_by_slug()
        self.test_suite_4_ephemeral_vs_persistent()
        print("==================================================")
        print("STRESS TEST SUITE COMPLETE")
        print("==================================================")
        return self.results

    def test_suite_1_insertion_and_precision(self):
        cat = "1. Insertion & Precision"
        config = RAGConfig(collection_name="stress_test_precision")
        store = ChromaVectorStore(config=config, embedder=MockEmbedder(), is_test=True)

        # 1.1 Empty store query
        res_empty = store.query("Two sum target", top_k=5)
        if len(res_empty) == 0:
            self.log(cat, "Empty Store Query", "PASS", "Returned empty list [] without error")
        else:
            self.log(cat, "Empty Store Query", "FAIL", f"Expected [], got {res_empty}")

        # 1.2 Empty query string
        res_blank = store.query("", top_k=5)
        res_spaces = store.query("   ", top_k=5)
        if len(res_blank) == 0 and len(res_spaces) == 0:
            self.log(cat, "Blank/Whitespace Query", "PASS", "Returned empty list for blank query")
        else:
            self.log(cat, "Blank/Whitespace Query", "FAIL", "Failed to handle blank query safely")

        # 1.3 Add problem chunks
        problems = build_test_problems()
        total_inserted = 0
        p1_chunks = []
        for p in problems:
            ids = store.add_problem(p)
            total_inserted += len(ids)
            if p.slug == "two-sum":
                # Get generated text chunk content
                tc = TextChunker()
                p1_chunks.extend(tc.chunk_problem(p))

        stats = store.get_stats()
        if stats["total_chunks"] == total_inserted and stats["total_problems"] == 5:
            self.log(cat, "Problem Chunk Insertion", "PASS", f"Inserted {total_inserted} chunks for 5 problems")
        else:
            self.log(cat, "Problem Chunk Insertion", "FAIL", f"Expected {total_inserted} chunks, stats show {stats}")

        # 1.4 Exact chunk text precision match
        exact_chunk_text = p1_chunks[0].content
        results = store.query(exact_chunk_text, top_k=1)
        if len(results) > 0 and results[0]["metadata"]["slug"] == "two-sum" and abs(results[0]["score"] - 1.0) < 1e-4:
            self.log(cat, "Exact Match Precision (Top-1)", "PASS",
                     f"Top-1 match slug 'two-sum' with score {results[0]['score']:.4f} and distance {results[0]['distance']:.4f}")
        else:
            top_slug = results[0]["metadata"]["slug"] if results else "None"
            score = results[0]["score"] if results else 0.0
            self.log(cat, "Exact Match Precision (Top-1)", "FAIL", f"Expected slug 'two-sum' with score 1.0, got slug '{top_slug}' score {score}")

        # 1.5 MockEmbedder Non-Exact Query Warning Demonstration
        # Paraphrased/partial query with MockEmbedder produces orthogonal hash vectors
        partial_desc = problems[0].description
        part_results = store.query(partial_desc, top_k=1)
        part_slug = part_results[0]["metadata"]["slug"] if part_results else "None"
        part_score = part_results[0]["score"] if part_results else 0.0
        self.log(cat, "MockEmbedder Hash Behavior", "WARN",
                 f"Paraphrased query against MockEmbedder yielded top-1 slug '{part_slug}' with score {part_score:.4f} "
                 f"(MockEmbedder relies on exact SHA-256 string equality for vector alignment).")

        # 1.6 Query top_k larger than total count
        res_large_k = store.query("trapping rain water", top_k=100)
        if len(res_large_k) == stats["total_chunks"]:
            self.log(cat, "Top-K > Total Chunks", "PASS", f"Requested top_k=100, returned max available ({len(res_large_k)})")
        else:
            self.log(cat, "Top-K > Total Chunks", "WARN", f"Requested 100, returned {len(res_large_k)}, total {stats['total_chunks']}")

        # 1.7 Idempotency / duplicate insertion
        duplicate_ids = store.add_problem(problems[0])
        stats_after_dup = store.get_stats()
        if stats_after_dup["total_chunks"] == total_inserted:
            self.log(cat, "Idempotent Re-insertion", "PASS", "Upsert correctly updated existing IDs without duplicating count")
        else:
            self.log(cat, "Idempotent Re-insertion", "WARN", f"Count changed from {total_inserted} to {stats_after_dup['total_chunks']}")

    def test_suite_2_metadata_filtering(self):
        cat = "2. Metadata Filtering"
        config = RAGConfig(collection_name="stress_test_filtering")
        store = ChromaVectorStore(config=config, embedder=MockEmbedder(), is_test=True)

        problems = build_test_problems()
        for p in problems:
            store.add_problem(p)

        # 2.1 Filter by difficulty: Easy
        easy_res = store.query("problem", top_k=10, where={"difficulty": "Easy"})
        easy_slugs = {r["metadata"]["slug"] for r in easy_res}
        if easy_slugs.issubset({"two-sum", "reverse-linked-list", "valid-anagram"}) and len(easy_res) > 0:
            self.log(cat, "Filter by difficulty='Easy'", "PASS", f"Found {len(easy_res)} Easy chunks for slugs {easy_slugs}")
        else:
            self.log(cat, "Filter by difficulty='Easy'", "FAIL", f"Unexpected easy slugs: {easy_slugs}")

        # 2.2 Filter by difficulty: Hard
        hard_res = store.query("water elevation", top_k=10, where={"difficulty": "Hard"})
        hard_slugs = {r["metadata"]["slug"] for r in hard_res}
        if hard_slugs == {"trapping-rain-water"}:
            self.log(cat, "Filter by difficulty='Hard'", "PASS", f"Found Hard problem: {hard_slugs}")
        else:
            self.log(cat, "Filter by difficulty='Hard'", "FAIL", f"Expected {{'trapping-rain-water'}}, got {hard_slugs}")

        # 2.3 Filter by tag: single tag "Tree"
        tree_res = store.query("nodes level", top_k=10, where={"tags": "Tree"})
        tree_slugs = {r["metadata"]["slug"] for r in tree_res}
        if "binary-tree-level-order-traversal" in tree_slugs:
            self.log(cat, "Filter by single tag 'Tree'", "PASS", f"Matched slug binary-tree-level-order-traversal")
        else:
            self.log(cat, "Filter by single tag 'Tree'", "FAIL", f"Expected tree slug, got {tree_slugs}")

        # 2.4 Filter by chunk_type
        code_res = store.query("def solution", top_k=10, where={"chunk_type": "code"})
        all_code = all(r["metadata"]["chunk_type"] == "code" for r in code_res)
        if all_code and len(code_res) > 0:
            self.log(cat, "Filter by chunk_type='code'", "PASS", f"All {len(code_res)} results have chunk_type='code'")
        else:
            self.log(cat, "Filter by chunk_type='code'", "FAIL", f"Non-code chunks returned or empty")

        # 2.5 Multi-filter $and condition (difficulty=Easy AND chunk_type=code)
        multi_res = store.query("code", top_k=10, where={"difficulty": "Easy", "chunk_type": "code"})
        valid_multi = all(r["metadata"]["difficulty"] == "Easy" and r["metadata"]["chunk_type"] == "code" for r in multi_res)
        if valid_multi and len(multi_res) > 0:
            self.log(cat, "Multi-filter ($and)", "PASS", f"Returned {len(multi_res)} chunks matching Easy & code")
        else:
            self.log(cat, "Multi-filter ($and)", "FAIL", "Multi-filter returned invalid results")

        # 2.6 Edge Case: Filter by list of tags: where={"tags": ["Tree", "Stack"]}
        list_tag_res = store.query("problem", top_k=10, where={"tags": ["Tree", "Stack"]})
        if len(list_tag_res) == 0:
            self.log(cat, "Edge Case: List of tags filter ($in flaw)", "WARN",
                     "where={'tags': ['Tree', 'Stack']} returned 0 results because metadata string equality check fails for concatenated tag strings!")
        else:
            self.log(cat, "Edge Case: List of tags filter", "PASS", f"Returned {len(list_tag_res)} results for list tag filter")

        # 2.7 Non-matching filters returning empty list without error
        non_diff = store.query("problem", top_k=10, where={"difficulty": "NonExistent"})
        non_tag = store.query("problem", top_k=10, where={"tags": "QuantumComputing"})
        non_slug = store.query("problem", top_k=10, where={"slug": "missing-slug"})
        if len(non_diff) == 0 and len(non_tag) == 0 and len(non_slug) == 0:
            self.log(cat, "Non-matching Filters", "PASS", "All non-matching filters returned [] safely without errors")
        else:
            self.log(cat, "Non-matching Filters", "FAIL", "Non-matching filters returned non-empty results!")

    def test_suite_3_deletion_by_slug(self):
        cat = "3. Deletion by Slug"
        config = RAGConfig(collection_name="stress_test_deletion")
        store = ChromaVectorStore(config=config, embedder=MockEmbedder(), is_test=True)

        problems = build_test_problems()
        for p in problems:
            store.add_problem(p)

        init_stats = store.get_stats()
        init_prob_count = init_stats["total_problems"]

        # 3.1 Delete existing slug "two-sum"
        del_success = store.delete_by_slug("two-sum")
        post_del_stats = store.get_stats()

        del_query_res = store.query("two sum target", top_k=5, where={"slug": "two-sum"})

        if del_success and post_del_stats["total_problems"] == init_prob_count - 1 and len(del_query_res) == 0:
            self.log(cat, "Delete Existing Slug ('two-sum')", "PASS", "Slug successfully deleted, stats updated, query returned []")
        else:
            self.log(cat, "Delete Existing Slug ('two-sum')", "FAIL", f"del_success={del_success}, stats={post_del_stats}")

        # 3.2 Delete already deleted slug
        del_again = store.delete_by_slug("two-sum")
        if del_again is False:
            self.log(cat, "Delete Already Deleted Slug", "PASS", "Returned False as expected")
        else:
            self.log(cat, "Delete Already Deleted Slug", "FAIL", f"Expected False, got {del_again}")

        # 3.3 Delete non-existent slug
        del_non_exist = store.delete_by_slug("fake-problem-slug")
        if del_non_exist is False:
            self.log(cat, "Delete Non-Existent Slug", "PASS", "Returned False as expected")
        else:
            self.log(cat, "Delete Non-Existent Slug", "FAIL", f"Expected False, got {del_non_exist}")

        # 3.4 Delete empty string slug
        del_empty = store.delete_by_slug("")
        if del_empty is False:
            self.log(cat, "Delete Empty Slug", "PASS", "Returned False as expected")
        else:
            self.log(cat, "Delete Empty Slug", "FAIL", f"Expected False, got {del_empty}")

        # 3.5 Wipe entire collection with delete_collection()
        store.delete_collection()
        wiped_stats = store.get_stats()
        if wiped_stats["total_chunks"] == 0 and wiped_stats["total_problems"] == 0:
            self.log(cat, "Wipe Entire Collection", "PASS", "Collection wiped and recreated cleanly")
        else:
            self.log(cat, "Wipe Entire Collection", "FAIL", f"Collection wipe stats: {wiped_stats}")

    def test_suite_4_ephemeral_vs_persistent(self):
        cat = "4. Ephemeral vs Persistent"
        temp_dir = tempfile.mkdtemp(prefix="chroma_stress_test_")

        try:
            # 4.1 Ephemeral instance (is_test=True)
            config_eph = RAGConfig(collection_name="ephemeral_test")
            store_eph = ChromaVectorStore(config=config_eph, embedder=MockEmbedder(), is_test=True)

            p1 = build_test_problems()[0]
            store_eph.add_problem(p1)
            eph_count = store_eph.get_stats()["total_chunks"]

            if eph_count > 0:
                self.log(cat, "Ephemeral Client In-Memory Write", "PASS", f"Indexed {eph_count} chunks in ephemeral store")
            else:
                self.log(cat, "Ephemeral Client In-Memory Write", "FAIL", "Failed to index chunks in ephemeral store")

            # 4.2 Persistent instance attempt (is_test=False)
            config_pers = RAGConfig(collection_name="persistent_test", chroma_db_dir=temp_dir)
            store_pers_1 = ChromaVectorStore(
                config=config_pers,
                embedder=MockEmbedder(),
                is_test=False,
                persist_directory=temp_dir
            )

            store_pers_1.add_problem(p1)
            pers_count_1 = store_pers_1.get_stats()["total_chunks"]

            # Now create second store with same persist_directory
            store_pers_2 = ChromaVectorStore(
                config=config_pers,
                embedder=MockEmbedder(),
                is_test=False,
                persist_directory=temp_dir
            )
            pers_count_2 = store_pers_2.get_stats()["total_chunks"]

            try:
                import chromadb
                chroma_installed = True
            except ImportError:
                chroma_installed = False

            if not chroma_installed:
                if pers_count_2 == 0:
                    self.log(cat, "Fallback In-Memory Non-Persistence", "WARN",
                             "chromadb module is not installed; falling back to _InMemoryClient. "
                             "Data is NOT persisted to disk across ChromaVectorStore instances.")
                else:
                    self.log(cat, "Fallback In-Memory Non-Persistence", "FAIL", "Unexpected persistence with fallback client")
            else:
                if pers_count_2 == pers_count_1:
                    self.log(cat, "Persistent Client Disk Retention", "PASS", f"ChromaDB persistent client loaded {pers_count_2} chunks from disk")
                else:
                    self.log(cat, "Persistent Client Disk Retention", "FAIL", f"Expected {pers_count_1} chunks, got {pers_count_2}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    runner = StressTestRunner()
    results = runner.run_all()
    failed = [r for r in results if r["status"] == "FAIL"]
    sys.exit(1 if failed else 0)
