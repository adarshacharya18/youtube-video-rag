"""
test_batch_timing_simulation.py
Empirical Monte Carlo simulation testing the batch pipeline timing budget for 60 videos in a 12-hour window.
"""

import random
import statistics

NUM_VIDEOS = 60
TIMING_BUDGET_SEC = 12 * 3600  # 43,200 seconds (12 hours)
NUM_SIMULATIONS = 10000

def simulate_video_pipeline(complexity_type):
    """
    Simulate processing time (seconds) for a single video based on problem complexity.
    Complexity types:
      - 'simple' (30%): Array, Two Pointers, Hash Table (4-6 Manim scenes)
      - 'medium' (40%): Binary Tree, Heap, Slid. Window (7-10 Manim scenes)
      - 'complex' (30%): Dynamic Programming, Graph BFS/DFS, Segment Tree, LRU Cache (11-16 Manim scenes)
    """
    # Phase 01-03: Ingestion & RAG (nominal ~90s)
    p01_03 = random.uniform(60, 120)

    # Phase 05: Script Generation (nominal ~60s)
    p05 = random.uniform(45, 90)

    # Phase 06: Code Trace (nominal ~90s)
    p06 = random.uniform(60, 120)

    # Phase 12: LLM Audit (nominal ~30s)
    p12 = random.uniform(20, 40)

    # Phase 12 Retry / Self-Correction Loop (15% chance of 1 retry loop back to Phase 05 + P06 + P12)
    retry_overhead = 0.0
    if random.random() < 0.15:  # 15% rejection rate
        retry_overhead += random.uniform(45, 90) + random.uniform(60, 120) + random.uniform(20, 40)

    # Phase 08: TTS Voice (nominal ~30s)
    p08 = random.uniform(25, 45)

    # Phase 09: Manim CE GPU Render
    # Rendering time depends heavily on complexity & scene count
    if complexity_type == 'simple':
        p09 = random.uniform(120, 210)  # 2 to 3.5 mins
    elif complexity_type == 'medium':
        p09 = random.uniform(210, 360)  # 3.5 to 6 mins
    else:  # complex
        p09 = random.uniform(360, 720)  # 6 to 12 mins

    # Phase 09 Retry (5% chance of scene crash requiring re-render of failed scene)
    if random.random() < 0.05:
        p09 += random.uniform(60, 180)

    # Phase 10: Assembly (nominal ~18s)
    p10 = random.uniform(15, 30)

    # Phase 11: Subtitles/Thumbnails (nominal ~25s)
    p11 = random.uniform(20, 35)

    # Phase 13: YouTube Upload (nominal ~12s)
    p13 = random.uniform(10, 25)

    # Parallel vs Sequential execution of Phase 08 (Voice) and Phase 09 (Manim):
    # Spec states P08 and P09 run concurrently in async.gather() along with P11.
    render_phase_time = max(p08, p09, p11)

    total_video_time = (p01_03 + p05 + p06 + p12 + retry_overhead +
                        render_phase_time + p10 + p13)
    return total_video_time

def run_monte_carlo():
    random.seed(42)
    batch_durations = []
    exceeded_count = 0

    # Complexity distribution for 60 videos in a typical DSA curriculum
    # 30% simple (18 videos), 40% medium (24 videos), 30% complex (18 videos)
    complexities = ['simple'] * 18 + ['medium'] * 24 + ['complex'] * 18

    for _ in range(NUM_SIMULATIONS):
        random.shuffle(complexities)
        total_batch_time = sum(simulate_video_pipeline(c) for c in complexities)
        batch_durations.append(total_batch_time)
        if total_batch_time > TIMING_BUDGET_SEC:
            exceeded_count += 1

    avg_duration_hrs = statistics.mean(batch_durations) / 3600.0
    p50_hrs = statistics.median(batch_durations) / 3600.0
    p95_hrs = statistics.quantiles(batch_durations, n=20)[18] / 3600.0  # 95th percentile
    p99_hrs = statistics.quantiles(batch_durations, n=100)[98] / 3600.0 # 99th percentile
    max_hrs = max(batch_durations) / 3600.0
    failure_pct = (exceeded_count / NUM_SIMULATIONS) * 100.0

    print("=== MONTE CARLO BATCH TIMING SIMULATION RESULTS ===")
    print(f"Simulations: {NUM_SIMULATIONS}")
    print(f"Batch Size: {NUM_VIDEOS} videos")
    print(f"Target Budget: 12.0 hours (43,200 sec)")
    print(f"Mean Batch Duration: {avg_duration_hrs:.2f} hours ({statistics.mean(batch_durations):.1f}s)")
    print(f"Median (P50): {p50_hrs:.2f} hours")
    print(f"P95 Batch Duration: {p95_hrs:.2f} hours")
    print(f"P99 Batch Duration: {p99_hrs:.2f} hours")
    print(f"Max Batch Duration: {max_hrs:.2f} hours")
    print(f"Probability of Exceeding 12-Hour Window: {failure_pct:.2f}%")

if __name__ == "__main__":
    run_monte_carlo()
