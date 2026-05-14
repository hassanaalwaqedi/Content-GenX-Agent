import requests, json, time

base = "http://127.0.0.1:8000"

# First get a video ID
print("Fetching a video...")
r = requests.get(f"{base}/videos/top?days=365&limit=1")
videos = r.json().get("videos", [])
if not videos:
    print("No videos found!")
    exit(1)

vid = videos[0]
print(f"Video: {vid['title'][:60]}")
print(f"ID: {vid['video_id']}")

# Test AI generate
print("\nCalling /ai/generate-content...")
start = time.time()
r = requests.post(f"{base}/ai/generate-content", json={
    "video_id": vid["video_id"],
    "platform": "youtube",
    "tone": "professional"
})
elapsed = time.time() - start
print(f"Status: {r.status_code} ({elapsed:.1f}s)")

if r.status_code == 200:
    d = r.json()
    print(f"\nIdea: {d.get('idea', '')[:100]}")
    print(f"Titles: {d.get('titles', [])}")
    print(f"Hooks: {[h[:50] for h in d.get('hooks', [])]}")
    print(f"Script length: {len(d.get('script', ''))} chars")
    print(f"Audience: {d.get('target_audience', '')[:80]}")
    print(f"Hashtags: {d.get('hashtags', [])}")
    print(f"Source: {d.get('source')}")
    print(f"Cached: {d.get('cached')}")
    
    # Test cache
    print("\nTesting cache...")
    start2 = time.time()
    r2 = requests.post(f"{base}/ai/generate-content", json={
        "video_id": vid["video_id"],
        "platform": "youtube",
        "tone": "professional"
    })
    elapsed2 = time.time() - start2
    print(f"Cached status: {r2.status_code} ({elapsed2:.1f}s)")
    print(f"Cached flag: {r2.json().get('cached')}")
else:
    print(f"Error: {r.text[:300]}")
