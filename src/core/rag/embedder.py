"""
RAG Embedding Engine and Dual Chunking System.

Provides:
- Chunk: Dataclass representing text or code chunks.
- TextChunker: Section- and paragraph-aware markdown document splitter.
- CodeChunker: Syntax- and block-aware solution code splitter.
- BaseEmbedder: Abstract base interface for embedding models.
- OpenAIEmbedder: OpenAI text-embedding-3-small implementation (1536 dims).
- MockEmbedder: SHA-256 deterministic unit-vector generator for offline/testing fallback.
- get_embedder: Embedder factory.
"""

from __future__ import annotations

import math
import hashlib
import os
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from src.core.exceptions import EmbeddingError, RAGError
from src.core.logger import get_logger
from src.models.problem import ScrapedProblem

logger = get_logger(__name__)


@dataclass
class Chunk:
    """Represents a discrete chunk of text or code for embedding and retrieval."""

    chunk_id: str
    content: str
    chunk_type: str  # "text" | "code"
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_slug: str = ""
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk object to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
            "parent_slug": self.parent_slug,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


def _split_long_line(line: str, max_size: int) -> List[str]:
    """Split a single text line exceeding max_size into sub-lines of length <= max_size."""
    if len(line) <= max_size:
        return [line]

    words = line.split(" ")
    sub_lines: List[str] = []
    curr = ""

    for w in words:
        if len(w) > max_size:
            if curr:
                sub_lines.append(curr)
                curr = ""
            for i in range(0, len(w), max_size):
                part = w[i : i + max_size]
                if len(part) == max_size:
                    sub_lines.append(part)
                else:
                    curr = part
            continue

        if not curr:
            curr = w
        elif len(curr) + 1 + len(w) <= max_size:
            curr = f"{curr} {w}"
        else:
            sub_lines.append(curr)
            curr = w

    if curr:
        sub_lines.append(curr)

    return sub_lines if sub_lines else [line[:max_size]]


def _split_long_code_line(line: str, max_size: int) -> List[str]:
    """Split a single code line exceeding max_size into sub-lines of length <= max_size."""
    if len(line) <= max_size:
        return [line]

    indent = len(line) - len(line.lstrip())
    indent_str = line[:indent]
    content = line[indent:]

    sub_lines: List[str] = []
    eff_max = max(1, max_size - len(indent_str)) if indent < max_size else max_size
    prefix = indent_str if indent < max_size else ""

    for i in range(0, len(content), eff_max):
        sub_lines.append(prefix + content[i : i + eff_max])

    return sub_lines


