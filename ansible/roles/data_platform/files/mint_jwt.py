#!/usr/bin/env python3
"""Mint HS256 JWTs for PostgREST roles. Stdlib only. Do not print tokens."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def mint(secret: str, role: str, expiry: int) -> str:
    now = int(time.time())
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(
        json.dumps(
            {
                "role": role,
                "iss": "supabase",
                "iat": now,
                "exp": now + expiry,
            },
            separators=(",", ":"),
        ).encode()
    )
    signing = f"{header}.{payload}".encode()
    sig = hmac.new(secret.encode(), signing, hashlib.sha256).digest()
    return f"{header}.{payload}.{b64url(sig)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    parser.add_argument("--expiry", type=int, default=3600 * 24 * 365 * 5)
    args = parser.parse_args()
    secret = sys.stdin.read().strip()
    if len(secret) < 32:
        print("jwt secret must be at least 32 characters", file=sys.stderr)
        return 1
    sys.stdout.write(mint(secret, args.role, args.expiry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
