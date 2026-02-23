"""
OpenTelemetry bootstrap — call setup_tracing() once at app startup.

Exporter: OTLP/HTTP → Jaeger (or any OTLP-compatible backend).
If the OTLP endpoint is not configured or the SDK is unavailable, all
OTel calls fall back to a no-op tracer so the app keeps running.

Environment variables:
  OTEL_ENABLED           : "true" to enable (default: "false")
  OTEL_SERVICE_NAME      : service name shown in Jaeger (default: "ai-lead-agent")
  OTEL_EXPORTER_OTLP_ENDPOINT : full URL of the OTLP/HTTP collector
                                 (default: "http://jaeger:4318")
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

_tracer = None
_NOOP_SPAN = None


def _noop_span():
    """Return a no-op context manager that does nothing."""
    from contextlib import nullcontext
    return nullcontext()


def setup_tracing(app=None) -> None:
    """
    Initialise the global TracerProvider and optionally instrument FastAPI
    and SQLAlchemy.  Safe to call multiple times (idempotent).
    """
    global _tracer

    enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    if not enabled:
        logger.debug("OpenTelemetry disabled (OTEL_ENABLED != true)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        service_name = os.getenv("OTEL_SERVICE_NAME", "ai-lead-agent")
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(provider)

        _tracer = trace.get_tracer(service_name)
        logger.info(
            "OpenTelemetry tracing enabled — service=%r endpoint=%r",
            service_name, endpoint,
        )

        # ── FastAPI auto-instrumentation ──────────────────────────────────────
        if app is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                FastAPIInstrumentor.instrument_app(app)
                logger.info("FastAPI OTel instrumentation enabled")
            except Exception as exc:
                logger.warning("FastAPI OTel instrumentation failed: %s", exc)

        # ── SQLAlchemy auto-instrumentation ───────────────────────────────────
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy OTel instrumentation enabled")
        except Exception as exc:
            logger.warning("SQLAlchemy OTel instrumentation failed: %s", exc)

    except Exception as exc:
        logger.warning(
            "OpenTelemetry setup failed — tracing disabled: %s", exc
        )
        _tracer = None


# ── Manual span helper ────────────────────────────────────────────────────────

def get_tracer():
    """Return the configured tracer (may be None if OTel is disabled)."""
    return _tracer


@contextmanager
def trace_span(name: str, attributes: dict | None = None) -> Generator:
    """
    Context manager that creates a named span if tracing is enabled,
    otherwise does nothing.  Always safe to use.

    Usage:
        with trace_span("llm.generate", {"provider": "gemini"}) as span:
            result = await provider.generate(...)
    """
    tracer = _tracer
    if tracer is None:
        yield None
        return

    try:
        from opentelemetry import trace
        with tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            yield span
    except Exception:
        # Never let OTel crash the caller
        yield None
