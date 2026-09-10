"""
ASGI entrypoint for the dedicated Pipecat voice-agent service.

docker-compose's ``voice-agent`` service runs ``uvicorn app.voice_main:app``.
It reuses the main FastAPI application so the Pipecat routes — including the
Twilio audio WebSocket (``/api/v1/calls/pipecat/ws/{voice_call_id}``) and the
status / TwiML webhooks — are served identically to the primary backend.

Running voice pipelines in a separate horizontally-scalable process keeps
long-lived call tasks off the request-serving backend. Because it is the same
app object, no routes drift between the two services.

── CPU / concurrency tuning ────────────────────────────────────────────────
The per-frame ML work in the voice pipeline (Silero VAD in PyTorch; SmartTurn
in ONNX when enabled) defaults to spawning threads across *every* core per
inference. Under concurrent calls those threads thrash and audio latency
spikes. We pin each inference to a single thread so N Uvicorn workers can each
own a core cleanly — throughput scales with ``--workers`` instead of collapsing
onto one saturated core. Env vars are set before torch/onnxruntime load their
native libs; ``torch.set_num_threads`` covers the runtime knob too.
"""
import os

# Must be set before torch / onnxruntime import their OpenMP/MKL runtimes.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

try:
    import torch

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except Exception:  # torch absent or interop already fixed post-init — non-fatal
    pass

from app.main import app

__all__ = ["app"]
