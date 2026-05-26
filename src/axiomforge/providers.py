from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_MODELS = (
    "moonshotai/kimi-k2.6",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "meta/llama-4-maverick-17b-128e-instruct",
)


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


def _raw_nvidia_keys() -> tuple[tuple[str, str], ...]:
    raw_keys: list[tuple[str, str]] = []
    for name, value in sorted(os.environ.items()):
        if name.startswith("NVIDIA_API_KEY_") and value.strip():
            raw_keys.append((name, value.strip()))
    for index, value in enumerate(_split_csv(os.getenv("AXIOMFORGE_NVIDIA_KEYS", "")), start=1):
        raw_keys.append((f"AXIOMFORGE_NVIDIA_KEYS_{index}", value))
    return tuple(raw_keys)


def nvidia_inventory_from_env() -> ProviderInventory:
    raw_keys = _raw_nvidia_keys()
    keys = tuple(ProviderKey(name=name, fingerprint=_fingerprint(value)) for name, value in raw_keys)
    models = _split_csv(os.getenv("AXIOMFORGE_NVIDIA_MODELS", "")) or DEFAULT_NVIDIA_MODELS
    base_url = os.getenv("AXIOMFORGE_NVIDIA_BASE_URL") or os.getenv("NVIDIA_BASE_URL") or DEFAULT_NVIDIA_BASE_URL
    enabled = os.getenv("AXIOMFORGE_PROVIDER_MODE", "offline").lower() == "nvidia" and bool(raw_keys)
    return ProviderInventory(provider="nvidia", base_url=base_url.rstrip("/"), keys=keys, models=tuple(models), enabled=enabled)


def nvidia_chat_once(*, prompt: str, model: str | None = None, timeout_seconds: int = 45) -> dict[str, Any]:
    inventory = nvidia_inventory_from_env()
    raw_keys = _raw_nvidia_keys()
    if not inventory.enabled:
        return {
            "ok": False,
            "error": "nvidia provider is not enabled or has no configured keys",
            "inventory": inventory.public_dict(),
        }

    attempts: list[dict[str, str]] = []
    candidate_models = (model,) if model else inventory.models
    for selected_model in candidate_models:
        if not selected_model:
            continue
        for key_name, api_key in raw_keys:
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
                body = exc.read().decode(errors="replace")[:500]
                attempts.append(
                    {
                        "model": selected_model,
                        "key_fingerprint": _fingerprint(api_key),
                        "error": f"http {exc.code}: {body}",
                    }
                )
                continue
            except OSError as exc:
                attempts.append(
                    {
                        "model": selected_model,
                        "key_fingerprint": _fingerprint(api_key),
                        "error": str(exc),
                    }
                )
                continue

            content = ""
            choices = body.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content", "")
            if content:
                return {
                    "ok": True,
                    "model": selected_model,
                    "key_fingerprint": _fingerprint(api_key),
                    "content": content,
                    "usage": body.get("usage", {}),
                    "attempts": attempts,
                }
            attempts.append(
                {
                    "model": selected_model,
                    "key_fingerprint": _fingerprint(api_key),
                    "error": "empty response",
                }
            )
    return {"ok": False, "error": "all nvidia attempts failed", "attempts": attempts}
