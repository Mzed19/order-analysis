from __future__ import annotations

import hashlib
import json
import os

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "86400"))

client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def make_contract_cache_key(contract_text: str, filename: str | None = None) -> str:
    key_base = contract_text + (filename or "")
    digest = hashlib.sha256(key_base.encode("utf-8")).hexdigest()
    return f"contract_chunks:{digest}"


def get_contract_chunks(key: str) -> list[dict]:
    payload = client.get(key)
    if not payload:
        return []

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return []


def set_contract_chunks(key: str, chunks: list[dict]) -> None:
    client.setex(key, REDIS_CACHE_TTL, json.dumps(chunks, ensure_ascii=False))
