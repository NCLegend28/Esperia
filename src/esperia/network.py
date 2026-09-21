"""Public HTTPS transport with DNS address pinning. Example: PublicTransport(settings)."""

import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

from esperia.settings import Settings


def validate_public_url(url: str, settings: Settings) -> None:
    """Validate syntax and owner host policy; DNS is checked at connection time."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or parsed.fragment
        or any(c.isspace() for c in url)
        or "\\" in url
        or "." not in host
        or host.endswith((".localhost", ".local", ".internal"))
    ):
        raise ValueError("Source URL is outside the public HTTPS policy")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Source URLs must use public DNS hostnames, not IP literals")
    if settings.allowed_hosts and host not in settings.allowed_hosts:
        raise ValueError("Source host is outside the configured host policy")


class PublicTransport(httpx.BaseTransport):
    """Resolve once, reject non-public destinations, and connect to the checked IP.

    TLS verification and SNI use the original hostname; redirects are checked again.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.inner = httpx.HTTPTransport(
            trust_env=False, limits=httpx.Limits(max_keepalive_connections=0)
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        validate_public_url(str(request.url), self.settings)
        try:
            addresses = socket.getaddrinfo(
                request.url.host, 443, type=socket.SOCK_STREAM
            )
        except OSError:
            raise httpx.ConnectError(
                "Source DNS resolution failed", request=request
            ) from None
        ips = [str(address[4][0]) for address in addresses]
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError("Source DNS must resolve only to public addresses")
        extensions = {**request.extensions, "sni_hostname": request.url.host}
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=ips[0]),
            headers=request.headers,
            stream=request.stream,
            extensions=extensions,
        )
        return self.inner.handle_request(pinned)

    def close(self) -> None:
        """Release pooled sockets."""
        self.inner.close()
