"""Prometheus metrics for security controls."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

TOR_BLOCKS_TOTAL = Counter(
    "tor_blocks_total",
    "Total requests blocked because client IP is a Tor exit node.",
    labelnames=("path",),
)

TOR_MONITORED_TOTAL = Counter(
    "tor_monitored_total",
    "Total requests observed from Tor IPs on monitored-only paths.",
    labelnames=("path",),
)

TOR_EXIT_NODES_COUNT = Gauge(
    "tor_exit_nodes_count",
    "Current number of Tor exit node IPs loaded in memory.",
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
    return generate_latest(), CONTENT_TYPE_LATEST
