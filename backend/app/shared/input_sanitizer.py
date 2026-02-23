"""
Chat input sanitizer.

Validates and sanitizes user messages before they reach the LLM.
Applied as the first step in ChatOrchestratorService to prevent:
  - Prompt injection attacks
  - Excessively long inputs that waste tokens
  - Control characters that break JSON / log parsing

Usage:
    from app.shared.input_sanitizer import sanitize_chat_input, InputSanitizationError

    try:
        clean = sanitize_chat_input(raw_message)
    except InputSanitizationError as e:
        # Return 400 to the client
        raise HTTPException(status_code=400, detail=str(e))
"""
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = 1000  # characters — sufficient for any legitimate lead message

# Patterns that strongly indicate a prompt injection attempt.
# Each tuple is (pattern_regex, description).
# Patterns are case-insensitive and match anywhere in the message.
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Classic override attempts
    (r"ignore\s+(all\s+)?previous\s+instructions?", "override previous instructions"),
    (r"forget\s+(all\s+)?(previous\s+)?instructions?", "forget instructions"),
    (r"disregard\s+(all\s+)?previous", "disregard previous"),
    # Role / persona hijacking
    (r"you\s+are\s+now\s+(a\s+)?(?!sofía|sofia|an?\s+assistant)", "role reassignment"),
    (r"act\s+as\s+(if\s+you\s+are\s+)?(a\s+)?(?!an?\s+assistant|sofía|sofia)", "act-as attack"),
    (r"new\s+persona", "persona override"),
    (r"pretend\s+you\s+(are|were)", "pretend attack"),
    # System / instruction injection markers
    (r"\[system\]", "system tag injection"),
    (r"<\s*system\s*>", "XML system tag"),
    (r"\[inst\]", "instruction tag"),
    (r"<<SYS>>", "llama system tag"),
    # Data exfiltration probes
    (r"(print|show|reveal|display|output)\s+(your\s+)?(system\s+)?prompt", "prompt exfiltration"),
    (r"what\s+(is\s+your|are\s+your)\s+(system\s+)?prompt", "prompt exfiltration"),
    (r"repeat\s+everything\s+(above|before)", "repeat-above attack"),
    (r"tell\s+me\s+your\s+(instructions?|rules?|guidelines?)", "rules exfiltration"),
    # Privilege escalation
    (r"admin\s+(mode|access|password|credentials?)", "admin escalation"),
    (r"developer\s+mode", "developer mode bypass"),
    (r"jailbreak", "jailbreak attempt"),
    (r"DAN\b", "DAN jailbreak"),
    # Separator injection (commonly used to break context)
    (r"---+\s*(SYSTEM|HUMAN|ASSISTANT|USER)\s*---+", "separator injection"),
]

# Compile patterns once at module load
_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE | re.DOTALL), description)
    for pattern, description in _INJECTION_PATTERNS
]


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class InputSanitizationError(ValueError):
    """Raised when the input fails sanitization checks."""

    def __init__(self, message: str, reason_code: str):
        super().__init__(message)
        self.reason_code = reason_code


# ---------------------------------------------------------------------------
# Sanitization result
# ---------------------------------------------------------------------------

@dataclass
class SanitizedMessage:
    """Holds the cleaned message and any metadata about transformations."""
    text: str
    original_length: int
    was_stripped: bool  # True if leading/trailing whitespace was removed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize_chat_input(
    message: str,
    max_length: int = MAX_MESSAGE_LENGTH,
    source: Optional[str] = None,
) -> SanitizedMessage:
    """
    Validate and clean a user chat message.

    Steps:
      1. Type check
      2. Strip unicode control characters (keep newlines / tabs)
      3. Length check (after stripping)
      4. Injection pattern detection

    Args:
        message:    Raw user input.
        max_length: Maximum allowed character length (default 1000).
        source:     Optional label for log context (e.g. "telegram", "webchat").

    Returns:
        SanitizedMessage with the cleaned text.

    Raises:
        InputSanitizationError: If the message fails any check.
    """
    if not isinstance(message, str):
        raise InputSanitizationError(
            "El mensaje debe ser texto.", reason_code="invalid_type"
        )

    original_length = len(message)

    # Step 1: Remove unicode control characters (keep \n, \r, \t)
    cleaned = _strip_control_characters(message)

    # Step 2: Strip leading / trailing whitespace
    stripped = cleaned.strip()
    was_stripped = stripped != message

    # Step 3: Empty message check
    if not stripped:
        raise InputSanitizationError(
            "El mensaje no puede estar vacío.", reason_code="empty_message"
        )

    # Step 4: Length check
    if len(stripped) > max_length:
        raise InputSanitizationError(
            f"El mensaje es demasiado largo. Máximo {max_length} caracteres.",
            reason_code="too_long",
        )

    # Step 5: Injection pattern detection
    detected = _detect_injection(stripped)
    if detected:
        logger.warning(
            "[InputSanitizer] Possible prompt injection detected",
            extra={
                "source": source or "unknown",
                "pattern_matched": detected,
                "message_preview": stripped[:80],
            },
        )
        raise InputSanitizationError(
            "Mensaje no permitido. Por favor, escríbenos en qué podemos ayudarte.",
            reason_code="injection_detected",
        )

    return SanitizedMessage(
        text=stripped,
        original_length=original_length,
        was_stripped=was_stripped,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_control_characters(text: str) -> str:
    """
    Remove unicode control characters while preserving:
      - Regular whitespace (space, tab, newline, carriage return)
      - All printable characters
    """
    allowed_control = {"\n", "\r", "\t"}

    def _keep(char: str) -> bool:
        if char in allowed_control:
            return True
        category = unicodedata.category(char)
        # Cc = control, Cf = format, Cs = surrogate
        return category not in ("Cc", "Cf", "Cs")

    return "".join(c for c in text if _keep(c))


def _detect_injection(text: str) -> Optional[str]:
    """
    Check text against known injection patterns.
    Returns the description of the first match, or None.
    """
    for pattern, description in _COMPILED_PATTERNS:
        if pattern.search(text):
            return description
    return None
