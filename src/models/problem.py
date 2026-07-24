from dataclasses import dataclass
from typing import Dict, Any, List
from datetime import datetime, timezone
from src.models.enums import Difficulty


@dataclass
class Example:
    input: str
    output: str
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Example":
        if not isinstance(data, dict):
            raise ValueError(f"Example.from_dict expects dict, got {type(data)}")
        return cls(
            input=str(data.get("input", "")),
            output=str(data.get("output", "")),
            explanation=str(data.get("explanation", "")),
        )


@dataclass(frozen=True)
class ScrapedProblem:
    slug: str
    title: str
    number: int
    difficulty: Difficulty
    description: str
    constraints: List[str]
    examples: List[Example]
    tags: List[str]
    accepted_code: str
    code_language: str
    scraped_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "number": self.number,
            "difficulty": self.difficulty.value if isinstance(self.difficulty, Difficulty) else str(self.difficulty),
            "description": self.description,
            "constraints": list(self.constraints),
            "examples": [ex.to_dict() if isinstance(ex, Example) else ex for ex in self.examples],
            "tags": list(self.tags),
            "accepted_code": self.accepted_code,
            "code_language": self.code_language,
            "scraped_at": self.scraped_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapedProblem":
        if not isinstance(data, dict):
            raise ValueError(f"ScrapedProblem.from_dict expects dict, got {type(data)}")

        raw_diff = data.get("difficulty")
        if isinstance(raw_diff, Difficulty):
            diff = raw_diff
        else:
            diff = Difficulty.from_string(raw_diff)

        raw_examples = data.get("examples", [])
        examples = [
            ex if isinstance(ex, Example) else Example.from_dict(ex)
            for ex in raw_examples
        ]

        scraped_at_val = data.get("scraped_at")
        if not scraped_at_val:
            scraped_at_val = datetime.now(timezone.utc).isoformat()

        return cls(
            slug=str(data.get("slug", "")),
            title=str(data.get("title", "")),
            number=int(data.get("number", 0)),
            difficulty=diff,
            description=str(data.get("description", "")),
            constraints=[str(c) for c in data.get("constraints", [])],
            examples=examples,
            tags=[str(t) for t in data.get("tags", [])],
            accepted_code=str(data.get("accepted_code", "")),
            code_language=str(data.get("code_language", "")),
            scraped_at=str(scraped_at_val),
        )
