"""The visitor's IP address, for guest limits — and a private fingerprint of it for storage.

Which header: on Vercel (production), ProxyFix in app/__init__.py sets request.remote_addr from
the LAST X-Forwarded-For entry. Vercel overwrites X-Forwarded-For with the real client IP "to
prevent IP spoofing" (vercel.com/docs/headers/request-headers), and the last entry is always the
one Vercel added, so a visitor who sends their own X-Forwarded-For can't change it. Locally there
is no proxy and remote_addr is the real socket address.

Storage: never the raw IP. ip_fingerprint() is an HMAC with SECRET_KEY, so the database can't
be turned back into IPs, and nobody can compute someone else's fingerprint to use up their tries.
IPv6 users usually own a whole /64 block and can switch addresses inside it at will, so all
addresses in one /64 count as one guest.
"""
import hashlib
import hmac
import ipaddress

from flask import current_app, request


def client_ip():
    return request.remote_addr or ""


def ip_fingerprint(ip=None):
    ip = client_ip() if ip is None else ip
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError:
        key = "unknown"
    else:
        if address.version == 6 and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        if address.version == 6:
            key = str(ipaddress.ip_network(f"{address}/64", strict=False))
        else:
            key = str(address)
    secret = current_app.config["SECRET_KEY"].encode()
    return hmac.new(secret, key.encode(), hashlib.sha256).hexdigest()
