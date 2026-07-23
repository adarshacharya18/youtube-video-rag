import hashlib
import math
import random
import uuid

def get_hash_bucket(video_id: str, experiment_id: str, salt: str) -> int:
    payload = f"{video_id}:{experiment_id}:{salt}".encode('utf-8')
    digest = hashlib.sha256(payload).hexdigest()
    hash_int = int(digest, 16)
    return hash_int % 100

def chi2_sf(df, x):
    """Survival function (1 - CDF) for Chi-Square distribution using math.gamma."""
    # chi2_sf(df, x) = igamc(df/2, x/2)
    return math.gamma(df / 2.0) # we can use incomplete gamma function

def p_value_chi2(chi2_stat, df=99):
    """Compute upper tail p-value using incomplete gamma function math.erfc or math.gamma integration/approximation."""
    # Since python 3.2+, math has no direct igamc, but we can compute or scipy can be checked.
    # Alternatively we can compute using series expansion or standard approximation.
    # Wilson-Hilferty transformation:
    # Z = ((chi2/df)**(1/3) - (1 - 2/(9*df))) / sqrt(2/(9*df))
    k = df
    z = ((chi2_stat / k)**(1/3) - (1 - 2/(9*k))) / math.sqrt(2/(9*k))
    # p-value = 0.5 * erfc(z / sqrt(2))
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return p

def run_suite():
    num_samples = 10000
    experiment_id = "exp_phase05_socratic_v3"
    
    datasets = {
        "Sequential LeetCode Titles": [f"leetcode_{i:05d}_problem_title" for i in range(num_samples)],
        "UUID4 Video IDs": [str(uuid.uuid4()) for _ in range(num_samples)],
        "Random Alphanumeric Slugs": [f"problem-slug-{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))}" for _ in range(num_samples)],
        "Numeric IDs": [str(i) for i in range(num_samples)]
    }

    salts = [
        "socratic_prompt_v3_salt_9021",
        "salt_alpha_2026",
        "salt_beta_7712",
        "salt_gamma_9901",
        "salt_delta_0042"
    ]

    print("=== EXTENDED SHA-256 HASH UNIFORMITY BENCHMARK ===")
    print(f"Sample Size: {num_samples} items per test run")
    print(f"Target Buckets: 100 (Expected per bucket = {num_samples/100:.1f})\n")

    summary_rows = []

    for dname, items in datasets.items():
        for salt in salts:
            buckets = [0] * 100
            for vid in items:
                b = get_hash_bucket(vid, experiment_id, salt)
                buckets[b] += 1
            
            min_c = min(buckets)
            max_c = max(buckets)
            mean_c = sum(buckets) / 100.0
            std_c = math.sqrt(sum((x - mean_c)**2 for x in buckets) / 100.0)
            chi2 = sum((x - 100.0)**2 / 100.0 for x in buckets)
            pval = p_value_chi2(chi2, df=99)
            
            status = "PASS (Uniform)" if pval > 0.01 else "FAIL (Non-uniform)"
            summary_rows.append((dname, salt, min_c, max_c, mean_c, std_c, chi2, pval, status))

    print(f"{'Dataset':<28} | {'Salt':<28} | {'Min':<4} | {'Max':<4} | {'StdDev':<6} | {'Chi2':<7} | {'p-val':<7} | {'Result'}")
    print("-" * 120)
    for r in summary_rows:
        print(f"{r[0]:<28} | {r[1]:<28} | {r[2]:<4} | {r[3]:<4} | {r[5]:<6.2f} | {r[6]:<7.2f} | {r[7]:<7.4f} | {r[8]}")

if __name__ == "__main__":
    random.seed(42)
    run_suite()
