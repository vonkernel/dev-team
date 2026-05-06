"""내장 LLM provider 구현체.

각 모듈은 임포트 시점에 `register_provider(...)` 를 호출하여 팩토리에 자가 등록한다.
본 패키지의 __init__ 은 모든 내장 구현 모듈을 임포트하는 역할만 수행 — 이 파일
자체는 provider 로직을 전혀 포함하지 않는다.

신규 provider 추가 시 해야 할 일:
  1. `providers/<name>.py` 생성 + `register_provider` 호출
  2. 아래 import 목록에 추가 (또는 `importlib` / entry points 로 자동화)

이로써 `factory.py` 는 신규 provider 추가에 대해 수정되지 않는다 (OCP).
"""

from dev_team_shared.llm.providers import anthropic  # noqa: F401  (side-effect import)

__all__: list[str] = []
