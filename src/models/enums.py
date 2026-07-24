from enum import Enum
from typing import Any


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"

    @classmethod
    def from_string(cls, value: Any) -> "Difficulty":
        if isinstance(value, cls):
            return value
        if not value or not isinstance(value, str):
            raise ValueError(f"Invalid difficulty value: {value!r}")

        normalized = value.strip().upper()
        mapping = {
            "EASY": cls.EASY,
            "MEDIUM": cls.MEDIUM,
            "MED": cls.MEDIUM,
            "HARD": cls.HARD,
        }
        if normalized in mapping:
            return mapping[normalized]

        for member in cls:
            if member.value.upper() == normalized:
                return member

        raise ValueError(f"Unknown difficulty: {value!r}")
