from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODELS = ("nvidia/llama-3.1-nemotron-ultra-253b-v1",)


@dataclass(frozen=True)
class ProviderKey:
    name: str
    fingerprint: str


@dataclass(frozen=True)
class ProviderInventory:
    provider: str
    base_url: str
    keys: tuple[ProviderKey, ...]
    models: tuple[str, ...]
    enabled: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "key_count": len(self.keys),
            "key_fingerprints": [key.fingerprint for key in self.keys],
            "models": list(self.models),
            "enabled": self.enabled,
        }


def _fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:12]


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def nvidia_inventory_from_env() -> ProviderInventory:
    raw_keys: list[tuple[str, str]] = []
    for name, value in sorted(os.environ.items()):
        if name.startswith("NVIDIA_API_KEY_") and value.strip():
            raw_keys.append((name, value.strip()))
    for index, value in enumerate(_split_csv(os.getenv("AXIOMFORGE_NVIDIA_KEYS", "")), start=1):
        raw_keys.append((f"AXIOMFORGE_NVIDIA_KEYS_{index}", value))

    keys = tuple(ProviderKey(name=name, fingerprint=_fingerprint(value)) for name, value in raw_keys)
    models = _split_csv(os.getenv("AXIOMFORGE_NVIDIA_MODELS", "")) or DEFAULT_NVIDIA_MODELS
    base_url = os.getenv("AXIOMFORGE_NVIDIA_BASE_URL") or os.getenv("NVIDIA_BASE_URL") or DEFAULT_NVIDIA_BASE_URL
    enabled = os.getenv("AXIOMFORGE_PROVIDER_MODE", "offline").lower() == "nvidia" and bool(raw_keys)
    return ProviderInventory(provider="nvidia", base_url=base_url.rstrip("/"), keys=keys, models=tuple(models), enabled=enabled)


def nvidia_chat_once(*, prompt: str, model: str | None = None, timeout_seconds: int = 45) -> dict[str, Any]:
    inventory = nvidia_inventory_from_env()
    if not inventory.enabled:
        return {
            "ok": False,
            "error": "nvidia provider is not enabled or has no configured keys",
            "inventory": inventory.public_dict(),
        }

    key_name = inventory.keys[0].name
    api_key = os.environ[key_name]
    selected_model = model or inventory.models[0]
    payload = {
        "model": selected_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 700,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{inventory.base_url}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:1000]
        return {"ok": False, "error": f"http {exc.code}: {body}", "model": selected_model}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "model": selected_model}

    content = ""
    choices = body.get("choices") or []
    if choices:
        content = choices[0].get("message", {}).get("content", "")
    return {
        "ok": bool(content),
        "model": selected_model,
        "key_fingerprint": inventory.keys[0].fingerprint,
        "content": content,
        "usage": body.get("usage", {}),
    }
