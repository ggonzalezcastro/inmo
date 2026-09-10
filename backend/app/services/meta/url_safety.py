"""URL safety helpers for values passed to Meta or used in Graph pagination."""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit


_LOCAL_HOST_SUFFIXES = (".local", ".localhost", ".internal")


def is_public_https_url(value: Any) -> bool:
    """Reject local/private URL forms without performing a server-side fetch.

    Hostname resolution is intentionally not performed here: the CRM passes media
    URLs to Meta and never downloads them itself. Any future downloader must also
    resolve and pin the public destination before opening a connection.
    """
    try:
        parsed = urlsplit(str(value))
        host = (parsed.hostname or "").lower().rstrip(".")
        # Accessing port also rejects malformed values such as ``:not-a-port``.
        _ = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or host == "localhost"
        or host.endswith(_LOCAL_HOST_SUFFIXES)
    ):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        # Reject single-label names such as https://redis or https://metadata.
        return "." in host
    return address.is_global
