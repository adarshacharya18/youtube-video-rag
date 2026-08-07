# Original User Request

## 2026-08-07T05:38:57Z

Enhance all Manim scene renderers in `/home/adarsh/Documents/Youtube-Channel/src/animation/scenes` to dynamically accept custom problem-specific example arguments, conduct domain research on visualization techniques for each DSA topic, eliminate static frame repetition, and provide untruncated, fully understandable educational step-by-step animations.

Working directory: /home/adarsh/Documents/Youtube-Channel
Integrity mode: development

## Requirements

### R1. Dynamic Custom Input & Parameter Parsing
- All scene templates (`linkedlist_scene.py`, `array_scene.py`, `tree_scene.py`, `graph_scene.py`, `hashmap_scene.py`, `stack_queue_scene.py`, `code_scene.py`, `complexity_scene.py`, `title_scene.py`) must cleanly parse and animate arbitrary custom input arguments (e.g., custom array elements, tree structures, graph vertices/edges, code strings, pointers, key-value maps) passed via `parameters.json`.

### R2. Comprehensive DSA Visualization Techniques Research & Refactoring
- Perform domain research on standard, high-quality visualization techniques for each DSA data structure.
- Implement dedicated animation routines for actions without frame duplication or static pauses, keeping every frame visually informative and understandable.

### R3. Unconstrained Educational Timing
- Adapt animation timelines naturally based on the number of steps and complexity rather than artificially truncating or rushing key algorithmic steps.

## Acceptance Criteria

### Visualization & Dynamic Parameter Acceptance
- [ ] Running pytest/Manim renders on custom input arguments for each scene produces valid `.mp4` video clips reflecting the custom inputs.
- [ ] No frame duplication or freeze states occur during step transitions.
- [ ] Each animation step clearly depicts the underlying data structure state change.
