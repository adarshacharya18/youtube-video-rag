# Context: Video Template & Visual Specifications (`video_template.md`)

This document defines the standard 10-section video storyboard, dark-mode visual design system, and Manim animation templates for the Automated DSA Educational YouTube Video Automation Pipeline.

---

## 1. Visual Design Tokens & Palette

To ensure a sleek, high-end educational aesthetic (similar to 3Blue1Brown), all visual elements are styled using a standardized dark theme palette.

| Token | Hex Value | Purpose |
|---|---|---|
| `BG_COLOR` | `#0f0f23` | Deep dark blue-black canvas background |
| `TEXT_COLOR` | `#e0e0e0` | Soft white for titles, descriptions, and code |
| `ACCENT_COLOR` | `#00d4ff` | Cyan accent for primary pointer highlights |
| `SUCCESS_COLOR` | `#00ff88` | Bright green for found/sorted elements |
| `ERROR_COLOR` | `#ff4444` | Bright red for missing/invalid pointers |
| `WARNING_COLOR` | `#ffaa00` | Warm orange for active iteration cursors |
| `INACTIVE_COLOR` | `#4a4a6a` | Muted slate gray for unvisited nodes |
| `CODE_BG` | `#1a1a2e` | Container background for C++ code blocks |
| `CELL_FILL` | `#16213e` | Array/Node cell fill color |
| `CELL_BORDER` | `#0f3460` | Cell border line color |

---

## 2. Standard 10-Section Storyboard Structure

Every video produced by the pipeline follows this exact 10-section storyboard:

| # | Section | Content Description | Duration Target | Primary Visual Template |
|---|---|---|---|---|
| 1 | **Title Card** | Problem Name, LeetCode #, Difficulty, Topic Tags | 15s | `TitleCardScene` |
| 2 | **Problem & Constraints** | Requirements explanation and array/list limits | 45s | `BulletPointScene` |
| 3 | **Intuition** | The "Aha!" conceptual mental model / metaphor | 60s | `IntuitionDiagramScene` |
| 4 | **Approach** | High-level algorithmic steps flow | 45s | `StepFlowScene` |
| 5 | **Pseudo Code** | Language-agnostic logic walkthrough | 45s | `PseudoCodeScene` |
| 6 | **Example Walkthrough** | Step-by-step execution on sample input | 180s | Custom DSA Scene (`LinkedListScene`, etc.) |
| 7 | **Edge Cases** | Handling empty inputs, single nodes, odd/even | 45s | `HighlightBoxScene` |
| 8 | **C++ Code** | Your accepted solution walkthrough | 120s | `CodeTypingScene` |
| 9 | **Complexity Analysis** | Big-O Time and Space analysis | 30s | `ComplexityChartScene` |
| 10 | **Outro** | Summary key takeaways & Subscribe call | 15s | `OutroCardScene` |

---

## 3. Core Manim Animation Template Specs

### A. `StepFlow` (Flowchart & High-Level Steps)
- Renders numbered boxes connected by directed arrows.
- Sequentially highlights each step in `ACCENT_COLOR` as the audio narrator introduces the step.

### B. `LinkedListScene` (DSA Visualizer - e.g., #143 Reorder List)
- Visualizes linked list nodes with pointers (`next`).
- Supports slow & fast pointer animations, split point markers, in-place pointer reversal animations, and interleaving merge animations.

### C. `CodeTyping` (Human-Like Code Typing Animation)
- Displays C++ code inside a styled box (`CODE_BG`).
- **Human Typing Simulation:** Characters appear sequentially line-by-line with a flashing cursor bar (`ACCENT_COLOR`).
- Highlights active execution lines during code walkthrough narration.
