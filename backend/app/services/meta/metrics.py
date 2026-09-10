"""Low-cardinality operational metrics for Meta integrations."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

try:
    from prometheus_client import Counter, Histogram
except ImportError:  # pragma: no cover
    Counter = Histogram = None


logger = logging.getLogger(__name__)


def endpoint_family(path: str) -> str:
    parsed = urlparse(path)
    parts = [part for part in parsed.path.split("/") if part]
    known = (
        "messages", "insights", "campaigns", "adsets", "ads", "adcreatives",
        "leadgen", "leads", "leadgen_forms", "debug_token", "subscribed_apps",
        "accounts", "owned_whatsapp_business_accounts", "client_whatsapp_business_accounts",
    )
    for family in known:
        if family in parts:
            return family
    return "other"


if Counter:
    meta_graph_requests_total = Counter(
        "meta_graph_requests_total",
        "Meta Graph API calls",
        ["method", "endpoint", "result"],
    )
    meta_webhook_events_total = Counter(
        "meta_webhook_events_total",
        "Meta webhook events accepted by the durable inbox",
        ["provider", "event_type", "result"],
    )
    meta_outbound_messages_total = Counter(
        "meta_outbound_messages_total",
        "Outbound Meta messages",
        ["channel", "message_type", "result"],
    )
    meta_sync_runs_total = Counter(
        "meta_sync_runs_total",
        "Meta scheduled synchronization results",
        ["sync_type", "result"],
    )
    meta_legacy_fallback_total = Counter(
        "meta_legacy_fallback_total",
        "Legacy WhatsApp routing decisions during Meta rollout",
        ["direction", "reason", "result"],
    )
    meta_graph_latency_seconds = Histogram(
        "meta_graph_latency_seconds",
        "Meta Graph API request latency",
        ["method", "endpoint"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
    )
    meta_webhook_processing_seconds = Histogram(
        "meta_webhook_processing_seconds",
        "Time to normalize and persist a Meta webhook",
        ["provider", "result"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
    )
else:  # pragma: no cover
    meta_graph_requests_total = None
    meta_webhook_events_total = None
    meta_outbound_messages_total = None
    meta_sync_runs_total = None
    meta_legacy_fallback_total = None
    meta_graph_latency_seconds = None
    meta_webhook_processing_seconds = None


def record_graph(method: str, path: str, result: str, seconds: float) -> None:
    family = endpoint_family(path)
    if meta_graph_requests_total:
        meta_graph_requests_total.labels(method=method.upper(), endpoint=family, result=result).inc()
    if meta_graph_latency_seconds:
        meta_graph_latency_seconds.labels(method=method.upper(), endpoint=family).observe(seconds)


def record_webhook(provider: str, event_type: str, result: str) -> None:
    if meta_webhook_events_total:
        meta_webhook_events_total.labels(provider=provider, event_type=event_type, result=result).inc()


def record_outbound(channel: str, message_type: str, result: str) -> None:
    if meta_outbound_messages_total:
        meta_outbound_messages_total.labels(channel=channel, message_type=message_type, result=result).inc()


def record_sync(sync_type: str, result: str) -> None:
    if meta_sync_runs_total:
        meta_sync_runs_total.labels(sync_type=sync_type, result=result).inc()


def record_legacy_fallback(direction: str, reason: str, result: str) -> None:
    """Record one low-cardinality legacy-routing decision without tenant data."""
    logger.info(
        "Meta legacy fallback decision direction=%s reason=%s result=%s",
        direction,
        reason,
        result,
    )
    if meta_legacy_fallback_total:
        meta_legacy_fallback_total.labels(
            direction=direction,
            reason=reason,
            result=result,
        ).inc()
