"""
test_circuit_breaker_dlq_cascading.py
Empirical simulation of Circuit Breaker fast-fail cascading into DLQ accumulation during batch execution.
"""

class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = -999.0

    def record_failure(self, current_time):
        self.failure_count += 1
        self.last_failure_time = current_time
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def allow_request(self, current_time):
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if current_time - self.last_failure_time >= self.reset_timeout:
                self.state = "HALF-OPEN"
                return True
            return False
        if self.state == "HALF-OPEN":
            return True
        return False

def simulate_batch_with_transient_outage(outage_duration_sec=180, total_slugs=60):
    cb = CircuitBreaker(failure_threshold=5, reset_timeout=60)
    dlq = []
    processed_successfully = []
    system_status = "HEALTHY"
    
    simulated_time = 0.0  # seconds
    outage_start = 10.0
    outage_end = outage_start + outage_duration_sec
    
    for i in range(1, total_slugs + 1):
        slug = f"problem-slug-{i:02d}"
        
        # Attempt to process slug with retry policy (max 3 retries)
        retries = 3
        success = False
        
        for attempt in range(retries):
            # Check if CB allows request
            if not cb.allow_request(simulated_time):
                # FAST FAIL due to OPEN circuit breaker
                # Fast fail takes ~0.1s
                simulated_time += 0.1
                continue
            
            # Request allowed by CB, attempt call
            # Check if network is down at this simulated time
            is_network_down = outage_start <= simulated_time <= outage_end
            
            if is_network_down:
                # Network fails
                cb.record_failure(simulated_time)
                # Exponential backoff retry delay: 2s, 4s, 8s
                retry_delay = 2 ** attempt
                simulated_time += retry_delay
            else:
                # Network succeeds
                cb.record_success()
                success = True
                # Nominal slug processing time (e.g., 500 seconds per video phase)
                simulated_time += 500.0
                break
        
        if success:
            processed_successfully.append((slug, simulated_time))
        else:
            dlq.append((slug, "CircuitBreakerFastFail" if cb.state == "OPEN" else "NetworkTimeout", simulated_time))
            if len(dlq) > 5 and system_status == "HEALTHY":
                system_status = "DEGRADED"

    print("=== CIRCUIT BREAKER & DLQ CASCADING FAILURE SIMULATION ===")
    print(f"Total Slugs in Batch: {total_slugs}")
    print(f"Transient Network Outage Window: t={outage_start}s to t={outage_end}s ({outage_duration_sec}s)")
    print(f"Successfully Processed Slugs: {len(processed_successfully)}")
    print(f"DLQ Backlog Count: {len(dlq)}")
    print(f"Final System Status: {system_status}")
    print(f"Total Batch Elapsed Time: {simulated_time / 3600.0:.2f} hours")
    print("\nDLQ Breakdown:")
    for entry in dlq[:15]:
        print(f"  - Slug: {entry[0]} | Reason: {entry[1]} | Time: {entry[2]:.1f}s")
    if len(dlq) > 15:
        print(f"  ... and {len(dlq)-15} more items in DLQ.")

if __name__ == "__main__":
    simulate_batch_with_transient_outage()
