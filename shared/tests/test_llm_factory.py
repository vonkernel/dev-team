"""LLM 팩토리 단위 테스트."""

from __future__ import annotations

from typing import Any, cast

import pytest
from dev_team_shared.adapters.llm import (
    LLMSpec,
    UnknownLLMProviderError,
    create_chat_model,
    register_provider,
    registered_providers,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage


class _StubChatModel(BaseChatModel):
    """테스트 전용 스텁. 호출되지 않으므로 최소 구현만."""

    recorded: dict[str, Any] = {}

    @property
    def _llm_type(self) -> str:
        return "stub"

    def _generate(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


class TestLLMSpec:
    def test_from_config_minimal(self) -> None:
        spec = LLMSpec.from_config({"provider": "anthropic", "model": "claude-sonnet-4-6"})
        assert spec.provider == "anthropic"
        assert spec.model == "claude-sonnet-4-6"
        assert spec.temperature is None
        assert spec.api_key is None
        assert spec.extra == {}

    def test_from_config_collects_extra(self) -> None:
        spec = LLMSpec.from_config(
            {
                "provider": "anthropic",
                "model": "x",
                "temperature": 0.4,
                "api_key": "k",
                "max_tokens": 2048,
            },
        )
        assert spec.temperature == 0.4
        assert spec.api_key == "k"
        assert spec.extra == {"max_tokens": 2048}

    def test_from_config_rejects_missing_provider(self) -> None:
        with pytest.raises(ValueError, match="provider"):
            LLMSpec.from_config({"model": "x"})

    def test_from_config_rejects_missing_model(self) -> None:
        with pytest.raises(ValueError, match="model"):
            LLMSpec.from_config({"provider": "anthropic"})

    def test_empty_api_key_becomes_none(self) -> None:
        spec = LLMSpec.from_config({"provider": "anthropic", "model": "x", "api_key": ""})
        assert spec.api_key is None


class TestProviderRegistry:
    def test_anthropic_is_registered_on_import(self) -> None:
        assert "anthropic" in registered_providers()

    def test_unknown_provider_raises(self) -> None:
        spec = LLMSpec(provider="nope", model="x")
        with pytest.raises(UnknownLLMProviderError):
            create_chat_model(spec)

    def test_register_and_create_custom_provider(self) -> None:
        received: list[LLMSpec] = []

        def builder(spec: LLMSpec) -> BaseChatModel:
            received.append(spec)
            return _StubChatModel()

        register_provider("stub", builder)
        try:
            spec = LLMSpec(provider="stub", model="m1", temperature=0.1, api_key="sk")
            model = create_chat_model(spec)

            assert isinstance(model, _StubChatModel)
            assert received == [spec]
        finally:
            # 후속 테스트에 누수 방지 — 내부 registry 초기화는 공개 API 가 없어
            # 테스트 환경에서 stub 을 남겨둬도 다른 테스트에 영향 없음.
            pass


class TestAnthropicProvider:
    def test_builds_chat_anthropic_without_calling_api(self) -> None:
        """실제 API 호출 없이 어댑터 생성만 확인."""
        spec = LLMSpec(
            provider="anthropic",
            model="claude-sonnet-4-6",
            temperature=0.2,
            api_key="dummy-not-called",
        )
        model = cast(Any, create_chat_model(spec))
        # langchain-anthropic 은 SecretStr 로 key 를 감쌈 — 그냥 존재 여부만 확인
        assert model is not None
        # 모델명이 spec 과 일치하는지 (버전에 따라 attr 명 차이 대비)
        assert getattr(model, "model", None) == "claude-sonnet-4-6" or getattr(
            model,
            "model_name",
            None,
        ) == "claude-sonnet-4-6"

    def test_ai_message_roundtrip_not_required(self) -> None:
        """AIMessage 가 import 가능한지만 체크 (의존성 sanity)."""
        _ = AIMessage(content="x")
