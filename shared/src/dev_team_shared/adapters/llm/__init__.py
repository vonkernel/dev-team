"""LLM Provider 어댑터.

LangChain 의 `BaseChatModel` 인터페이스를 공통 반환 타입으로 사용.
provider 구현 모듈(`providers/*`)이 임포트 시점에 팩토리에 자가 등록하므로,
이 패키지를 import 하는 것만으로 내장 provider 들이 사용 가능해진다.
"""

# 내장 provider 들 자가 등록 (side-effect import)
from dev_team_shared.adapters.llm import providers  # noqa: F401
from dev_team_shared.adapters.llm.factory import (
    LLMSpec,
    UnknownLLMProviderError,
    create_chat_model,
    register_provider,
    registered_providers,
)

__all__ = [
    "LLMSpec",
    "UnknownLLMProviderError",
    "create_chat_model",
    "register_provider",
    "registered_providers",
]
