# Phase 15 / 02: Quality Evaluation Framework

**Author:** Principal Data Scientist / Quality Lead  
**Target System:** Automated DSA Educational YouTube Video Pipeline  
**Document Version:** 1.0.0  
**Status:** Implemented

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Evaluation Dimensions](#2-evaluation-dimensions)
3. [Implementation Guidance](#3-implementation-guidance)
4. [Trend Analysis & Reporting](#4-trend-analysis--reporting)

---

# 1. Executive Summary

As the platform evolves (Phase 15), we must ensure that experimental models or prompt variations do not degrade the quality of the final YouTube video. The **Quality Evaluation Framework** establishes quantitative scorecards and automated LLM-as-a-Judge mechanisms to rigorously evaluate the pipeline's output before it reaches the end user.

---

# 2. Evaluation Dimensions

### 2.1 Content & Technical Correctness
- **Educational Correctness:** Does the generated script accurately explain the underlying algorithm (e.g., Dijkstra's vs. BFS)? Is the intuition clear to a beginner?
- **Technical Correctness:** Is the generated Python code optimal? Does it pass the original LeetCode test cases?
- **Retrieval Quality:** Did the RAG system retrieve the correct optimal time/space complexity metadata for the given problem, or did it hallucinate a suboptimal O(N^2) solution?

### 2.2 Production Quality
- **Script Quality:** Is the narrative engaging? Does it avoid robotic, dry language while maintaining a professional educational tone?
- **Animation Quality:** Did Manim compile cleanly? Are the visualizations actually helpful (e.g., highlighting the correct nodes in a tree), or are they generic static shapes?
- **Narration Quality:** Did the TTS engine mispronounce technical terms (e.g., "Deque", "Trie", "Dijkstra")?
- **Overall Production Quality:** Is the audio-visual sync tight? Does the video meet the 1080p60 minimum standard without rendering glitches?

---

# 3. Implementation Guidance

### LLM-as-a-Judge Implementation
To scale quality evaluation across hundreds of videos, utilize an advanced model (e.g., GPT-4o or Claude 3.5 Sonnet) to act as a blind grader for the generated scripts and code.

```python
# src/core/evolution/evaluator.py
import json

class QualityEvaluator:
    def evaluate_script(self, script_text: str, leetcode_problem: str) -> dict:
        prompt = f"""
        You are an expert Computer Science educator and strict grader.
        Review the following YouTube script for the problem: {leetcode_problem}.
        
        Grade the script on a scale of 1-10 for:
        1. Educational Correctness
        2. Technical Correctness
        3. Script Engagement
        
        Output pure JSON: {{"educational": 9, "technical": 10, "engagement": 8, "feedback": "..."}}
        
        Script:
        {script_text}
        """
        # Call LLM and parse JSON response
        return self._call_llm(prompt)
```

### Heuristic / Deterministic Evaluation
- **Animation Quality:** Count the number of `Warning` or `Error` logs emitted by Manim during compilation. A high warning count directly lowers the Animation Quality score.
- **Technical Correctness:** Execute the generated code against local unit tests. If it fails, Technical Correctness = 0.
- **Narration Quality:** Maintain a deterministic "Pronunciation Dictionary" (`trie` -> `tree`, `deque` -> `deck`). Run a regex check on the script prior to TTS to ensure these replacements were successfully made.

---

# 4. Trend Analysis & Reporting

### Automated Scorecards
Every video generated (whether in Production or an A/B Test run) must output a `quality_scorecard.json` alongside the `.mp4` artifact.

```json
{
  "video_id": "two_sum",
  "model_version": "gpt-4o-2024-05-13",
  "experiment_id": "prompt_v2_ab_test",
  "scores": {
    "educational": 9,
    "technical": 10,
    "retrieval": 9,
    "script": 8,
    "animation": 7,
    "narration": 10
  },
  "overall_score": 8.8,
  "recommendations": [
    "Manim compilation produced 3 warnings regarding missing fonts.",
    "Script engagement is slightly low; consider adding more real-world analogies."
  ]
}
```

### Trend Analysis Pipeline
1. **Ingestion:** A scheduled task parses all `quality_scorecard.json` files generated over the last 7 days.
2. **Aggregation:** Calculate the moving average of the `overall_score`, segmented by `model_version` or `experiment_id`.
3. **Alerting:** If the 7-day moving average drops by more than 15% following a model upgrade or prompt change, trigger an automatic Slack alert to DevOps to halt the A/B test.
