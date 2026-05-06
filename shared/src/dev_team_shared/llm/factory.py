"""LLM provider 팩토리.

Role Config 의 `llm` 블록을 받아 `BaseChatModel` 인스턴스를 반환한다.
이 모듈은 **provider 구현에 대해 폐쇄(closed)**이며, 신규 provider 는
`providers/<name>.py` 파일을 추가하고 `register_provider` 로 자가 등록만 하면
확장된다 (OCP).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel


@dataclass(frozen=True)
class LLMSpec:
    """Role Config `llm` 블록의 정규화된 표현."""

    provider: str
    model: str
    temperature: float | None = None
    api_key: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> LLMSpec:
        known = {"provider", "model", "temperature", "api_key"}
        extra = {k: v for k, v in cfg.items() if k not in known}

        provider = cfg.get("provider")
        model = cfg.get("model")
        if not provider:
            raise ValueError("llm.provider is required")
        if not model:
            raise ValueError("llm.model is required")

        return cls(
            provider=str(provider),
            model=str(model),
            temperature=cfg.get("temperature"),
            api_key=cfg.get("api_key") or None,
            extra=extra,
        )


class UnknownLLMProviderError(ValueError):
    """팩토리에 등록되지 않은 provider 요청."""


# provider 이름 → 빌더 함수. 구현체 모듈이 `register_provider` 로 자가 등록한다.
_registry: dict[str, Callable[[LLMSpec], BaseChatModel]] = {}


def register_provider(name: str, builder: Callable[[LLMSpec], BaseChatModel]) -> None:
    """신규 LLM provider 구현체를 등록.

    provider 구현 모듈(예: `providers/anthropic.py`) 가 임포트될 때 호출되어야 한다.
    """
    _registry[name] = builder


def registered_providers() -> list[str]:
    """현재 등록된 provider 이름 목록 (주로 디버깅/테스트용)."""
    return sorted(_registry)


def create_chat_model(spec: LLMSpec) -> BaseChatModel:
    """주어진 스펙으로 `BaseChatModel` 인스턴스를 생성."""
    if spec.provider not in _registry:
        raise UnknownLLMProviderError(
            f"unknown LLM provider: {spec.provider!r} (registered: {registered_providers()})",
        )
    return _registry[spec.provider](spec)


__all__ = [
    "LLMSpec",
    "UnknownLLMProviderError",
    "create_chat_model",
    "register_provider",
    "registered_providers",
]
