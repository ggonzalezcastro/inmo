"""
Outlook Calendar service via Microsoft Graph API.

Implements the same public interface as GoogleCalendarService so the
rest of the codebase can swap providers transparently.

Token refresh uses MSAL ConfidentialClientApplication.  Microsoft Graph
refresh tokens rotate on every use — after each successful API call the
caller must persist the (possibly new) refresh token via
`persist_outlook_token_if_rotated()`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
import logging
import pytz

import httpx
import msal

from app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH_SCOPES = ["https://graph.microsoft.com/Calendars.ReadWrite"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
CHILE_TZ = pytz.timezone("America/Santiago")


class OutlookCalendarService:
    """Microsoft Outlook / Microsoft 365 Calendar via Graph API."""

    def __init__(
        self,
        refresh_token: str,
        calendar_id: Optional[str] = None,
    ) -> None:
        self._refresh_token = refresh_token
        self.calendar_id = calendar_id  # Graph calendar ID; None → primary
        self._token_rotated: bool = False  # set True when Graph returns a new RT
        # Build the MSAL app once per service instance (not per API call)
        self._msal_app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        ) if settings.MICROSOFT_CLIENT_ID else None

    @property
    def is_ready(self) -> bool:
        """True when credentials are present and MICROSOFT_CLIENT_ID is configured."""
        return bool(self._refresh_token and self._msal_app)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Acquire a fresh access token via the stored refresh token.

        Microsoft may rotate the refresh token in the response.  When it does,
        `_token_rotated` is set to True so callers can persist the new value.
        """
        if not self._msal_app:
            raise ValueError("MICROSOFT_CLIENT_ID not configured")
        result = self._msal_app.acquire_token_by_refresh_token(
            self._refresh_token,
            scopes=GRAPH_SCOPES,
        )
        if "error" in result:
            raise ValueError(
                f"Outlook token refresh failed: {result.get('error')} — "
                f"{result.get('error_description')}"
            )
        new_rt = result.get("refresh_token")
        if new_rt and new_rt != self._refresh_token:
            self._refresh_token = new_rt
            self._token_rotated = True

        return result["access_token"]

    def _calendar_url(self) -> str:
        """Base URL for events in the configured calendar."""
        if self.calendar_id:
            return f"{GRAPH_BASE}/me/calendars/{self.calendar_id}/events"
        return f"{GRAPH_BASE}/me/events"

    # ── Public interface (mirrors GoogleCalendarService) ─────────────────────

    def create_event_with_meet(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        attendees: Optional[list] = None,
        location: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create an Outlook/Teams calendar event.

        Returns a dict with event_id, meet_url, html_link, start_time, end_time.
        Returns None on failure.

        NOTE: Teams meeting links are only available for accounts with a
        Microsoft 365 license.  Personal @outlook.com / @hotmail.com accounts
        will receive a valid event but meet_url will be None.
        """
        try:
            access_token = self._get_access_token()
        except ValueError as exc:
            logger.error("Outlook token refresh failed (create_event): %s", exc)
            return None

        # Normalise datetimes to Chile timezone then represent as ISO-8601
        if start_time.tzinfo is None:
            start_time = CHILE_TZ.localize(start_time)
        if end_time.tzinfo is None:
            end_time = CHILE_TZ.localize(end_time)

        body: Dict[str, Any] = {
            "subject": title,
            "body": {"contentType": "HTML", "content": description or ""},
            "start": {
                "dateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "America/Santiago",
            },
            "end": {
                "dateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "America/Santiago",
            },
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        }

        if attendees:
            body["attendees"] = [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendees
            ]
        if location:
            body["location"] = {"displayName": location}

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    self._calendar_url(),
                    json=body,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                event = resp.json()

            meet_url = None
            online_meeting = event.get("onlineMeeting") or {}
            meet_url = online_meeting.get("joinUrl")
            if not meet_url:
                logger.info(
                    "Teams meeting link not available (account may lack M365 license)"
                )

            logger.info("Outlook Calendar event created: %s", event.get("id"))
            return {
                "event_id": event.get("id"),
                "meet_url": meet_url,
                "html_link": event.get("webLink"),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            }

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Graph API error creating Outlook event: %s — %s",
                exc.response.status_code, exc.response.text,
            )
            return None
        except Exception as exc:
            logger.error("Unexpected error creating Outlook event: %s", exc, exc_info=True)
            return None

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        attendees: Optional[list] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an existing Outlook Calendar event via Graph PATCH."""
        try:
            access_token = self._get_access_token()
        except ValueError as exc:
            logger.error("Outlook token refresh failed (update_event): %s", exc)
            return None

        patch: Dict[str, Any] = {}
        if title is not None:
            patch["subject"] = title
        if description is not None:
            patch["body"] = {"contentType": "HTML", "content": description}
        if start_time is not None:
            if start_time.tzinfo is None:
                start_time = CHILE_TZ.localize(start_time)
            patch["start"] = {
                "dateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "America/Santiago",
            }
        if end_time is not None:
            if end_time.tzinfo is None:
                end_time = CHILE_TZ.localize(end_time)
            patch["end"] = {
                "dateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "America/Santiago",
            }
        if attendees is not None:
            patch["attendees"] = [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendees
            ]

        try:
            # Use calendar-specific URL when calendar_id is set, same as create_event
            base_url = (
                f"{GRAPH_BASE}/me/calendars/{self.calendar_id}/events/{event_id}"
                if self.calendar_id
                else f"{GRAPH_BASE}/me/events/{event_id}"
            )
            with httpx.Client(timeout=15) as client:
                resp = client.patch(
                    base_url,
                    json=patch,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                logger.info("Outlook Calendar event updated: %s", event_id)
                return resp.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Graph API error updating Outlook event %s: %s — %s",
                event_id, exc.response.status_code, exc.response.text,
            )
            return None
        except Exception as exc:
            logger.error("Unexpected error updating Outlook event %s: %s", event_id, exc, exc_info=True)
            return None

    def delete_event(self, event_id: str) -> bool:
        """Delete an Outlook Calendar event. Returns True on success."""
        try:
            access_token = self._get_access_token()
        except ValueError as exc:
            logger.error("Outlook token refresh failed (delete_event): %s", exc)
            return False

        try:
            base_url = (
                f"{GRAPH_BASE}/me/calendars/{self.calendar_id}/events/{event_id}"
                if self.calendar_id
                else f"{GRAPH_BASE}/me/events/{event_id}"
            )
            with httpx.Client(timeout=15) as client:
                resp = client.delete(
                    base_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code == 404:
                    logger.warning("Outlook event %s not found (already deleted?)", event_id)
                    return False
                resp.raise_for_status()
                logger.info("Outlook Calendar event deleted: %s", event_id)
                return True

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Graph API error deleting Outlook event %s: %s — %s",
                event_id, exc.response.status_code, exc.response.text,
            )
            return False
        except Exception as exc:
            logger.error("Unexpected error deleting Outlook event %s: %s", event_id, exc, exc_info=True)
            return False


# ── Token rotation persistence helper ────────────────────────────────────────

async def persist_outlook_token_if_rotated(
    service: OutlookCalendarService,
    config,  # BrokerPromptConfig ORM instance
    db,      # AsyncSession
) -> None:
    """
    If the Graph API rotated the refresh token during the last call,
    encrypt and persist the new value to the database.

    Call this after every create / update / delete operation.
    """
    if not getattr(service, "_token_rotated", False):
        return
    from app.core.encryption import encrypt_value
    config.outlook_refresh_token = encrypt_value(service._refresh_token)
    service._token_rotated = False
    await db.commit()
    logger.info("Outlook refresh token rotated and persisted for broker_id=%s", config.broker_id)
