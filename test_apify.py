from connectors.registry import ConnectorRegistry

ConnectorRegistry.reset_singleton()
r = ConnectorRegistry()
avail = r.get_available()
print(f"Available connectors: {avail}")

h = r.health_check_all()
for platform, health in h.items():
    print(f"  {platform}: {health.status} ({health.latency_ms}ms) {health.error_message}")
