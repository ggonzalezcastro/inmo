"""
Prometheus metrics for Deal operations.
Import and call these from the deal services/effects.
"""

try:
    from prometheus_client import Counter, Histogram
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False

# Counters
deals_created_total = None
deals_stage_transitions_total = None
deal_documents_uploaded_total = None
deal_time_in_stage_seconds = None

if METRICS_ENABLED:
    deals_created_total = Counter(
        "deals_created_total",
        "Total deals created",
        ["broker_id", "delivery_type"]
    )
    deals_stage_transitions_total = Counter(
        "deals_stage_transitions_total",
        "Total deal stage transitions",
        ["from_stage", "to_stage"]
    )
    deal_documents_uploaded_total = Counter(
        "deal_documents_uploaded_total",
        "Total deal documents uploaded",
        ["slot", "actor_type"]  # actor_type: "user" | "ai"
    )
    deal_time_in_stage_seconds = Histogram(
        "deal_time_in_stage_seconds",
        "Time spent in each deal stage",
        ["stage"],
        buckets=[3600, 86400, 259200, 604800, 1209600, 2592000]  # 1h, 1d, 3d, 1w, 2w, 30d
    )


def record_deal_created(broker_id: int, delivery_type: str) -> None:
    if deals_created_total:
        deals_created_total.labels(broker_id=str(broker_id), delivery_type=delivery_type).inc()


def record_stage_transition(from_stage: str, to_stage: str) -> None:
    if deals_stage_transitions_total:
        deals_stage_transitions_total.labels(from_stage=from_stage, to_stage=to_stage).inc()


def record_document_uploaded(slot: str, actor_type: str) -> None:
    if deal_documents_uploaded_total:
        deal_documents_uploaded_total.labels(slot=slot, actor_type=actor_type).inc()


def record_time_in_stage(stage: str, seconds: float) -> None:
    if deal_time_in_stage_seconds:
        deal_time_in_stage_seconds.labels(stage=stage).observe(seconds)
