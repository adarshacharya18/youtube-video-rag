import html
import re
from typing import Dict, Any, List, Union, Optional
from bs4 import BeautifulSoup
from src.models import Difficulty, Example, ScrapedProblem


class MarkdownSanitizer:
    """
    Sanitizes and standardizes Markdown, HTML content, and DSA problem data fields.
    Provides strict fail-fast validation when creating ScrapedProblem dataclasses.
    """

    @staticmethod
    def clean_html(text: str) -> str:
        """
        Strip unwanted HTML tags while preserving layout structure, then unescape HTML entities.
        """
        if not text:
            return ""

        # Convert sup and sub tags to math exponents/subscripts FIRST
        # Handle entity-encoded sup/sub tags if present
        text = re.sub(r"&lt;\s*(/?)\s*(sup|sub)\b([^&]*)&gt;", r"<\1\2\3>", text, flags=re.IGNORECASE)
        text = re.sub(r"<\s*sup[^>]*>(.*?)</\s*sup\s*>", r"^\1", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<\s*sub[^>]*>(.*?)</\s*sub\s*>", r"_\1", text, flags=re.DOTALL | re.IGNORECASE)

        # Unescape entity-encoded standard HTML tags BEFORE tag stripping so &lt;p&gt; gets stripped cleanly
        tag_pattern = r"&lt;\s*(/?)\s*(p|br|div|span|b|strong|i|em|code|pre|ul|ol|li|a|h[1-6]|table|tr|td|th|tbody|thead|img|section|article|header|footer|nav|main|font|blockquote)\b([^&]*)&gt;"
        text = re.sub(tag_pattern, r"<\1\2\3>", text, flags=re.IGNORECASE)

        # Parse with BeautifulSoup if HTML brackets exist to strip markup tags
        if "<" in text and ">" in text:
            # Replace common block/break tags with newlines before stripping
            soup_str = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
            soup_str = soup_str.replace("</p>", "\n</p>").replace("</div>", "\n</div>")
            soup = BeautifulSoup(soup_str, "html.parser")
            stripped = soup.get_text()
        else:
            stripped = text

        # Unescape HTML entities after tag stripping so &lt;tag&gt; becomes <tag>
        unescaped = html.unescape(stripped)

        return MarkdownSanitizer.normalize_whitespace(unescaped)

    @staticmethod
    def preserve_code_blocks(code: str) -> str:
        """
        Preserve indentation, spaces, and line structure of code blocks.
        Only strip overall leading/trailing blank lines and normalize line endings.
        """
        if not code:
            return ""

        # Normalize line endings
        normalized = code.replace("\r\n", "\n").replace("\r", "\n")

        # Strip only leading and trailing blank lines while preserving indentation of lines
        lines = normalized.split("\n")

        # Trim leading empty lines
        while lines and not lines[0].strip():
            lines.pop(0)

        # Trim trailing empty lines
        while lines and not lines[-1].strip():
            lines.pop()

        return "\n".join(lines)

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        Normalize line endings, trim line-trailing whitespace, and collapse 3+ newlines to 2.
        """
        if not text:
            return ""

        # Standardize line endings
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        # Strip line-trailing whitespace
        lines = [line.rstrip() for line in normalized.split("\n")]
        result = "\n".join(lines)

        # Collapse 3 or more consecutive newlines into 2
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result.strip()

    @staticmethod
    def clean_title(title: str) -> str:
        """
        Clean problem title by stripping header hashes, HTML entities, and extra spaces.
        """
        if not title:
            return ""

        cleaned = MarkdownSanitizer.clean_html(title)
        # Remove leading hashes
        cleaned = re.sub(r"^#+\s*", "", cleaned)
        cleaned = re.sub(r"^(Title|Problem):\s*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def clean_difficulty(difficulty_raw: Any) -> Difficulty:
        """
        Validate and convert raw difficulty to Difficulty enum. Raises ValueError if invalid.
        """
        if not difficulty_raw:
            raise ValueError("Difficulty cannot be empty or None")
        # Clean HTML markup if present (e.g. <b>Med</b>)
        diff_str = MarkdownSanitizer.clean_html(str(difficulty_raw))
        return Difficulty.from_string(diff_str)

    @staticmethod
    def clean_tags(tags_raw: Union[List[str], str, None]) -> List[str]:
        """
        Clean, strip HTML, and deduplicate tags.
        """
        if not tags_raw:
            return []

        if isinstance(tags_raw, str):
            raw_list = [t.strip() for t in tags_raw.split(",")]
        elif isinstance(tags_raw, (list, tuple)):
            raw_list = [str(t).strip() for t in tags_raw]
        else:
            raw_list = [str(tags_raw).strip()]

        cleaned_tags: List[str] = []
        seen = set()
        for tag in raw_list:
            tag_clean = MarkdownSanitizer.clean_html(tag)
            tag_clean = re.sub(r"^[-*#]\s*", "", tag_clean).strip()
            if tag_clean and tag_clean.lower() not in seen:
                seen.add(tag_clean.lower())
                cleaned_tags.append(tag_clean)

        return cleaned_tags

    @staticmethod
    def sanitize_example(ex: Union[Example, Dict[str, Any]]) -> Example:
        """
        Sanitize an Example instance or dictionary into a clean Example dataclass.
        """
        if isinstance(ex, Example):
            inp = ex.input
            out = ex.output
            exp = ex.explanation
        elif isinstance(ex, dict):
            inp = ex.get("input", "")
            out = ex.get("output", "")
            exp = ex.get("explanation", "")
        else:
            raise ValueError(f"Invalid example data format: {ex!r}")

        clean_inp = MarkdownSanitizer.clean_html(str(inp))
        clean_out = MarkdownSanitizer.clean_html(str(out))
        clean_exp = MarkdownSanitizer.clean_html(str(exp))

        return Example(input=clean_inp, output=clean_out, explanation=clean_exp)

    @classmethod
    def sanitize_problem(cls, data: Dict[str, Any]) -> ScrapedProblem:
        """
        Validate and standardize raw extracted problem dictionary into a validated ScrapedProblem.
        Performs strict fail-fast validation.
        """
        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary for problem data, got {type(data)}")

        # Title validation & cleaning
        raw_title = data.get("title")
        if not raw_title or not str(raw_title).strip():
            raise ValueError("Problem title is required and cannot be empty")
        title = cls.clean_title(str(raw_title))

        # Number validation
        raw_number = data.get("number")
        if raw_number is None or str(raw_number).strip() == "":
            num_match = re.match(r"^(\d+)\s*[\.\:\-]", title)
            if num_match:
                number = int(num_match.group(1))
                title = re.sub(r"^\d+\s*[\.\:\-]\s*", "", title).strip()
            else:
                raise ValueError("Problem number is required and cannot be empty")
        else:
            try:
                number = int(raw_number)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid problem number {raw_number!r}: {e}")

        if number <= 0:
            raise ValueError("Problem number must be a positive integer")

        # Slug validation
        slug = data.get("slug")
        if not slug or not str(slug).strip():
            derived_slug = re.sub(r"[^\w\s-]", "", title.lower())
            derived_slug = re.sub(r"[_\s]+", "-", derived_slug).strip("-")
            if not derived_slug:
                slug = f"problem-{number}" if number > 0 else "problem"
            else:
                slug = derived_slug
        else:
            slug = cls.clean_html(str(slug)).strip().lower()
            if not slug:
                slug = f"problem-{number}" if number > 0 else "problem"

        # Difficulty validation
        raw_diff = data.get("difficulty")
        difficulty = cls.clean_difficulty(raw_diff)

        # Description validation
        raw_desc = data.get("description")
        if not raw_desc or not str(raw_desc).strip():
            raise ValueError("Problem description is required and cannot be empty")
        description = cls.clean_html(str(raw_desc))

        # Accepted Code validation
        raw_code = data.get("accepted_code")
        if not raw_code or not str(raw_code).strip():
            raise ValueError("Accepted solution code is required and cannot be empty")
        accepted_code = cls.preserve_code_blocks(str(raw_code))

        # Code language validation
        code_language = str(data.get("code_language", "python")).strip().lower()
        if not code_language:
            code_language = "python"

        # Constraints
        raw_constraints = data.get("constraints", [])
        constraints: List[str] = []
        if isinstance(raw_constraints, (list, tuple)):
            for c in raw_constraints:
                c_clean = cls.clean_html(str(c))
                c_clean = re.sub(r"^[-*•]\s*", "", c_clean)
                if c_clean and c_clean not in constraints:
                    constraints.append(c_clean)

        # Examples
        raw_examples = data.get("examples", [])
        examples: List[Example] = []
        if isinstance(raw_examples, (list, tuple)):
            for ex in raw_examples:
                examples.append(cls.sanitize_example(ex))

        # Tags
        tags = cls.clean_tags(data.get("tags", []))

        # Scraped at
        scraped_at = str(data.get("scraped_at", ""))

        return ScrapedProblem(
            slug=slug,
            title=title,
            number=number,
            difficulty=difficulty,
            description=description,
            constraints=constraints,
            examples=examples,
            tags=tags,
            accepted_code=accepted_code,
            code_language=code_language,
            scraped_at=scraped_at,
        )


# Class Aliases
DataSanitizer = MarkdownSanitizer
ProblemSanitizer = MarkdownSanitizer
