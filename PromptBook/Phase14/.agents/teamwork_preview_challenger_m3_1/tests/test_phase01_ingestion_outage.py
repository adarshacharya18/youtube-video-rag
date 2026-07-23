"""
test_phase01_ingestion_outage.py
Empirical simulation of Phase 01 Ingestion under a 3-minute network outage.
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

def simulate_ingestion_phase_outage():
    cb = CircuitBreaker(failure_threshold=5, reset_timeout=60)
    dlq = []
    ingested = []
    
    simulated_time = 0.0
    outage_start = 15.0
    outage_end = outage_start + 180.0  # 3 minute outage (15s to 195s)
    
    total_slugs = 60
    
    for i in range(1, total_slugs + 1):
        slug = f"leetcode-problem-{i:02d}"
        
        retries = 3
        success = False
        
        for attempt in range(retries):
            if not cb.allow_request(simulated_time):
                # CB is OPEN, fast fail (takes ~0.05s)
                simulated_time += 0.05
                continue
            
            # Request allowed
            is_down = outage_start <= simulated_time <= outage_end
            if is_down:
                cb.record_failure(simulated_time)
                delay = 2 ** attempt  # 1s, 2s, 4s backoff
                simulated_time += delay
            else:
                cb.record_success()
                simulated_time += 1.5  # 1.5s per HTTP GraphQL query
                success = True
                break
        
        if success:
            ingested.append((slug, simulated_time))
        else:
            dlq.append((slug, "CircuitBreakerFastFail" if cb.state == "OPEN" else "NetworkTimeout", simulated_time))

    print("=== PHASE 01 INGESTION OUTAGE SIMULATION ===")
    print(f"Total Slugs to Ingest: {total_slugs}")
    print(f"Outage Window: {outage_start}s to {outage_end}s (180s)")
    print(f"Successfully Ingested: {len(ingested)}")
    print(f"Failed & Routed to DLQ: {len(dlq)}")
    print(f"Circuit Breaker Final State: {cb.state}")
    print("\nDLQ Entries:")
    for entry in dlq:
        print(f"  - Slug: {entry[0]} | Failure Mode: {entry[1]} | Time: {entry[2]:.2f}s")

if __name__ == "__main__":
    simulate_ingestion_phase_outage()
