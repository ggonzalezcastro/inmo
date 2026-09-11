"""Async, observable client for the versioned Meta Graph API."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.services.meta.metrics import record_graph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetaGraphError(RuntimeError):
    category: str
    message: str
    status_code: int
    code: Optional[int] = None
    subcode: Optional[int] = None
    is_transient: bool = False
    trace_id: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.category}: {self.message}"


def _classify_error(code: Optional[int], status: int, is_transient: bool) -> str:
    if code == 190:
        return "TOKEN_EXPIRED"
    if code in {10, 200, 294}:
        return "PERMISSION_REVOKED"
    if code in {4, 17, 32, 613} or status == 429:
        return "RATE_LIMITED"
    if status >= 500 or is_transient:
        return "TRANSIENT_PROVIDER_ERROR"
    return "INVALID_REQUEST"


def _redact_secrets(message: str, *secrets: Optional[str]) -> str:
    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


class MetaGraphClient:
    BASE_URL = "https://graph.facebook.com"
    ALLOWED_HOSTS = {"graph.facebook.com", "graph.instagram.com"}

    def __init__(
        self,
        access_token: Optional[str] = None,
        *,
        api_version: Optional[str] = None,
        app_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.access_token = access_token
        self.api_version = (api_version or settings.META_GRAPH_API_VERSION).lstrip("/")
        self.app_secret = app_secret if app_secret is not None else settings.META_APP_SECRET
        requested_base_url = (base_url or self.BASE_URL).rstrip("/")
        parsed_base_url = urlsplit(requested_base_url)
        if (
            parsed_base_url.scheme.lower() != "https"
            or (parsed_base_url.hostname or "").lower() not in self.ALLOWED_HOSTS
            or parsed_base_url.username is not None
            or parsed_base_url.password is not None
            or parsed_base_url.port not in {None, 443}
            or parsed_base_url.path
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise ValueError("Meta Graph base URL is invalid")
        self.base_url = requested_base_url
        self.transport = transport

    def _url(self, path: str) -> str:
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc:
            host = (parsed.hostname or "").lower().rstrip(".")
            try:
                port = parsed.port
            except ValueError as exc:
                raise ValueError("Meta Graph pagination URL is invalid") from exc
            if (
                parsed.scheme.lower() != "https"
                or host not in self.ALLOWED_HOSTS
                or parsed.username is not None
                or parsed.password is not None
                or port not in {None, 443}
            ):
                raise ValueError("Meta Graph pagination URL must use an approved Meta Graph host")
            return path
        return f"{self.base_url}/{self.api_version}/{path.lstrip('/')}"

    def _auth_params(self, token: Optional[str]) -> Dict[str, str]:
        effective_token = token or self.access_token
        if not effective_token:
            return {}
        params = {"access_token": effective_token}
        if self.app_secret:
            params["appsecret_proof"] = hmac.new(
                self.app_secret.encode(),
                effective_token.encode(),
                hashlib.sha256,
            ).hexdigest()
        return params

    async def request(
        self,
        method: str,
        path: str,
        *,
        access_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        query = dict(params or {})
        query.update(self._auth_params(access_token))
        timeout = httpx.Timeout(20.0, connect=5.0)
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    method.upper(),
                    self._url(path),
                    params=query,
                    data=data,
                    json=json,
                )
        except httpx.HTTPError:
            record_graph(method, path, "network_error", time.monotonic() - started)
            raise

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if response.is_error or "error" in payload:
            error = payload.get("error") or {}
            code = error.get("code")
            subcode = error.get("error_subcode")
            is_transient = bool(error.get("is_transient"))
            category = _classify_error(code, response.status_code, is_transient)
            record_graph(method, path, category.lower(), time.monotonic() - started)
            provider_message = error.get("message") or (
                f"Meta Graph returned HTTP {response.status_code}"
            )
            raise MetaGraphError(
                category=category,
                message=_redact_secrets(
                    str(provider_message),
                    access_token,
                    self.access_token,
                    self.app_secret,
                ),
                status_code=response.status_code,
                code=code,
                subcode=subcode,
                is_transient=is_transient or response.status_code >= 500,
                trace_id=error.get("fbtrace_id"),
            )
        record_graph(method, path, "success", time.monotonic() - started)
        return payload

    async def get(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.request("POST", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.request("DELETE", path, **kwargs)

    async def iterate(self, path: str, **kwargs: Any) -> AsyncIterator[Dict[str, Any]]:
        next_path: Optional[str] = path
        first_kwargs = kwargs
        while next_path:
            page = await self.get(next_path, **first_kwargs)
            first_kwargs = {}
            for item in page.get("data", []):
                yield item
            next_path = (page.get("paging") or {}).get("next")
