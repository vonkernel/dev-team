"""Anthropic (ChatAnthropic) provider 구현.

이 모듈은 임포트되는 것만으로 팩토리에 `"anthropic"` provider 를 등록한다.
다른 모듈에서 직접 참조할 필요는 없으며, `providers/__init__.py` 가
부작용 임포트(side-effect import)로 등록을 트리거한다.
"""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from dev_team_shared.adapters.llm.factory import LLMSpec, register_provider


def _build(spec: LLMSpec) -> BaseChatModel:
    kwargs: dict[str, Any] = {"model": spec.model}
    if spec.temperature is not None:
        kwargs["temperature"] = spec.temperature
    if spec.api_key:
        kwargs["api_key"] = spec.api_key
    kwargs.update(spec.extra)
    return ChatAnthropic(**kwargs)


register_provider("anthropic", _build)
