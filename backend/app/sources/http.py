"""Shared HTTP client for network sources. Tests inject ``httpx.MockTransport``."""

import httpx

USER_AGENT = "growthOS/0.2 (personal career growth engine; +https://github.com/radys-s/growthOS)"


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html;q=0.9, */*;q=0.5",  # some sites 406 without */*
            "Accept-Language": "cs, en;q=0.8",
        },
        follow_redirects=True,
        transport=transport or httpx.HTTPTransport(retries=1),
    )
