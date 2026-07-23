import hashlib
import math
try:
    from scipy.stats import chisquare
    has_scipy = True
except ImportError:
    has_scipy = False

def get_hash_bucket(video_id: str, experiment_id: str, salt: str) -> int:
    payload = f"{video_id}:{experiment_id}:{salt}".encode('utf-8')
    digest = hashlib.sha256(payload).hexdigest()
    hash_int = int(digest, 16)
    return hash_int % 100

def test_uniformity():
    num_samples = 10000
    experiment_id = "exp_phase05_socratic_v3"
    salt = "socratic_prompt_v3_salt_9021"

    buckets = [0] * 100

    for i in range(num_samples):
        video_id = f"leetcode_{i:05d}_problem_title"
        bucket = get_hash_bucket(video_id, experiment_id, salt)
        buckets[bucket] += 1

    expected = num_samples / 100.0
    min_cnt = min(buckets)
    max_cnt = max(buckets)
    mean_cnt = sum(buckets) / len(buckets)
    variance = sum((x - mean_cnt) ** 2 for x in buckets) / len(buckets)
    stddev = math.sqrt(variance)

    # Chi-square statistic calculation
    chi2_stat = sum((x - expected) ** 2 / expected for x in buckets)

    print("=== SHA-256 HASH BUCKET UNIFORMITY TEST RESULTS ===")
    print(f"Total Samples: {num_samples}")
    print(f"Experiment ID: {experiment_id}")
    print(f"Salt:          {salt}")
    print(f"Expected / Bucket: {expected:.1f}")
    print(f"Min Count:     {min_cnt}")
    print(f"Max Count:     {max_cnt}")
    print(f"Mean Count:    {mean_cnt:.2f}")
    print(f"Std Dev:       {stddev:.2f}")
    print(f"Chi-Square Stat: {chi2_stat:.4f}")

    if has_scipy:
        stat, p_val = chisquare(buckets)
        print(f"scipy Chi-Square p-value: {p_val:.6f}")
        is_uniform = p_val > 0.05
    else:
        # Approximate p-value check for df=99, critical value at alpha=0.05 is 123.23
        print("scipy not installed; using critical value threshold 123.23 (alpha=0.05, df=99)")
        is_uniform = chi2_stat < 123.23
        p_val = None

    print(f"Uniformity Hypothesis (alpha=0.05): {'PASSED (Uniform)' if is_uniform else 'FAILED (Non-uniform)'}")

    # Display sample bucket breakdown (first 10 buckets and last 10 buckets)
    print("\nBucket Breakdown Sample (Buckets 0-9 & 90-99):")
    print("Buckets 0-9:  ", buckets[:10])
    print("Buckets 90-99:", buckets[90:])

if __name__ == "__main__":
    test_uniformity()
