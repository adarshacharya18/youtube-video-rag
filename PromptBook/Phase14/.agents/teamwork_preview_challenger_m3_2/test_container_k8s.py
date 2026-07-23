#!/usr/bin/env python3
"""
Empirical Test Suite 2: Containerization & Kubernetes Manifest Validation
Empirically tests container permissions, device node access (/dev/dri, /dev/accel/accel0),
and Kubernetes deployment manifest completeness against 01_Production_Architecture.md.
"""

import os
import stat
import yaml
import re

# 1. Parse Dockerfile & docker-compose.yml from 01_Production_Architecture.md
DOCKERFILE_USER_DEF = """
RUN useradd -m -u 1000 pipelineuser && \\
    mkdir -p /app/data /tmp/promptbook_scratch && \\
    chown -R pipelineuser:pipelineuser /app /tmp/promptbook_scratch
USER pipelineuser
"""

DOCKER_COMPOSE_SPEC = """
services:
  dsa-video-pipeline:
    container_name: dsa_video_pipeline_prod
    devices:
      - "/dev/dri/renderD128:/dev/dri/renderD128"
      - "/dev/accel/accel0:/dev/accel/accel0"
    security_opt:
      - seccomp:unconfined
"""

K8S_MANIFEST_SPEC = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dsa-pipeline-worker
spec:
  template:
    spec:
      containers:
      - name: pipeline-worker
        image: dsa-video-pipeline:2.0.0
        resources:
          limits:
            cpu: "14"
            memory: "24Gi"
            gpu.intel.com/i915: "1"
          requests:
            cpu: "8"
            memory: "12Gi"
            gpu.intel.com/i915: "1"
        volumeMounts:
        - name: data-volume
          mountPath: /app/data
        - name: scratch-volume
          mountPath: /tmp/promptbook_scratch
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: dsa-pipeline-data-pvc
      - name: scratch-volume
        emptyDir:
          medium: Memory
          sizeLimit: 4Gi
"""

def test_container_permissions_and_device_nodes():
    print("=== TEST 2.1: Docker Container Device Node Permission & User Groups ===")
    
    # Check if unprivileged pipelineuser has supplementary groups in Dockerfile
    has_video_group = "video" in DOCKERFILE_USER_DEF or "usermod -aG" in DOCKERFILE_USER_DEF
    has_render_group = "render" in DOCKERFILE_USER_DEF
    has_group_add = "group_add:" in DOCKER_COMPOSE_SPEC
    
    print(f"Dockerfile user setup checks:")
    print(f"  User creation: UID 1000 ('pipelineuser')")
    print(f"  Added to 'render'/'video' groups in Dockerfile: {has_render_group or has_video_group}")
    print(f"  'group_add' configured in docker-compose.yml: {has_group_add}")
    
    # Inspect real host device node permissions if present or analyze standard permissions
    dev_dri_path = "/dev/dri/renderD128"
    dev_accel_path = "/dev/accel/accel0"
    
    dri_exists = os.path.exists(dev_dri_path)
    accel_exists = os.path.exists(dev_accel_path)
    
    print(f"\nHost Device Node Inspection:")
    print(f"  {dev_dri_path} exists on host: {dri_exists}")
    print(f"  {dev_accel_path} exists on host: {accel_exists}")
    
    if not (has_render_group or has_video_group or has_group_add):
        print("\n❌ CRITICAL DEFECT: Container switches to unprivileged 'pipelineuser' (UID 1000) WITHOUT 'render', 'video', or 'accel' group membership or 'group_add' in docker-compose.")
        print("  Impact: When mounted via `/dev/dri/renderD128` or `/dev/accel/accel0`, UID 1000 will receive EACCES (Permission Denied) on Linux device nodes owned by root:render / root:video (mode 0660). Intel Arc GPU hardware acceleration & OpenVINO NPU will silently fail!")

def test_k8s_manifest_device_omissions():
    print("\n=== TEST 2.2: Kubernetes Manifest Device Mounts & Resource Request Completeness ===")
    parsed = yaml.safe_load(K8S_MANIFEST_SPEC)
    container_spec = parsed["spec"]["template"]["spec"]["containers"][0]
    volume_mounts = [m["mountPath"] for m in container_spec.get("volumeMounts", [])]
    resources_limits = container_spec.get("resources", {}).get("limits", {})
    resources_requests = container_spec.get("resources", {}).get("requests", {})
    
    print("Kubernetes Manifest Analysis:")
    print(f"  Volume Mounts: {volume_mounts}")
    print(f"  Resource Limits: {resources_limits}")
    print(f"  Resource Requests: {resources_requests}")
    
    dri_mounted = any("/dev/dri" in vm for vm in volume_mounts)
    accel_mounted = any("/dev/accel" in vm for vm in volume_mounts)
    npu_resource_requested = any("npu" in k.lower() or "accel" in k.lower() for k in resources_limits.keys())
    security_context = container_spec.get("securityContext", {})
    is_privileged = security_context.get("privileged", False)
    
    print("\nDevice Mount & Resource Check:")
    print(f"  /dev/dri mounted: {dri_mounted}")
    print(f"  /dev/accel/accel0 mounted: {accel_mounted}")
    print(f"  NPU resource requested in K8s limits: {npu_resource_requested}")
    print(f"  Privileged securityContext enabled: {is_privileged}")
    
    if not accel_mounted and not npu_resource_requested and not is_privileged:
        print("\n❌ CRITICAL DEFECT: Kubernetes manifest COMPLETELY OMITS Intel AI Boost NPU device pass-through!")
        print("  - `/dev/accel/accel0` device path is NOT mounted as volume or hostPath.")
        print("  - No NPU K8s device plugin resource (e.g. `accel.intel.com/npu`) is declared in limits/requests.")
        print("  Impact: In Kubernetes, OpenVINO Kokoro TTS (Phase 08) will fail with `DeviceNotFound: NPU device /dev/accel/accel0 unavailable`.")

    if not dri_mounted and "gpu.intel.com/i915" in resources_limits:
        print("\n⚠️ HIGH DEFECT: K8s GPU pass-through relies solely on `gpu.intel.com/i915` resource request without explicit `/dev/dri` hostPath mount or Intel GPU device plugin daemonset specification.")
        print("  Impact: If the host uses the modern Intel `xe` DRM driver (Ubuntu 25.10 kernel 6.11+ uses `xe` driver for Arc Xe LPG, resource name `gpu.intel.com/xe` or device `/dev/dri/renderD128`), `gpu.intel.com/i915` will fail to schedule or mount renderD128.")

if __name__ == "__main__":
    test_container_permissions_and_device_nodes()
    test_k8s_manifest_device_omissions()
