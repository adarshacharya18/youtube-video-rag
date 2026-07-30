"""Theme and Styling Constants for Manim DSA Animations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    """Catppuccin Mocha themed color scheme for video animations."""

    BACKGROUND: str = "#1E1E2E"
    TEXT_PRIMARY: str = "#CDD6F4"
    TEXT_SECONDARY: str = "#A6ADC8"
    PRIMARY_ACCENT: str = "#89B4FA"
    SECONDARY_ACCENT: str = "#F38BA8"
    HIGHLIGHT: str = "#A6E3A1"
    WARNING: str = "#F9E2AF"
    CONTAINER_BG: str = "#313244"
    BORDER: str = "#45475A"


DEFAULT_THEME = ThemeColors()
DEFAULT_FONT = "Sans-Serif"
DEFAULT_FPS = 30
