"""
test_youtube_quota_calculator.py
Empirical quota arithmetic and failure simulation for YouTube Data API v3 publishing during batch processing.
"""

def test_youtube_quota_limit():
    DEFAULT_DAILY_QUOTA = 10000  # Default Google API Console daily quota
    
    # Official API Quota costs per call:
    VIDEO_INSERT_UNITS = 1600
    VIDEO_UPDATE_UNITS = 50
    THUMBNAIL_SET_UNITS = 50
    
    UNITS_PER_VIDEO = VIDEO_INSERT_UNITS + VIDEO_UPDATE_UNITS + THUMBNAIL_SET_UNITS
    
    TARGET_BATCH_VIDEOS = 60
    
    max_uploadable_videos = DEFAULT_DAILY_QUOTA // UNITS_PER_VIDEO
    total_quota_required = TARGET_BATCH_VIDEOS * UNITS_PER_VIDEO
    quota_deficit = total_quota_required - DEFAULT_DAILY_QUOTA
    
    print("=== YOUTUBE DATA API V3 QUOTA ANALYSIS ===")
    print(f"Default Daily API Quota Allocation: {DEFAULT_DAILY_QUOTA:,} units")
    print(f"API Quota Cost per Video Upload (Insert + Metadata + Thumbnail): {UNITS_PER_VIDEO:,} units")
    print(f"Maximum Videos Uploadable per Day on Default Quota: {max_uploadable_videos} videos")
    print(f"Target 12-Hour Batch Size: {TARGET_BATCH_VIDEOS} videos")
    print(f"Total Quota Required for Batch: {total_quota_required:,} units")
    print(f"Quota Deficit: {quota_deficit:,} units ({total_quota_required / DEFAULT_DAILY_QUOTA:.1f}x limit)")
    
    print("\n--- SIMULATING BATCH PUBLISHING UNTIL QUOTA EXHAUSTION ---")
    current_quota = DEFAULT_DAILY_QUOTA
    uploaded = 0
    failed_quota = 0
    
    for v in range(1, TARGET_BATCH_VIDEOS + 1):
        if current_quota >= UNITS_PER_VIDEO:
            current_quota -= UNITS_PER_VIDEO
            uploaded += 1
        else:
            failed_quota += 1
            
    print(f"Videos Uploaded Successfully: {uploaded}")
    print(f"Videos Failed due to HTTP 403 quotaExceeded: {failed_quota}")

if __name__ == "__main__":
    test_youtube_quota_limit()
