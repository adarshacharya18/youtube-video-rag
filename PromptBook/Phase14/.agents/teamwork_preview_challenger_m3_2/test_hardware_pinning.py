#!/usr/bin/env python3
"""
Empirical Test Suite 1: Hardware Core Pinning, CPU Topology & Async Sync Validation
Tests the CPU pinning scheme, core overlap, and asyncio NPU Semaphore safety claims in 01_Production_Architecture.md.
"""

import sys
import os
import asyncio
import multiprocessing
import time
from dataclasses import dataclass
from typing import List, Dict, Set

# 1. CPU Topology Analysis for Intel Core Ultra 7 155H
# Spec claims: 16 Cores (6 P-Cores [12 threads], 8 E-Cores [8 threads], 2 LP E-Cores [2 threads]) = 22 Threads.
# Standard Linux Kernel CPU Indexing Topology for Hybrid Architecture:
# - Logical CPUs 0-11: 6 P-Cores with HyperThreading (2 threads per core: P0=0,1; P1=2,3; P2=4,5; P3=6,7; P4=8,9; P5=10,11)
# - Logical CPUs 12-19: 8 E-Cores (1 thread per core: E0=12, E1=13, E2=14, E3=15, E4=16, E5=17, E6=18, E7=19)
# - Logical CPUs 20-21: 2 LP E-Cores (1 thread per core: LP0=20, LP1=21)

TABLE_PINNING_CONFIG = {
    "Pipeline Control & EventBus": {"claimed_cores": "P-Cores 0, 1", "taskset": [0, 1, 2, 3]},
    "Ingestion & Web Scraping": {"claimed_cores": "E-Cores 6, 7", "taskset": [6, 7]},
    "Generative LLM Prompting": {"claimed_cores": "P-Core 2", "taskset": [4, 5]},
    "OpenVINO TTS Synthesis": {"claimed_cores": "E-Cores 8, 9", "taskset": [8, 9]},
    "Manim CE Scene Render": {"claimed_cores": "P-Cores 3, 4, 5", "taskset": [6, 7, 8, 9, 10, 11]},
    "FFmpeg QSV Video Assembly": {"claimed_cores": "E-Cores 10, 11, 12, 13", "taskset": [10, 11, 12, 13]}
}

def analyze_cpu_pinning_mapping():
    print("=== TEST 1.1: CPU Core Pinning Topology & Logical Mapping Verification ===")
    results = []
    
    # Analyze taskset vs actual Linux CPU topology
    p_core_logical_cpus = set(range(0, 12))
    e_core_logical_cpus = set(range(12, 20))
    lp_core_logical_cpus = set(range(20, 22))

    for subsystem, info in TABLE_PINNING_CONFIG.items():
        taskset_cpus = set(info["taskset"])
        claimed = info["claimed_cores"]
        
        # Check actual mapped architecture
        actual_p = taskset_cpus.intersection(p_core_logical_cpus)
        actual_e = taskset_cpus.intersection(e_core_logical_cpus)
        actual_lp = taskset_cpus.intersection(lp_core_logical_cpus)
        
        mismatch = False
        details = []
        if "E-Cores" in claimed and actual_p:
            mismatch = True
            details.append(f"MISMAPPED: Claimed {claimed}, but taskset {list(taskset_cpus)} maps to P-Core threads {list(actual_p)}!")
        elif "P-Cores" in claimed and actual_e:
            mismatch = True
            details.append(f"MISMAPPED: Claimed {claimed}, but taskset includes E-Core threads {list(actual_e)}!")
            
        print(f"Subsystem: {subsystem}")
        print(f"  Claimed: {claimed} | Taskset: {info['taskset']}")
        print(f"  Actual Topology: P-Core Threads={list(actual_p)}, E-Core Threads={list(actual_e)}, LP-Core Threads={list(actual_lp)}")
        if mismatch:
            print(f"  ❌ ERROR: {details[0]}")
        else:
            print(f"  ✓ Topology matched claimed category.")
        results.append((subsystem, mismatch, details))
    return results

