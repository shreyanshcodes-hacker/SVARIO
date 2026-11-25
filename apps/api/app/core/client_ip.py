"""Trusted proxy-aware client IP resolution for rate limiting and security controls."""

from __future__ import annotations

import ipaddress
from typing import Optional, Tuple, Union
from fastapi import Request
from app.core.config import Settings, get_settings

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def _parse_ip_address(raw: Optional[str]) -> Optional[IPAddress]:
    """Parse a raw IPv4/IPv6 string safely; return None if invalid."""
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def _is_trusted_ip(ip_obj: IPAddress, trusted_networks: Tuple[IPNetwork, ...]) -> bool:
    return any(ip_obj in network for network in trusted_networks)


def resolve_client_ip(request: Request, settings: Optional[Settings] = None) -> str:
    """Resolve the effective client IP from the immediate peer and trusted X-Forwarded-For chain.

    Security rules:
    - Immediate peer (`request.client.host`) is always inspected first.
    - If the immediate peer is missing/unparseable or not in `TRUSTED_PROXIES`,
      `X-Forwarded-For` is ignored completely.
    - If the immediate peer IS in `TRUSTED_PROXIES`, `X-Forwarded-For` is walked
      from right to left, skipping trusted proxies, and the first untrusted valid
      IP address is returned.
    - If any hop at or before the first untrusted address is empty or malformed,
      resolution fails safely to the immediate peer IP.
    """
    if request.client is None or not request.client.host:
        return "unknown"

    peer_raw = request.client.host.strip()
    if not peer_raw:
        return "unknown"

    peer_ip = _parse_ip_address(peer_raw)
    if peer_ip is None:
        return peer_raw

    resolved_settings = settings or get_settings()
    trusted_networks = resolved_settings.trusted_proxy_networks
    if not trusted_networks or not _is_trusted_ip(peer_ip, trusted_networks):
        return str(peer_ip)

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for or not forwarded_for.strip():
        return str(peer_ip)

    hops = [part.strip() for part in forwarded_for.split(",")]
    for raw_hop in reversed(hops):
        hop_ip = _parse_ip_address(raw_hop)
        if hop_ip is None:
            return str(peer_ip)
        if _is_trusted_ip(hop_ip, trusted_networks):
            continue
        return str(hop_ip)

    return str(peer_ip)
