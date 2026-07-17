from api.api import app


def test_reddit_read_routes_are_registered_from_the_router() -> None:
    paths = {route.path for route in app.routes}
    assert {
        "/platforms/reddit/overview",
        "/platforms/reddit/discussions/emerging",
        "/platforms/reddit/health",
        "/platforms/reddit/scan",
    } <= paths


def test_creator_routes_are_registered_from_the_router() -> None:
    paths = {route.path for route in app.routes}
    assert {
        "/creators/top",
        "/creators/intelligence",
        "/creators/rising",
        "/creators/by-trend",
        "/creators/{channel}/videos",
    } <= paths


def test_system_and_dataset_routes_are_registered_from_focused_routers() -> None:
    paths = {route.path for route in app.routes}
    assert {
        "/health",
        "/connectors/health",
        "/stats",
        "/stats/transcripts",
        "/datasets",
        "/datasets/active",
        "/datasets/{run_id}/activate",
    } <= paths


def test_video_routes_are_registered_from_the_router() -> None:
    paths = {route.path for route in app.routes}
    assert {
        "/videos/top",
        "/videos/trending",
        "/videos/{video_id}",
        "/videos/{video_id}/transcript",
    } <= paths
