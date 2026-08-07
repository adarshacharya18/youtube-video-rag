# E2E Test Infra: Manim DSA Scene Renderer

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial + Real-World Workload Testing.

## Feature Inventory & Test Mapping
| # | Feature / Scene | Source Requirement | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Total Tests |
|---|-----------------|--------------------|:------:|:------:|:------:|:------:|:-----------:|
| 1 | `ArrayScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 2 | 2 | 14 |
| 2 | `LinkedListScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 2 | 2 | 14 |
| 3 | `StackQueueScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 1 | 2 | 13 |
| 4 | `HashmapScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 2 | 2 | 14 |
| 5 | `TreeScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 1 | 1 | 12 |
| 6 | `GraphScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 1 | 2 | 13 |
| 7 | `CodeScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 1 | 6 | 17 |
| 8 | `ComplexityScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 1 | 5 | 16 |
| 9 | `TitleScene` Dynamic Inputs & Actions | ORIGINAL_REQUEST §R1-R3 | 5 | 5 | 1 | 9 | 20 |
| **Total** | **9 Scenes** | **R1, R2, R3** | **45** | **45** | **12** | **9** | **111** |

## Test Architecture
- **Test Runner**: Pytest (`pytest tests/test_animation/test_manim_animation.py -v`)
- **Video Probing**: `probe_video(video_path)` (`ffprobe` `nb_frames > 1`, `duration > 0.1s`)
- **Frame Extraction**: `extract_frames(video_path, output_dir, fps=5)` via FFmpeg CLI
- **Frame Motion Delta Validation**: `compute_frame_motion_delta(img1, img2)` (`PIL ImageChops` normalized MAD, asserting `max_delta > 0.001` across consecutive frames to prevent freeze windows or static frame repetition)
- **Pytest Fixture Architecture**:
  - `manim_renderer` fixture in `conftest.py`: Returns fast, low-quality `ManimRenderer(quality="low", timeout=60.0)` targeting `tmp_path`.
  - `video_prober` & `motion_analyzer` fixtures in `conftest.py`: Reusable validation helpers across all test tiers.

## Real-World Application Scenarios (Tier 4)
| # | Scenario ID | Target DSA Algorithm | Scenes Exercised | Key Verification Focus |
|---|-------------|----------------------|------------------|------------------------|
| 1 | `T4_DSA_01` | Two Sum | Title, Code, Array, Hashmap, Complexity | Array scanning, hashmap lookup, time/space complexity cards. |
| 2 | `T4_DSA_02` | Reverse Linked List | Title, Code, LinkedList, Complexity | Iterative 3-pointer list reversal, arrow direction flipping. |
| 3 | `T4_DSA_03` | Binary Tree BFS | Title, Tree, StackQueue, Code | Level-order tree traversal pulses synchronized with queue states. |
| 4 | `T4_DSA_04` | Dijkstra Shortest Path | Title, Graph, Code, Complexity | Weighted edge graph traversal, min-heap code line highlights. |
| 5 | `T4_DSA_05` | Valid Parentheses | Title, Code, StackQueue | Stack container push/pop operations for bracket matching. |
| 6 | `T4_DSA_06` | Binary Search | Title, Array, Code, Complexity | Two-pointer index convergence on sorted array. |
| 7 | `T4_DSA_07` | LRU Cache | Title, Hashmap, LinkedList, Code | Hashmap lookup table combined with doubly linked list MRU/LRU updates. |
| 8 | `T4_DSA_08` | Topological Sort | Title, Graph, StackQueue, Complexity | DAG vertex traversal and output stack ordering. |
| 9 | `T4_DSA_09` | Fibonacci DP | Title, Array, Complexity, Code | DP array step highlights, complexity growth curve graph. |

## Coverage Thresholds & Gate Requirements
- **Tier 1 (Feature Coverage)**: 45 tests (5 per scene type) verifying custom parameter acceptance and basic action rendering.
- **Tier 2 (Boundary & Corner Cases)**: 45 tests (5 per scene type) verifying empty inputs, single elements, max bounds, negative/float values, and OOB index handling.
- **Tier 3 (Cross-Feature Interactions)**: 12 tests verifying multi-action and multi-parameter combinations.
- **Tier 4 (Real-World Application Scenarios)**: 9 tests verifying end-to-end multi-scene algorithm visualization traces.
- **Verification Rule**: 100% of tests must pass pytest with exit code 0, non-empty MP4 output, valid `ffprobe` metadata, and `max_delta > 0.001`.
