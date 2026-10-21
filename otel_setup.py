import os
from urllib.parse import urlparse

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader


def _grpc_endpoint(endpoint: str | None) -> str:
    """Normalize an OTLP gRPC endpoint for the Python exporter."""
    value = (endpoint or "http://localhost:4317").strip()
    if not value:
        return "localhost:4317"

    if "://" in value:
        parsed = urlparse(value)
        host = parsed.hostname or "localhost"
        port = parsed.port or 4317
        return f"{host}:{port}"

    if ":" not in value:
        return f"{value}:4317"
    return value


def setup_tracing(service_name: str = "bfsi-assistant", collector_endpoint: str | None = None):
    """Configure a traced service for local debugging or Docker-based OTLP export."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    debug_enabled = (
        os.getenv("OTEL_ENABLE_CONSOLE_EXPORTER", "false").lower() == "true"
        or not (
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        )
    )
    if debug_enabled:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    endpoint = collector_endpoint or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4317"
    grpc_endpoint = _grpc_endpoint(endpoint)

    try:
        exporter = OTLPSpanExporter(endpoint=grpc_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        print(f"Tracing enabled via OTLP gRPC collector at {grpc_endpoint}")
    except Exception as exc:  # pragma: no cover - best-effort fallback at runtime
        print(f"OTLP exporter unavailable at {grpc_endpoint}; using console exporter only. Error: {exc}")
        if not debug_enabled:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # Configure metrics (MeterProvider) to mirror the tracing configuration.
    try:
        metric_exporter = OTLPMetricExporter(endpoint=grpc_endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        print(f"Metrics enabled via OTLP gRPC collector at {grpc_endpoint}")
    except Exception as exc:  # pragma: no cover - best-effort fallback at runtime
        print(f"OTLP metric exporter unavailable at {grpc_endpoint}; metrics may be no-op. Error: {exc}")

    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(provider)

    return trace.get_tracer(service_name)


def get_meter(name: str = "bfsi-assistant"):
    """Return an OpenTelemetry Meter obtained from the global MeterProvider.

    The MeterProvider is configured inside `setup_tracing()` so callers can
    safely `get_meter()` after setup.
    """
    return metrics.get_meter(name)


if __name__ == "__main__":
    tracer = setup_tracing(service_name="bfsi-assistant-local")
    with tracer.start_as_current_span("otel_setup_smoke_test") as span:
        span.set_attribute("debug.sample", True)
        print("OpenTelemetry smoke test span created.")
