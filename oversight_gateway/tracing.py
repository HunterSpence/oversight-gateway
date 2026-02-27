"""OpenTelemetry tracing configuration"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from typing import Optional
import structlog

logger = structlog.get_logger()


def setup_tracing(service_name: str = "oversight-gateway", otlp_endpoint: Optional[str] = None) -> None:
    """
    Configure OpenTelemetry tracing for the application.
    
    Args:
        service_name: Name of the service for tracing
        otlp_endpoint: OTLP endpoint (e.g., "http://localhost:4317")
    """
    logger.info("setting_up_tracing", service_name=service_name, endpoint=otlp_endpoint)
    
    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            processor = BatchSpanProcessor(otlp_exporter)
            provider.add_span_processor(processor)
            logger.info("otlp_exporter_configured", endpoint=otlp_endpoint)
        except Exception as e:
            logger.warning("failed_to_configure_otlp", error=str(e))
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    
    # Instrument HTTPX for outgoing requests
    HTTPXClientInstrumentor().instrument()
    
    logger.info("tracing_configured")


def instrument_app(app) -> None:
    """
    Instrument FastAPI application with automatic tracing.
    
    Args:
        app: FastAPI application instance
    """
    FastAPIInstrumentor.instrument_app(app)
    logger.info("fastapi_instrumented")


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Get a tracer instance"""
    return trace.get_tracer(name)
