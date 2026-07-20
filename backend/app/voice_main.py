"""
ASGI entrypoint for the dedicated Pipecat voice-agent service.

docker-compose's ``voice-agent`` service runs ``uvicorn app.voice_main:app``.
It reuses the main FastAPI application so the Pipecat routes — including the
Twilio audio WebSocket (``/api/v1/calls/pipecat/ws/{voice_call_id}``) and the
status / TwiML webhooks — are served identically to the primary backend.

Running voice pipelines in a separate horizontally-scalable process keeps
long-lived call tasks off the request-serving backend. Because it is the same
app object, no routes drift between the two services.
"""
from app.main import app

__all__ = ["app"]
