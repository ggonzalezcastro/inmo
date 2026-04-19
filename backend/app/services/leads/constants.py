"""Constants for the leads service.

Currently focused on the response-time / engagement signals used to detect
"interesado / fast responder" leads. Kept separate from broker-overridable
config because these are global heuristics applied uniformly across tenants.
"""

# Average bot→lead reply turnaround (seconds) under which a lead is
# considered a fast responder.
FAST_RESPONSE_THRESHOLD_SECONDS: int = 60

# Minimum number of recorded lead replies before we are willing to call the
# lead a "fast responder". Avoids tagging leads that have only sent one or two
# messages by accident.
FAST_RESPONSE_MIN_REPLIES: int = 3

# Tag applied to ``Lead.tags`` when the lead meets the fast-responder
# criteria.
FAST_RESPONDER_TAG: str = "respuesta_rapida"
