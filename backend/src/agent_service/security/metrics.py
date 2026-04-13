"""Prometheus metrics for security controls."""

from __future__ import annotations

import os
import re

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

PROMETHEUS_MULTIPROC_DIR = os.getenv("PROMETHEUS_MULTIPROC_DIR", "").strip()

_DYNAMIC_SEGMENT_RE = re.compile(
    r"^(?:\d+|[0-9a-fA-F]{8,}|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}|[A-Za-z0-9_-]{24,})$"
)
_KNOWN_METRIC_PATH_ROOTS = {
    "agent",
    "eval",
    "graphql",
    "health",
    "metrics",
    "rate-limit",
    "live",
    "admin",
    "sessions",
    "models",
    "follow-up",
    "router",
}

TOR_BLOCKS_TOTAL = Counter(
    "tor_blocks_total",
    "Total requests blocked because client IP is a Tor exit node.",
    labelnames=("path_pattern",),
)

TOR_MONITORED_TOTAL = Counter(
    "tor_monitored_total",
    "Total requests observed from Tor IPs on monitored-only paths.",
    labelnames=("path_pattern",),
)

TOR_EXIT_NODES_COUNT = Gauge(
    "tor_exit_nodes_count",
    "Current number of Tor exit node IPs loaded in memory.",
    multiprocess_mode="livemax",
)

TOR_LIST_REFRESH_DURATION_SECONDS = Histogram(
    "tor_list_refresh_duration_seconds",
    "Duration of Tor exit list refresh operations.",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30),
)

TOR_LIST_REFRESH_FAILURES_TOTAL = Counter(
    "tor_list_refresh_failures_total",
    "Total failed Tor exit list refresh operations.",
)

TOR_LIST_STALENESS_SECONDS = Gauge(
    "tor_list_staleness_seconds",
    "Age in seconds of the currently loaded Tor exit node set.",
    multiprocess_mode="livemax",
)

SESSION_RISK_SCORE = Histogram(
    "session_risk_score",
    "Risk scores produced by session security validator.",
    labelnames=("decision",),
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

SESSION_DECISIONS_TOTAL = Counter(
    "session_decisions_total",
    "Count of session security outcomes.",
    labelnames=("decision",),
)

SESSION_IMPOSSIBLE_TRAVEL_TOTAL = Counter(
    "session_impossible_travel_total",
    "Count of impossible-travel detections.",
)

SESSION_CONCURRENT_IP_HIGH_RISK_TOTAL = Counter(
    "session_concurrent_ip_high_risk_total",
    "Count of high-risk concurrent IP detections.",
)

SESSION_DEVICE_MISMATCH_TOTAL = Counter(
    "session_device_mismatch_total",
    "Count of detected device fingerprint mismatches.",
)

SESSION_GEO_ANOMALY_TOTAL = Counter(
    "session_geo_anomaly_total",
    "Count of geographic anomaly detections.",
)


def export_prometheus_metrics() -> tuple[bytes, str]:
    """Render all registered Prometheus metrics."""
    if PROMETHEUS_MULTIPROC_DIR:
        try:
            # Kwarg added in prometheus_client>=0.21; older builds raise TypeError,
            # and the installed stub may not list it — hence the type-ignore.
            registry = CollectorRegistry(support_collectors_without_names=True)  # type: ignore[call-arg]
        except TypeError:
            # Backward compatibility for older prometheus_client builds.
            registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST


def normalize_path_for_metrics(raw_path: str, route_path: str | None = None) -> str:
    """
    Create a bounded path label for metrics.

    Prefer FastAPI route templates (e.g. /agent/config/{session_id}) when available.
    For unmatched routes, collapse to a constrained prefix representation.
    """
    if route_path:
        return route_path

    if not raw_path:
        return "/unmatched_route"
    if raw_path == "/":
        return "/"
    if not raw_path.startswith("/"):
        raw_path = f"/{raw_path}"

    segments = [segment for segment in raw_path.split("/") if segment]
    if not segments:
        return "/"

    root = segments[0].lower()
    if root not in _KNOWN_METRIC_PATH_ROOTS:
        return "/unmatched_route"

    normalized_segments = [root]
    for segment in segments[1:4]:
        candidate = segment.strip()
        if not candidate:
            continue
        if _DYNAMIC_SEGMENT_RE.fullmatch(candidate):
            normalized_segments.append("{id}")
        else:
            normalized_segments.append(candidate.lower())

    if len(segments) > 4:
        normalized_segments.append("{tail}")

    return "/" + "/".join(normalized_segments)
