"""
test_checkpoint_saga_consistency.py
Empirical proof of state inconsistency between Checkpoint Rehydration and Saga Compensation Rollback.
"""

import os
import hashlib
import json
import tempfile
import shutil

def run_checkpoint_saga_test():
    temp_dir = tempfile.mkdtemp()
    scratch_dir = os.path.join(temp_dir, "data", "animation", "scratch")
    checkpoint_dir = os.path.join(temp_dir, "data", "checkpoints", "lru-cache")
    os.makedirs(scratch_dir, exist_ok=True)
    os.makedirs(checkpoint_dir, exist_ok=True)

    # 1. Simulate render of Scene 1, Scene 2, Scene 3
    artifact_ledger = {}
    for scene_num in [1, 2, 3]:
        file_path = os.path.join(scratch_dir, f"scene_{scene_num}.mp4")
        content = f"Simulated MP4 content for scene {scene_num}".encode('utf-8')
        with open(file_path, "wb") as f:
            f.write(content)
        sha256_hash = hashlib.sha256(content).hexdigest()
        artifact_ledger[f"scene_{scene_num}"] = {
            "path": file_path,
            "hash": sha256_hash,
            "status": "COMPLETED"
        }

    # Save Checkpoint Snapshot
    checkpoint_data = {
        "slug": "lru-cache",
        "last_completed_phase": "Phase 09 (Scene 3/5)",
        "artifacts": artifact_ledger
    }
    checkpoint_file = os.path.join(checkpoint_dir, "checkpoint.json")
    with open(checkpoint_file, "w") as f:
        json.dump(checkpoint_data, f, indent=2)

    print("=== CHECKPOINT & SAGA CONSISTENCY TEST ===")
    print(f"Phase 09 Scene 1-3 created successfully. Artifact hashes recorded in {checkpoint_file}.")
    print(f"Scratch files on disk before failure: {os.listdir(scratch_dir)}")

    # 2. Simulate Scene 4 Failure -> Saga Compensation Triggered
    # Per Section 3.2: "Deletes incomplete MP4 scene renders in data/animation/scratch/"
    print("\n--- FAULT OCCURRED IN SCENE 4: Saga Compensation Triggered ---")
    shutil.rmtree(scratch_dir)
    os.makedirs(scratch_dir, exist_ok=True)
    print(f"Scratch files on disk after Saga rollback: {os.listdir(scratch_dir)}")

    # 3. Simulate Checkpoint Rehydration / Resume Attempt
    print("\n--- OPERATOR RESUMING FROM CHECKPOINT ---")
    with open(checkpoint_file, "r") as f:
        rehydrated_checkpoint = json.load(f)

    verification_failed = False
    for artifact_name, meta in rehydrated_checkpoint["artifacts"].items():
        target_path = meta["path"]
        expected_hash = meta["hash"]
        
        if not os.path.exists(target_path):
            print(f"[FAIL] Missing artifact file on disk: {target_path}")
            verification_failed = True
        else:
            with open(target_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            if actual_hash != expected_hash:
                print(f"[FAIL] Hash mismatch for {artifact_name}")
                verification_failed = True

    if verification_failed:
        print("\nRESULT: STATE REHYDRATION FAILED!")
        print("Conclusion: Saga compensation unlinked scratch scene renders, invalidating checkpoint SHA-256 ledger.")
        print("System CANNOT resume at Scene 4 and is forced to re-render Scene 1-3 from scratch.")
    else:
        print("\nRESULT: State rehydration succeeded.")

    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    run_checkpoint_saga_test()
