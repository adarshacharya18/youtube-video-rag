import re
import html
from typing import Dict, Any, List, Optional
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
from src.models import ScrapedProblem, Example, Difficulty
from src.core.ingestion.sanitizer import MarkdownSanitizer


class DSAParser:
    """
    AST-based Markdown parser for DSA problem descriptions using markdown-it-py and BeautifulSoup.
    Traverses Markdown AST tokens to extract metadata, problem statement, examples, constraints,
    and solution code into validated ScrapedProblem objects.
    """

    def __init__(self):
        # Initialize MarkdownIt parser with commonmark and HTML support
        self.md = MarkdownIt("commonmark", {"html": True})

    def parse(self, markdown_content: str, scraped_at: Optional[str] = None) -> ScrapedProblem:
        """
        Parse raw Markdown text into a validated ScrapedProblem dataclass instance.
        """
        if not markdown_content or not markdown_content.strip():
            raise ValueError("Markdown content is empty or whitespace only")

        tokens = self.md.parse(markdown_content)

        raw_data: Dict[str, Any] = {
            "title": "",
            "slug": "",
            "number": None,
            "difficulty": None,
            "tags": [],
            "description": "",
            "constraints": [],
            "examples": [],
            "accepted_code": "",
            "code_language": "python",
            "scraped_at": scraped_at or "",
        }

        current_section = "HEAD"
        example_blocks: List[str] = []
        description_parts: List[str] = []
        constraints_parts: List[str] = []

        i = 0
        n = len(tokens)
        while i < n:
            token = tokens[i]

            # 1. Heading Token
            if token.type == "heading_open":
                level = token.tag  # e.g., 'h1', 'h2', 'h3'
                # Get heading content from next inline token
                inline_token = tokens[i + 1] if i + 1 < n and tokens[i + 1].type == "inline" else None
                heading_text = inline_token.content.strip() if inline_token else ""

                if level == "h1":
                    raw_data["title"] = heading_text
                    current_section = "METADATA"
                else:
                    norm_heading = heading_text.lower()
                    if any(k in norm_heading for k in ["description", "problem statement", "problem", "overview"]):
                        current_section = "DESCRIPTION"
                    elif any(k in norm_heading for k in ["example"]):
                        current_section = "EXAMPLES"
                        if heading_text:
                            example_blocks.append(heading_text)
                    elif any(k in norm_heading for k in ["constraint"]):
                        current_section = "CONSTRAINTS"
                    elif any(k in norm_heading for k in ["solution", "code", "python", "cpp", "c++", "implementation"]):
                        current_section = "CODE"
                    else:
                        if current_section == "EXAMPLES":
                            example_blocks.append(heading_text)

            # 2. Code Fence Token
            elif token.type == "fence":
                fence_lang = token.info.strip().lower() if token.info else ""
                code_content = token.content

                if current_section == "EXAMPLES":
                    example_blocks.append(code_content)
                elif current_section in ("CODE", "SOLUTION"):
                    if not raw_data["accepted_code"] or current_section in ("CODE", "SOLUTION"):
                        raw_data["accepted_code"] = code_content
                        if fence_lang:
                            if fence_lang in ["python", "python3", "py"]:
                                raw_data["code_language"] = "python"
                            elif fence_lang in ["cpp", "c++", "c"]:
                                raw_data["code_language"] = "cpp"
                            else:
                                raw_data["code_language"] = fence_lang

            # 3. HTML Block / Inline Token / Paragraph
            elif token.type in ("html_block", "inline"):
                text_content = token.content.strip()
                if text_content:
                    self._parse_metadata_lines(text_content, raw_data)

                    if current_section == "DESCRIPTION":
                        # Only add if it's not a heading title or metadata line
                        if not self._is_metadata_line(text_content):
                            description_parts.append(text_content)
                    elif current_section == "CONSTRAINTS":
                        self._parse_constraints_text(text_content, constraints_parts)
                    elif current_section == "EXAMPLES":
                        example_blocks.append(text_content)

            # 4. List Items
            elif token.type == "list_item_open":
                item_text = self._collect_list_item_text(tokens, i)
                if item_text:
                    self._parse_metadata_lines(item_text, raw_data)
                    if current_section == "CONSTRAINTS":
                        clean_item = re.sub(r"^[-*•]\s*", "", item_text).strip()
                        if clean_item and clean_item not in constraints_parts:
                            constraints_parts.append(clean_item)
                    elif current_section == "EXAMPLES":
                        example_blocks.append(item_text)

            i += 1

        # Post-processing parsed components
        raw_data["description"] = "\n\n".join(description_parts)
        raw_data["constraints"] = constraints_parts
        raw_data["examples"] = self._parse_examples(example_blocks)

        # Standardize and validate using MarkdownSanitizer
        return MarkdownSanitizer.sanitize_problem(raw_data)

    def _is_metadata_line(self, line: str) -> bool:
        """Check if line is a metadata line like Difficulty: Easy or Tags: Array."""
        clean = re.sub(r"\*\*|\*", "", line).strip()
        keywords = ["Difficulty:", "Tags:", "Slug:", "Problem Number:", "Number:", "Scraped At:", "Language:"]
        return any(clean.startswith(kw) for kw in keywords)

    def _parse_metadata_lines(self, text: str, raw_data: Dict[str, Any]) -> None:
        """
        Extract metadata key-values like Difficulty, Tags, Number, Slug from markdown text lines.
        """
        lines = text.split("\n")
        for line in lines:
            clean_line = re.sub(r"\*\*|\*", "", line).strip()

            # Difficulty
            diff_match = re.search(r"Difficulty:\s*([A-Za-z]+)", clean_line, re.IGNORECASE)
            if diff_match and not raw_data["difficulty"]:
                raw_data["difficulty"] = diff_match.group(1).strip()

            # Tags
            tag_match = re.search(r"Tags:\s*(.+)", clean_line, re.IGNORECASE)
            if tag_match and not raw_data["tags"]:
                raw_data["tags"] = [t.strip() for t in tag_match.group(1).split(",")]

            # Number
            num_match = re.search(r"(?:Number|Problem Number|ID):\s*(\d+)", clean_line, re.IGNORECASE)
            if num_match and not raw_data["number"]:
                raw_data["number"] = int(num_match.group(1))

            # Slug
            slug_match = re.search(r"Slug:\s*([a-zA-Z0-9_-]+)", clean_line, re.IGNORECASE)
            if slug_match and not raw_data["slug"]:
                raw_data["slug"] = slug_match.group(1).strip()

            # Scraped At
            scraped_match = re.search(r"Scraped\s*At:\s*(.+)", clean_line, re.IGNORECASE)
            if scraped_match and not raw_data["scraped_at"]:
                raw_data["scraped_at"] = scraped_match.group(1).strip()

            # Code Language
            lang_match = re.search(r"Language:\s*([a-zA-Z0-9_+-]+)", clean_line, re.IGNORECASE)
            if lang_match and raw_data["code_language"] == "python":
                raw_data["code_language"] = lang_match.group(1).strip()

    def _parse_constraints_text(self, text: str, constraints_parts: List[str]) -> None:
        """
        Extract individual constraint lines from paragraph or list text.
        """
        lines = text.split("\n")
        for line in lines:
            cleaned = line.strip()
            cleaned = re.sub(r"^[-*•]\s*", "", cleaned)
            if cleaned and not cleaned.lower().startswith("constraint") and not self._is_metadata_line(line):
                if cleaned not in constraints_parts:
                    constraints_parts.append(cleaned)

    def _collect_list_item_text(self, tokens: List[Any], index: int) -> str:
        """
        Helper to collect inner inline text of a list_item_open token.
        """
        text_parts = []
        j = index + 1
        depth = 1
        while j < len(tokens) and depth > 0:
            tok = tokens[j]
            if tok.type == "list_item_open":
                depth += 1
            elif tok.type == "list_item_close":
                depth -= 1
            elif tok.type == "inline":
                text_parts.append(tok.content)
            j += 1
        return " ".join(text_parts).strip()

    def _parse_examples(self, example_blocks: List[str]) -> List[Example]:
        """
        Parse raw text/code chunks under Examples section into Example dataclass list.
        """
        full_text = "\n".join(example_blocks)
        if not full_text.strip():
            return []

        # Unescape HTML entities & strip bold formatting tags for clean input/output regex matching
        clean_text = html.unescape(full_text)
        if "<" in clean_text and ">" in clean_text:
            clean_text = BeautifulSoup(clean_text, "html.parser").get_text()

        # Remove markdown bold/italic tags around Input/Output/Explanation labels
        clean_text = re.sub(r"\*\*(Input|Output|Explanation):\*\*", r"\1:", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\*(Input|Output|Explanation):\*", r"\1:", clean_text, flags=re.IGNORECASE)

        examples: List[Example] = []

        # Split text into chunks separated by Example headers or Input: markers
        chunks = re.split(r"(?=Example\s*\d+:?|Input:)", clean_text, flags=re.IGNORECASE)

        for chunk in chunks:
            chunk_clean = chunk.strip()
            if not chunk_clean:
                continue

            inp_match = re.search(r"Input:\s*(.*?)(?=(?:\s*,?\s*|\n\s*)(?:Output|Explanation|Input|Example)|$)", chunk_clean, re.DOTALL | re.IGNORECASE)
            out_match = re.search(r"Output:\s*(.*?)(?=(?:\s*,?\s*|\n\s*)(?:Explanation|Input|Example)|$)", chunk_clean, re.DOTALL | re.IGNORECASE)
            exp_match = re.search(r"Explanation:\s*(.*?)(?=(?:\s*,?\s*|\n\s*)(?:Input|Example)|$)", chunk_clean, re.DOTALL | re.IGNORECASE)

            if inp_match and out_match:
                inp_val = inp_match.group(1).strip()
                out_val = out_match.group(1).strip()
                exp_val = exp_match.group(1).strip() if exp_match else ""

                examples.append(Example(input=inp_val, output=out_val, explanation=exp_val))

        return examples
