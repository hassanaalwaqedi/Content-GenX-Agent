import requests, json

base = "http://127.0.0.1:8000"

# Test 1: Creator Intelligence
print("=== Creator Intelligence ===")
r = requests.get(f"{base}/creators/intelligence?days=365&limit=5&min_videos=1")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"Count: {d['count']}")
    for c in d.get("creators", [])[:3]:
        print(f"  {c['channel']}: dom={c.get('trend_dominance_score')}, vel={c.get('recent_velocity')}, opp={c.get('opportunity_alignment')}, topics={c.get('top_topics', [])[:3]}")
else:
    print(r.text[:300])

# Test 2: Rising Creators
print("\n=== Rising Creators ===")
r = requests.get(f"{base}/creators/rising?days=90&limit=5")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"Count: {d['count']}")
    for c in d.get("creators", [])[:3]:
        print(f"  {c['channel']}: vel={c.get('recent_velocity')}, eng={c.get('avg_engagement')}")

# Test 3: Creators by Trend
print("\n=== Creators by Trend (gaming) ===")
r = requests.get(f"{base}/creators/by-trend?trend=gaming&days=365&limit=5")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"Trend: {d['trend']}, Count: {d['count']}")

# Test 4: Creator Videos
print("\n=== Creator Videos ===")
r2 = requests.get(f"{base}/creators/intelligence?days=365&limit=1&min_videos=1")
if r2.status_code == 200 and r2.json().get("creators"):
    ch = r2.json()["creators"][0]["channel"]
    r = requests.get(f"{base}/creators/{ch}/videos?limit=3")
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"Channel: {d['channel']}, Videos: {d['count']}")
        for v in d.get("videos", [])[:2]:
            print(f"  {v['title'][:50]} - score={v.get('score')}")
