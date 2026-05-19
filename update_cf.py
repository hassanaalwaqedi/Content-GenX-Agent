import json
import subprocess
import sys

# Get current config
r = subprocess.run(
    ["aws", "cloudfront", "get-distribution-config", "--id", "E74YK9JEIM72X", "--output", "json"],
    capture_output=True, text=True, shell=True
)
data = json.loads(r.stdout)
etag = data["ETag"]
cfg = data["DistributionConfig"]

# Update forwarded headers to include Authorization and Content-Type
cfg["DefaultCacheBehavior"]["ForwardedValues"]["Headers"]["Quantity"] = 5
cfg["DefaultCacheBehavior"]["ForwardedValues"]["Headers"]["Items"] = [
    "Origin",
    "Access-Control-Request-Method",
    "Access-Control-Request-Headers",
    "Authorization",
    "Content-Type",
]

with open("cf_dist_final.json", "w", encoding="utf-8") as f:
    json.dump(cfg, f)

print(f"ETag: {etag}")
print(f"Headers updated: {cfg['DefaultCacheBehavior']['ForwardedValues']['Headers']}")

# Apply update
r2 = subprocess.run(
    ["aws", "cloudfront", "update-distribution",
     "--id", "E74YK9JEIM72X",
     "--if-match", etag,
     "--distribution-config", "file://cf_dist_final.json"],
    capture_output=True, text=True, shell=True
)
if r2.returncode == 0:
    print("CloudFront updated successfully!")
else:
    print(f"Error: {r2.stderr}")
    sys.exit(1)
