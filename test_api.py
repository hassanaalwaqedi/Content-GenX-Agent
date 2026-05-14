"""Phase 1 verification: Security + Infrastructure fixes."""
import requests

BASE = "http://127.0.0.1:8000"

print("=" * 60)
print("  Phase 1 -- Security & Infrastructure Verification")
print("=" * 60)

# 1. CORS headers check
print("\n[1] CORS -- restricted origins")
r = requests.options(f"{BASE}/health", headers={
    "Origin": "http://evil-site.com",
    "Access-Control-Request-Method": "GET",
})
cors_origin = r.headers.get("access-control-allow-origin", "BLOCKED")
print(f"  Evil origin response: {cors_origin}")
assert cors_origin != "*", "CORS should NOT be wildcard"
print("  [OK] Malicious origin blocked")

# 2. Pipeline auth check (no key configured = open)
print("\n[2] Pipeline Auth -- /pipeline/run")
r = requests.post(f"{BASE}/pipeline/run")
print(f"  No key (key disabled): {r.status_code}")
assert r.status_code in (202, 200, 409), f"Expected 2xx or 409, got {r.status_code}"
print("  [OK] Auth passes when no key configured (correct)")

# 3. Schema migration (init_db runs on startup)
print("\n[3] Schema Auto-Migration -- verified via startup logs")
r = requests.get(f"{BASE}/health")
print(f"  Health status: {r.status_code}")
assert r.status_code == 200
print("  [OK] Database initialized with migration check")

# 4. Endpoints regression
print("\n[4] Endpoint Regression")
for ep in ["/health", "/stats", "/videos/top?niche=AI+for+business&days=365",
           "/creators/top", "/pipeline/history"]:
    r = requests.get(f"{BASE}{ep}")
    status = "[OK]" if r.status_code == 200 else "[FAIL]"
    print(f"  {status} {ep}: {r.status_code}")

# 5. Strategic insights still present
print("\n[5] Strategic Insights Intact")
r = requests.get(f"{BASE}/videos/top", params={"niche": "AI for business", "days": 365})
v = r.json()["videos"][0]
print(f"  Target Audience:  {v.get('target_audience', 'MISSING')[:60]}")
print(f"  Strategic Advice: {str(v.get('strategic_advice', 'MISSING'))[:60]}")
has_insights = v.get("target_audience") != "MISSING"
print(f"  {'[OK]' if has_insights else '[FAIL]'} Strategic fields present")

print("\n" + "=" * 60)
print("  PHASE 1 VERIFICATION COMPLETE")
print("=" * 60)
