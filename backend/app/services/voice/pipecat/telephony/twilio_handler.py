"""
TwilioHandler — initiates and controls Twilio SIP calls for Pipecat pipelines.

Uses Twilio REST API (twilio-python) to:
- Initiate outbound calls (autonomous / handoff modes)
- Transfer calls mid-session via SIP REFER
- End calls programmatically
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape, quoteattr as _xml_attr

logger = logging.getLogger(__name__)

# E.164: leading +, 8-15 digits. Reject anything else before it reaches TwiML.
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def _validate_e164(number: str) -> str:
    if not number or not _E164_RE.match(number):
        raise ValueError(f"invalid E.164 phone number: {number!r}")
    return number


class TwilioHandler:
    """Thin wrapper around the Twilio REST client for voice call control."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> None:
        self._account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self._auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self._from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self._account_sid, self._auth_token)
            except ImportError:
                raise ImportError("twilio package not installed. Run: pip install twilio")
        return self._client

    async def initiate_call(
        self,
        to_number: str,
        websocket_url: str,
        status_callback_url: Optional[str] = None,
    ) -> str:
        """
        Place an outbound call that streams audio to the Pipecat WebSocket.

        Returns the Twilio call_sid.
        """
        import asyncio
        client = self._get_client()

        _validate_e164(to_number)
        twiml = (
            f"<Response><Connect><Stream url={_xml_attr(websocket_url)}/>"
            f"</Connect></Response>"
        )

        call = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.calls.create(
                to=to_number,
                from_=self._from_number,
                twiml=twiml,
                status_callback=status_callback_url,
                status_callback_method="POST",
            ),
        )
        logger.info("[TwilioHandler] call initiated call_sid=%s to=%s", call.sid, to_number)
        return call.sid

    async def transfer_call(self, call_sid: str, to_number: str) -> bool:
        """
        Transfer an active call to a human agent via SIP REFER.

        The lead stays connected; the AI is removed from the call.
        """
        import asyncio
        client = self._get_client()
        sip_domain = os.getenv("TWILIO_SIP_DOMAIN", "")

        _validate_e164(to_number)
        twiml = (
            f"<Response><Dial><Number>{_xml_escape(to_number)}</Number>"
            f"</Dial></Response>"
        )

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.calls(call_sid).update(twiml=twiml),
            )
            logger.info("[TwilioHandler] call transferred call_sid=%s to=%s", call_sid, to_number)
            return True
        except Exception as exc:
            logger.error("[TwilioHandler] transfer failed: %s", exc)
            return False

    async def end_call(self, call_sid: str) -> bool:
        """Terminate an active call."""
        import asyncio
        client = self._get_client()

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.calls(call_sid).update(status="completed"),
            )
            logger.info("[TwilioHandler] call ended call_sid=%s", call_sid)
            return True
        except Exception as exc:
            logger.error("[TwilioHandler] end_call failed: %s", exc)
            return False
