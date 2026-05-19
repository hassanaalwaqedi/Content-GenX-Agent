import urllib.request, json

r = urllib.request.urlopen("http://localhost:8000/connectors/health")
d = json.loads(r.read())

for name, info in d["connectors"].items():
    status = info["status"]
    err = info.get("error_message", "")
    creds = info.get("credentials_configured", False)
    print(f"  {name:12s} => {status:10s} | creds={creds} | {err}")

print(f"\nAvailable: {d['available']}")