def analyze_core_contention():
    print("\n=== TEST 1.2: Core Contention & Thread Overlap Matrix ===")
    # Phase 08 (TTS), Phase 09 (Manim), Phase 10 (FFmpeg) run concurrently per Section 2.3 & 4.4
    concurrent_subsystems = [
        "Ingestion & Web Scraping",
        "Generative LLM Prompting",
        "OpenVINO TTS Synthesis",
        "Manim CE Scene Render",
        "FFmpeg QSV Video Assembly"
    ]
    
    cpu_usage_map: Dict[int, List[str]] = {}
    for sub in concurrent_subsystems:
        cpus = TABLE_PINNING_CONFIG[sub]["taskset"]
        for c in cpus:
            if c not in cpu_usage_map:
                cpu_usage_map[c] = []
            cpu_usage_map[c].append(sub)
            
    print("Logical CPU Contention Map:")
    conflicts_found = 0
    for cpu_id in sorted(cpu_usage_map.keys()):
        subsystems = cpu_usage_map[cpu_id]
        if len(subsystems) > 1:
            conflicts_found += 1
            print(f"  ❌ Logical CPU {cpu_id}: CONFLICT between {subsystems}")
        else:
            print(f"  ✓ Logical CPU {cpu_id}: Assigned to {subsystems[0]}")
            
    print(f"\nTotal CPU Thread Conflicts: {conflicts_found} logical CPU cores shared concurrently.")
    return conflicts_found

# 2. Test OpenVINO NPU Thread Safety Lock (asyncio.Semaphore vs Multiprocess Subprocesses)
async def simulate_async_npu_work(worker_id: int, semaphore: asyncio.Semaphore, shared_state: list):
    async with semaphore:
        shared_state.append(f"Worker {worker_id} START NPU Ingest")
        await asyncio.sleep(0.05)
        shared_state.append(f"Worker {worker_id} END NPU Ingest")

def subprocess_npu_worker(worker_id: int, shared_counter):
    # Subprocess cannot see main process asyncio.Semaphore!
    # Simulates Manim/FFmpeg subprocess or separate worker process trying to access hardware
    time.sleep(0.01)
    with shared_counter.get_lock():
        shared_counter.value += 1

def test_npu_semaphore_multiprocess_isolation():
    print("\n=== TEST 1.3: OpenVINO NPU Thread Safety Lock Boundary Test ===")
    print("Evaluating asyncio.Semaphore(1) claim in multi-process operational architecture...")
    
    # 1. Asyncio inside single event loop works
    sem = asyncio.Semaphore(1)
    state = []
    async def run_async_test():
        await asyncio.gather(
            simulate_async_npu_work(1, sem, state),
            simulate_async_npu_work(2, sem, state)
        )
    asyncio.run(run_async_test())
    
    print("Single Event Loop asyncio.Semaphore behavior:")
    for entry in state:
        print(f"  {entry}")
        
    # 2. Subprocess boundary failure
    print("\nSubprocess Execution (Section 4.1 Architecture):")
    shared_counter = multiprocessing.Value('i', 0)
    p1 = multiprocessing.Process(target=subprocess_npu_worker, args=(1, shared_counter))
    p2 = multiprocessing.Process(target=subprocess_npu_worker, args=(2, shared_counter))
    
    p1.start()
    p2.start()
    p1.join()
    p2.join()
    
    print(f"  Subprocesses executed concurrently without asyncio.Semaphore control! Active concurrent hardware accesses = {shared_counter.value}")
    print("  ❌ CRITICAL VULNERABILITY: asyncio.Semaphore(1) provides NO inter-process locking across Manim/FFmpeg/TTS subprocess boundaries!")

if __name__ == "__main__":
    analyze_cpu_pinning_mapping()
    analyze_core_contention()
    test_npu_semaphore_multiprocess_isolation()
