"""
ApifyMixin — shared Apify actor HTTP plumbing for BaseConnector subclasses.

Eliminates the duplicated ``_get_client`` / ``run_actor_sync`` /
``run_actor_async`` code that was previously copied across
``TikTokConnector``, ``InstagramConnector`` (and would be copied again
for any future Apify-based connector such as Reddit).

Usage:
    class MyConnector(BaseConnector, ApifyMixin):
        def __init__(self):
            ...
            self._api_token = "…"
            self._actor_id  = "…"

        def health_check(self) -> ConnectorHealth:
            return self._apify_health_check("myplatform")
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from connectors.models import ConnectorHealth

_APIFY_BASE_URL = "https://api.apify.com/v2"

logger = logging.getLogger(__name__)


class ApifyMixin:
    """Mixin that adds Apify actor-run capabilities to a ``BaseConnector``.

    The host class **must**:

    *   Inherit from ``BaseConnector`` (so ``self._metrics`` and
        ``self._logger`` are available).
    *   Set ``self._api_token`` and ``self._actor_id`` before calling any
        of the methods below (typically in ``__init__``).
    """

    _api_token: str = ""
    _actor_id: str = ""
    _client: Optional[httpx.Client] = None

    # ------------------------------------------------------------------
    # HTTP client
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        """Return (or create) a shared ``httpx.Client`` for Apify API calls."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=15.0, read=310.0, write=15.0, pool=15.0,
                ),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    # ------------------------------------------------------------------
    # Synchronous actor run  (preferred)
    # ------------------------------------------------------------------

    def run_actor_sync(
        self,
        actor_input: Dict[str, Any],
        *,
        timeout_secs: int = 120,
        memory_mb: int = 256,
    ) -> List[Dict[str, Any]]:
        """
        Run the Apify actor synchronously.

        POSTs to the ``/run-sync-get-dataset-items`` endpoint which starts
        the actor, waits for completion (up to 300 seconds), and returns
        the dataset items directly.

        Falls back to :meth:`run_actor_async` if the sync endpoint
        responds with HTTP 408 (timeout).
        """
        client = self._get_client()
        url = f"{_APIFY_BASE_URL}/acts/{self._actor_id}/run-sync-get-dataset-items"

        try:
            resp = client.post(
                url,
                params={
                    "token": self._api_token,
                    "timeout": timeout_secs,
                    "memory": memory_mb,
                    "format": "json",
                },
                json=actor_input,
            )

            if resp.status_code == 408:
                self._logger.warning(
                    "Apify sync run timed out after %ds — trying async fallback",
                    timeout_secs,
                )
                return self.run_actor_async(actor_input, memory_mb=memory_mb)

            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("items", [data])
            return []

        except httpx.HTTPStatusError as exc:
            self._logger.warning(
                "Apify API error: %s %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
            self._metrics.record_request(success=False)
            return []

        except Exception as exc:
            self._logger.warning("Apify request failed: %s", exc)
            self._metrics.record_request(success=False)
            return []

    # ------------------------------------------------------------------
    # Asynchronous actor run  (fallback when sync times out)
    # ------------------------------------------------------------------

    def run_actor_async(
        self,
        actor_input: Dict[str, Any],
        *,
        memory_mb: int = 256,
        max_wait_secs: int = 180,
        poll_interval: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Run the Apify actor asynchronously with polling.

        Steps:
            1. ``POST /acts/{id}/runs`` – start the run
            2. Poll ``GET /actor-runs/{runId}`` until a terminal status
            3. ``GET /datasets/{datasetId}/items`` – fetch results
        """
        client = self._get_client()

        # -- Step 1: Start the run ----------------------------------------
        try:
            resp = client.post(
                f"{_APIFY_BASE_URL}/acts/{self._actor_id}/runs",
                params={"token": self._api_token, "memory": memory_mb},
                json=actor_input,
            )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
            run_id = run_data.get("id")
            if not run_id:
                self._logger.error("Apify async run: no run ID returned")
                return []
        except Exception as exc:
            self._logger.error("Apify async run start failed: %s", exc)
            return []

        # -- Step 2: Poll till terminal -----------------------------------
        terminal_statuses = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
        start_time = time.time()
        run_info: Dict[str, Any] = {}

        while time.time() - start_time < max_wait_secs:
            try:
                status_resp = client.get(
                    f"{_APIFY_BASE_URL}/actor-runs/{run_id}",
                    params={"token": self._api_token},
                )
                status_resp.raise_for_status()
                run_info = status_resp.json().get("data", {})
                status = run_info.get("status", "")

                if status in terminal_statuses:
                    if status != "SUCCEEDED":
                        self._logger.warning(
                            "Apify async run ended with status: %s", status
                        )
                        return []
                    break
            except Exception as exc:
                self._logger.warning("Apify status poll failed: %s", exc)

            time.sleep(poll_interval)
        else:
            self._logger.warning(
                "Apify async run did not complete within %ds", max_wait_secs
            )
            return []

        # -- Step 3: Fetch dataset items ----------------------------------
        dataset_id = run_info.get("defaultDatasetId", "")
        if not dataset_id:
            self._logger.error("Apify async run: no dataset ID")
            return []

        try:
            items_resp = client.get(
                f"{_APIFY_BASE_URL}/datasets/{dataset_id}/items",
                params={"token": self._api_token, "format": "json"},
            )
            items_resp.raise_for_status()
            data = items_resp.json()
            return data if isinstance(data, list) else []
        except Exception as exc:
            self._logger.error("Apify dataset fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Shared health check
    # ------------------------------------------------------------------

    def _apify_health_check(self, platform: str) -> ConnectorHealth:
        """
        Verify Apify token validity.

        Validates the API token via ``/v2/users/me``, then probes the
        actor endpoint (GET ``/v2/acts/{actorId}``).  Some store actors
        return 403/404 on the GET probe but still run fine via POST, so
        a failed actor probe is treated as *degraded* rather than unavailable.

        Subclasses call this from their ``health_check()`` method::

            def health_check(self) -> ConnectorHealth:
                return self._apify_health_check("myplatform")
        """
        start = time.time()

        if not self._api_token:
            return ConnectorHealth(
                platform=platform,
                status="unavailable",
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message="APIFY_API_TOKEN not configured in .env",
                credentials_configured=False,
            )

        # -- Step 1: validate the token itself --------------------------------
        try:
            client = self._get_client()
            token_resp = client.get(
                f"{_APIFY_BASE_URL}/users/me",
                params={"token": self._api_token},
            )
            if token_resp.status_code != 200:
                latency = (time.time() - start) * 1000
                return ConnectorHealth(
                    platform=platform,
                    status="unavailable",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message="Invalid or expired APIFY_API_TOKEN",
                    credentials_configured=True,
                )
        except Exception as exc:
            latency = (time.time() - start) * 1000
            return ConnectorHealth(
                platform=platform,
                status="unavailable",
                latency_ms=round(latency, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc)[:200],
                credentials_configured=bool(self._api_token),
            )

        # -- Step 2: probe actor accessibility (best-effort) ------------------
        errors: list[str] = []
        try:
            actor_resp = client.get(
                f"{_APIFY_BASE_URL}/acts/{self._actor_id}",
                params={"token": self._api_token},
            )
            if actor_resp.status_code not in (200, 201):
                errors.append(
                    f"Actor probe returned HTTP {actor_resp.status_code}"
                )
        except Exception as exc:
            errors.append(str(exc)[:100])

        latency = (time.time() - start) * 1000

        return ConnectorHealth(
            platform=platform,
            status="healthy" if not errors else "degraded",
            latency_ms=round(latency, 1),
            last_check=datetime.now(timezone.utc).isoformat(),
            error_message="; ".join(errors) if errors else "",
            credentials_configured=True,
        )