class TextChunker:
    """Markdown section- and paragraph-aware text splitter for problem text and docs."""

    def __init__(self, max_chunk_size: int = 500, chunk_overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(
        self,
        text: str,
        parent_slug: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        max_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[Chunk]:
        """
        Splits markdown text into section/paragraph-aware chunks.
        """
        max_size = max_chunk_size or self.max_chunk_size
        overlap = chunk_overlap if chunk_overlap is not None else self.chunk_overlap
        meta = dict(metadata or {})

        if not text or not text.strip():
            return []

        # Split by markdown headers (#, ##, ###) or double newlines
        raw_sections = re.split(r"(\n(?=#{1,4}\s+))", text)
        sections: List[str] = []
        buf = ""
        for sec in raw_sections:
            if not sec:
                continue
            if re.match(r"\n?#{1,4}\s+", sec):
                if buf.strip():
                    sections.append(buf.strip())
                buf = sec
            else:
                buf += sec
        if buf.strip():
            sections.append(buf.strip())

        # Further split long sections by paragraph (\n\n) if needed
        units: List[str] = []
        for sec in sections:
            if len(sec) <= max_size:
                units.append(sec)
            else:
                paragraphs = sec.split("\n\n")
                for para in paragraphs:
                    para_str = para.strip()
                    if not para_str:
                        continue
                    if len(para_str) <= max_size:
                        units.append(para_str)
                    else:
                        # Split very long paragraph by lines/sentences
                        lines = para_str.split("\n")
                        current_chunk = ""
                        for line in lines:
                            sub_lines = _split_long_line(line, max_size)
                            for sub_line in sub_lines:
                                if len(current_chunk) + len(sub_line) + 1 <= max_size:
                                    current_chunk = (
                                        f"{current_chunk}\n{sub_line}".strip()
                                        if current_chunk
                                        else sub_line
                                    )
                                else:
                                    if current_chunk:
                                        units.append(current_chunk)
                                    current_chunk = sub_line
                        if current_chunk:
                            units.append(current_chunk)

        if not units:
            return []

        # Build Chunk objects with sliding window overlap
        chunks: List[Chunk] = []
        i = 0
        n_units = len(units)
        j_prev = -1

        while i < n_units:
            curr_units: List[str] = []
            curr_len = 0
            j = i
            while j < n_units:
                unit = units[j]
                sep_len = 2 if curr_units else 0
                if curr_len + sep_len + len(unit) <= max_size:
                    curr_units.append(unit)
                    curr_len += sep_len + len(unit)
                    j += 1
                else:
                    break

            if not curr_units:
                curr_units.append(units[i][:max_size])
                j = i + 1

            unit_str = "\n\n".join(curr_units)

            if overlap > 0 and chunks and i == j_prev:
                prev_content = chunks[-1].content
                curr_len = len(unit_str)
                avail = max_size - curr_len
                if avail > 0:
                    sep = "\n\n" if avail > 2 else ("\n" if avail == 2 else "")
                    max_overlap_chars = min(overlap, avail - len(sep))
                    if max_overlap_chars > 0:
                        overlap_str = prev_content[-max_overlap_chars:]
                        unit_str = f"{overlap_str}{sep}{unit_str}"

            cid = f"{parent_slug}_text_{len(chunks)}" if parent_slug else f"text_{len(chunks)}"
            c_meta = dict(meta)
            c_meta["chunk_type"] = "text"
            if parent_slug:
                c_meta["slug"] = parent_slug
                c_meta["parent_slug"] = parent_slug

            chunks.append(
                Chunk(
                    chunk_id=cid,
                    content=unit_str,
                    chunk_type="text",
                    metadata=c_meta,
                    parent_slug=parent_slug,
                )
            )

            j_prev = j

            if j >= n_units:
                break

            if overlap > 0:
                next_i = j
                overlap_acc = 0
                for k in range(j - 1, i - 1, -1):
                    u_len = len(units[k]) + (2 if overlap_acc > 0 else 0)
                    if overlap_acc + u_len <= overlap:
                        overlap_acc += u_len
                        next_i = k
                    else:
                        break
                if next_i == j or next_i == i:
                    i = j
                else:
                    i = next_i
            else:
                i = j

        return chunks

    def chunk_problem(
        self,
        problem: ScrapedProblem,
        max_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[Chunk]:
        """
        Generates text chunks from a ScrapedProblem object (description, constraints, examples).
        """
        diff_str = (
            problem.difficulty.value
            if hasattr(problem.difficulty, "value")
            else str(problem.difficulty)
        )
        tags_str = ",".join(problem.tags) if isinstance(problem.tags, list) else str(problem.tags)

        base_meta = {
            "slug": problem.slug,
            "title": problem.title,
            "number": problem.number,
            "difficulty": diff_str,
            "tags": tags_str,
            "scraped_at": problem.scraped_at,
            "chunk_type": "text",
        }

        # Build full text document combining problem header, description, constraints, and examples
        parts = [
            f"# Problem {problem.number}: {problem.title}",
            f"Difficulty: {diff_str}",
            f"Tags: {tags_str}",
            "\n## Description",
            problem.description or "",
        ]

        if problem.constraints:
            parts.append("\n## Constraints")
            for c in problem.constraints:
                parts.append(f"- {c}")

        if problem.examples:
            parts.append("\n## Examples")
            for idx, ex in enumerate(problem.examples, 1):
                inp = getattr(ex, "input", str(ex))
                outp = getattr(ex, "output", "")
                expl = getattr(ex, "explanation", "")
                ex_str = f"Example {idx}:\n  Input: {inp}\n  Output: {outp}"
                if expl:
                    ex_str += f"\n  Explanation: {expl}"
                parts.append(ex_str)

        full_text = "\n".join(parts)
        return self.split_text(
            text=full_text,
            parent_slug=problem.slug,
            metadata=base_meta,
            max_chunk_size=max_chunk_size or self.max_chunk_size,
            chunk_overlap=chunk_overlap if chunk_overlap is not None else self.chunk_overlap,
        )


class CodeChunker:
    """Syntax and statement-aware code splitter preserving algorithmic context."""

    def __init__(self, max_chunk_size: int = 1000):
        self.max_chunk_size = max_chunk_size

    def split_code(
        self,
        code: str,
        parent_slug: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        code_language: str = "python",
        max_chunk_size: Optional[int] = None,
    ) -> List[Chunk]:
        """
        Splits solution code into syntax-aware chunks preserving functions and block context.
        """
        max_size = max_chunk_size or self.max_chunk_size
        meta = dict(metadata or {})
        meta["code_language"] = code_language
        meta["chunk_type"] = "code"

        if not code or not code.strip():
            return []

        raw_lines = code.splitlines()
        total_lines = len(raw_lines)

        lines: List[str] = []
        for l in raw_lines:
            if len(l) > max_size:
                lines.extend(_split_long_code_line(l, max_size))
            else:
                lines.append(l)

        # If code fits within max_chunk_size, keep as a single intact unit
        if len(code) <= max_size:
            cid = f"{parent_slug}_code_0" if parent_slug else "code_0"
            c_meta = dict(meta)
            if parent_slug:
                c_meta["slug"] = parent_slug
                c_meta["parent_slug"] = parent_slug
            return [
                Chunk(
                    chunk_id=cid,
                    content=code,
                    chunk_type="code",
                    metadata=c_meta,
                    parent_slug=parent_slug,
                    start_line=1,
                    end_line=total_lines,
                )
            ]

        # Break long code into statement-aware blocks
        chunks: List[Chunk] = []
        current_lines: List[str] = []
        current_start_line = 1
        class_header = ""

        for line in lines:
            stripped = line.strip()

            active_class_header = class_header
            indent = len(line) - len(line.lstrip()) if stripped else -1

            is_top_level_non_comment = (
                stripped
                and indent == 0
                and not (stripped.startswith("#") or stripped.startswith("@"))
            )

            # Check for top-level statement/function boundary
            is_boundary = bool(
                current_lines
                and (
                    stripped.startswith("def ")
                    or stripped.startswith("class ")
                    or stripped.startswith("struct ")
                    or stripped.startswith("int ")
                    or stripped.startswith("void ")
                    or (is_top_level_non_comment and active_class_header)
                )
            )

            prefix = ""
            if active_class_header and current_lines and not current_lines[0].strip().startswith("class "):
                prefix = f"{active_class_header}\n    # ... (context)\n"

            current_len = len(prefix) + sum(len(l) + 1 for l in current_lines)

            if (current_len + len(line) > max_size) or is_boundary:
                if current_lines:
                    # Detach preceding comments/decorators at boundary so they attach to new block
                    k = len(current_lines)
                    if is_boundary:
                        while k > 0:
                            prev_stripped = current_lines[k - 1].strip()
                            if prev_stripped.startswith("#") or prev_stripped.startswith("@"):
                                k -= 1
                            elif prev_stripped == "" and k < len(current_lines):
                                if k - 2 >= 0 and (
                                    current_lines[k - 2].strip().startswith("#")
                                    or current_lines[k - 2].strip().startswith("@")
                                ):
                                    k -= 1
                                else:
                                    break
                            else:
                                break

                    prev_chunk_lines = current_lines[:k] if k > 0 else current_lines
                    carried_over = current_lines[k:] if k < len(current_lines) else []

                    if prev_chunk_lines:
                        chunk_prefix = ""
                        if active_class_header and not prev_chunk_lines[0].strip().startswith("class "):
                            chunk_prefix = f"{active_class_header}\n    # ... (context)\n"

                        content = chunk_prefix + "\n".join(prev_chunk_lines)
                        if len(content) > max_size:
                            content = content[:max_size]

                        c_meta = dict(meta)
                        cid = f"{parent_slug}_code_{len(chunks)}" if parent_slug else f"code_{len(chunks)}"
                        if parent_slug:
                            c_meta["slug"] = parent_slug
                            c_meta["parent_slug"] = parent_slug

                        end_line = current_start_line + len(prev_chunk_lines) - 1
                        if content.strip():
                            chunks.append(
                                Chunk(
                                    chunk_id=cid,
                                    content=content,
                                    chunk_type="code",
                                    metadata=c_meta,
                                    parent_slug=parent_slug,
                                    start_line=current_start_line,
                                    end_line=end_line,
                                )
                            )
                        current_start_line = end_line + 1

                    current_lines = list(carried_over)

            # Reset class_header when returning to indent 0 or encountering top-level statement
            if stripped and indent == 0:
                if stripped.startswith("class ") or stripped.startswith("struct "):
                    class_header = line
                elif not (stripped.startswith("#") or stripped.startswith("@")):
                    class_header = ""

            current_lines.append(line)

        if current_lines:
            chunk_prefix = ""
            if class_header and not current_lines[0].strip().startswith("class "):
                chunk_prefix = f"{class_header}\n    # ... (context)\n"

            content = chunk_prefix + "\n".join(current_lines)
            if len(content) > max_size:
                content = content[:max_size]

            c_meta = dict(meta)
            cid = f"{parent_slug}_code_{len(chunks)}" if parent_slug else f"code_{len(chunks)}"
            if parent_slug:
                c_meta["slug"] = parent_slug
                c_meta["parent_slug"] = parent_slug

            end_line = current_start_line + len(current_lines) - 1
            if content.strip():
                chunks.append(
                    Chunk(
                        chunk_id=cid,
                        content=content,
                        chunk_type="code",
                        metadata=c_meta,
                        parent_slug=parent_slug,
                        start_line=current_start_line,
                        end_line=end_line,
                    )
                )

        chunks = [c for c in chunks if c.content.strip()]
        return chunks

    def chunk_problem(
        self,
        problem: ScrapedProblem,
        max_chunk_size: Optional[int] = None,
    ) -> List[Chunk]:
        """
        Generates code chunks from a ScrapedProblem object.
        """
        if not problem.accepted_code or not problem.accepted_code.strip():
            return []

        diff_str = (
            problem.difficulty.value
            if hasattr(problem.difficulty, "value")
            else str(problem.difficulty)
        )
        tags_str = ",".join(problem.tags) if isinstance(problem.tags, list) else str(problem.tags)

        base_meta = {
            "slug": problem.slug,
            "title": problem.title,
            "number": problem.number,
            "difficulty": diff_str,
            "tags": tags_str,
            "code_language": problem.code_language or "python",
            "scraped_at": problem.scraped_at,
            "chunk_type": "code",
        }

        return self.split_code(
            code=problem.accepted_code,
            parent_slug=problem.slug,
            metadata=base_meta,
            code_language=problem.code_language or "python",
            max_chunk_size=max_chunk_size or self.max_chunk_size,
        )


class BaseEmbedder(ABC):
    """Abstract Base Class for embedding models."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a float vector."""
        pass

    @abstractmethod
    def embed_chunks(self, chunks: List[Chunk]) -> List[List[float]]:
        """Embed a list of Chunk objects into float vectors."""
        pass

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings into float vectors."""
        return [self.embed_text(t) for t in texts]


class MockEmbedder(BaseEmbedder):
    """
    Deterministic SHA-256 text-hash L2-normalized unit vector generator.
    Used for testing, local offline development, and zero-network execution.
    """

    def __init__(self, dimension: int = 1536):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        """Generate a deterministic 1536-dimensional L2-normalized unit vector."""
        if not text:
            text = ""

        # Seed pseudo-random number generator with SHA-256 hash of text
        hash_hex = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seed_val = int(hash_hex[:16], 16)
        rng = random.Random(seed_val)

        # Generate float components
        raw_vector = [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]

        # L2 Normalize
        l2_norm = math.sqrt(sum(x * x for x in raw_vector))
        if l2_norm == 0.0:
            l2_norm = 1.0

        return [x / l2_norm for x in raw_vector]

    def embed_chunks(self, chunks: List[Chunk]) -> List[List[float]]:
        return [self.embed_text(c.content) for c in chunks]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding implementation using text-embedding-3-small (1536 dims)."""

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.model_name = model_name
        self._dim = 1536
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise EmbeddingError("OpenAI API key was not provided.")
        try:
            import openai

            self.client = openai.OpenAI(api_key=key)
        except Exception as e:
            raise EmbeddingError(f"Failed to initialize OpenAI client: {e}") from e

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        try:
            res = self.client.embeddings.create(input=[text], model=self.model_name)
            return res.data[0].embedding
        except Exception as e:
            raise EmbeddingError(f"OpenAI embed_text failed: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            res = self.client.embeddings.create(input=texts, model=self.model_name)
            sorted_items = sorted(res.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_items]
        except Exception as e:
            raise EmbeddingError(f"OpenAI embed_batch failed: {e}") from e

    def embed_chunks(self, chunks: List[Chunk]) -> List[List[float]]:
        texts = [c.content for c in chunks]
        return self.embed_batch(texts)


def get_embedder(
    model_name: Optional[str] = None,
    use_mock: bool = False,
    api_key: Optional[str] = None,
) -> BaseEmbedder:
    """
    Factory function for instantiating an embedder.
    Falls back gracefully to MockEmbedder if requested or if OpenAI API key is missing.
    """
    if use_mock:
        logger.info("Using MockEmbedder as explicitly requested")
        return MockEmbedder()

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        logger.info("No OpenAI API key found; selecting MockEmbedder fallback")
        return MockEmbedder()

    try:
        model = model_name or "text-embedding-3-small"
        return OpenAIEmbedder(model_name=model, api_key=key)
    except Exception as e:
        logger.warning(
            "Failed to initialize OpenAIEmbedder, falling back to MockEmbedder", error=str(e)
        )
        return MockEmbedder()
