"""Normalize WhatsApp, Instagram, Messenger, and Lead Ads webhook payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class NormalizedMetaMessage:
    provider: str
    asset_type: str
    asset_external_id: str
    sender_id: str
    message_id: str
    text: str
    message_type: str = "text"
    username: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedMetaStatus:
    provider: str
    asset_type: str
    asset_external_id: str
    message_id: str
    status: str
    error_code: Optional[str] = None
    error_subcode: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedLeadgen:
    asset_external_id: str
    leadgen_id: str
    form_id: str
    ad_id: Optional[str] = None
    adgroup_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


NormalizedMetaEvent = Union[NormalizedMetaMessage, NormalizedMetaStatus, NormalizedLeadgen]


def _whatsapp_text(message: Dict[str, Any]) -> str:
    kind = message.get("type")
    if kind == "text":
        return message.get("text", {}).get("body", "")
    if kind == "button":
        return message.get("button", {}).get("text", "")
    if kind == "interactive":
        interactive = message.get("interactive") or {}
        response = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return response.get("title") or response.get("id") or ""
    media = message.get(kind) or {}
    return media.get("caption") or ""


def _whatsapp_attachments(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    kind = message.get("type")
    if kind not in {"image", "video", "audio", "document", "sticker"}:
        return []
    media = message.get(kind) or {}
    return [{
        "type": kind,
        "id": media.get("id"),
        "mime_type": media.get("mime_type"),
        "sha256": media.get("sha256"),
        "filename": media.get("filename"),
        "caption": media.get("caption"),
    }]


def normalize_meta_payload(payload: Dict[str, Any]) -> List[NormalizedMetaEvent]:
    object_type = payload.get("object")
    normalized: List[NormalizedMetaEvent] = []

    if object_type == "whatsapp_business_account":
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                asset_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
                contacts = {
                    str(item.get("wa_id")): (item.get("profile") or {}).get("name")
                    for item in value.get("contacts", [])
                }
                for message in value.get("messages", []):
                    sender = str(message.get("from") or "")
                    message_id = str(message.get("id") or "")
                    if not asset_id or not sender or not message_id:
                        continue
                    normalized.append(NormalizedMetaMessage(
                        provider="whatsapp",
                        asset_type="whatsapp_phone",
                        asset_external_id=asset_id,
                        sender_id=sender,
                        username=contacts.get(sender),
                        message_id=message_id,
                        text=_whatsapp_text(message),
                        message_type=str(message.get("type") or "unknown"),
                        attachments=_whatsapp_attachments(message),
                        metadata={
                            "timestamp": message.get("timestamp"),
                            "context": message.get("context"),
                            "referral": message.get("referral"),
                        },
                    ))
                for status in value.get("statuses", []):
                    status_id = str(status.get("id") or "")
                    if not asset_id or not status_id:
                        continue
                    errors = status.get("errors") or []
                    first_error = errors[0] if errors else {}
                    normalized.append(NormalizedMetaStatus(
                        provider="whatsapp",
                        asset_type="whatsapp_phone",
                        asset_external_id=asset_id,
                        message_id=status_id,
                        status=str(status.get("status") or "unknown"),
                        error_code=str(first_error.get("code")) if first_error.get("code") is not None else None,
                        error_subcode=str(first_error.get("error_subcode")) if first_error.get("error_subcode") is not None else None,
                        metadata={"timestamp": status.get("timestamp"), "conversation": status.get("conversation")},
                    ))
        return normalized

    if object_type in {"instagram", "page"}:
        for entry in payload.get("entry", []):
            entry_id = str(entry.get("id") or "")
            for change in entry.get("changes", []):
                if change.get("field") != "leadgen":
                    continue
                value = change.get("value") or {}
                leadgen_id = str(value.get("leadgen_id") or "")
                form_id = str(value.get("form_id") or "")
                page_id = str(value.get("page_id") or entry_id)
                if leadgen_id and form_id and page_id:
                    normalized.append(NormalizedLeadgen(
                        asset_external_id=page_id,
                        leadgen_id=leadgen_id,
                        form_id=form_id,
                        ad_id=str(value.get("ad_id")) if value.get("ad_id") else None,
                        adgroup_id=str(value.get("adgroup_id")) if value.get("adgroup_id") else None,
                        metadata=value,
                    ))
            for event in entry.get("messaging", []):
                message = event.get("message") or {}
                postback = event.get("postback") or {}
                sender_id = str((event.get("sender") or {}).get("id") or "")
                recipient_id = str((event.get("recipient") or {}).get("id") or entry_id)
                provider = "instagram" if object_type == "instagram" else "facebook"
                asset_type = "instagram_account" if provider == "instagram" else "facebook_page"
                delivery = event.get("delivery") or {}
                for delivered_id in delivery.get("mids") or []:
                    if recipient_id and delivered_id:
                        normalized.append(NormalizedMetaStatus(
                            provider=provider,
                            asset_type=asset_type,
                            asset_external_id=recipient_id,
                            message_id=str(delivered_id),
                            status="delivered",
                            metadata={"sender_id": sender_id, "watermark": delivery.get("watermark")},
                        ))
                read = event.get("read") or {}
                if recipient_id and sender_id and read.get("watermark"):
                    normalized.append(NormalizedMetaStatus(
                        provider=provider,
                        asset_type=asset_type,
                        asset_external_id=recipient_id,
                        message_id=f"watermark:{sender_id}:{read['watermark']}",
                        status="read",
                        metadata={"sender_id": sender_id, "watermark": read.get("watermark")},
                    ))
                if delivery or read:
                    continue
                if message.get("is_echo"):
                    continue
                message_id = str(message.get("mid") or postback.get("mid") or "")
                if not sender_id or not recipient_id or not message_id:
                    continue
                text = message.get("text") or postback.get("title") or postback.get("payload") or ""
                normalized.append(NormalizedMetaMessage(
                    provider=provider,
                    asset_type=asset_type,
                    asset_external_id=recipient_id,
                    sender_id=sender_id,
                    message_id=message_id,
                    text=text,
                    message_type="postback" if postback else "text",
                    attachments=message.get("attachments") or [],
                    metadata={
                        "timestamp": event.get("timestamp"),
                        "referral": event.get("referral") or message.get("referral"),
                    },
                ))
        return normalized

    return normalized
