"""Referral slug generation.

A slug encodes the affiliate's full ancestor chain (base36 ids joined by "-")
plus a short random suffix so links stay unique per product, e.g. user with
path 1/4/9 gets a channel like "1-4-9~x7kq". The chain makes every link
self-describing: the owning affiliate and every parent in their network.
"""
import secrets
import string

ALPHABET = string.digits + string.ascii_lowercase


def b36(n: int) -> str:
    if n == 0:
        return "0"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = ALPHABET[r] + out
    return out


def make_slug(path: str) -> str:
    chain = "-".join(b36(int(p)) for p in path.split("/") if p)
    suffix = "".join(secrets.choice(ALPHABET) for _ in range(4))
    return f"{chain}~{suffix}"
