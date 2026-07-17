from __future__ import annotations

from types import SimpleNamespace

from core import database
from pipeline import runner


def test_pipeline_records_a_failed_preflight_and_releases_its_lock(isolated_database, monkeypatch) -> None:
    config_id = database.save_pipeline_config(
        {
            "name": "Missing YouTube credential",
            "regions": ["US"],
            "platforms": ["youtube"],
            "categories": [],
            "keywords": [],
            "content_type": "all",
            "is_preset": False,
        }
    )
    monkeypatch.setattr(runner, "get_settings", lambda: SimpleNamespace(youtube_api_key=""))

    result = runner.run_pipeline(triggered_by="test", config_id=config_id)
    history = database.get_pipeline_history(limit=1)

    assert result["status"] == "failed"
    assert "YOUTUBE_API_KEY" in result["error"]
    assert history[0]["status"] == "failed"
    assert database.is_pipeline_running() is False
