"""Agent Card 빌더.

A2A spec §4.4.1: https://a2a-protocol.org/latest/specification/
필수 필드: name, description, supportedInterfaces[], version, capabilities,
           defaultInputModes[], defaultOutputModes[], skills[]
각 skill 필수: id, name, description, tags[]

노출 경로: `/.well-known/agent-card.json`
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentCapabilities(BaseModel):
    """A2A AgentCapabilities (spec §4.4.3)."""

    model_config = ConfigDict(populate_by_name=True)

    streaming: bool | None = None
    push_notifications: bool | None = Field(default=None, alias="pushNotifications")
    extended_agent_card: bool | None = Field(default=None, alias="extendedAgentCard")
    extensions: list[dict[str, Any]] | None = None


class AgentInterface(BaseModel):
    """A2A AgentInterface (spec §4.4.6)."""

    model_config = ConfigDict(populate_by_name=True)

    url: str
    protocol_binding: str = Field(alias="protocolBinding")
    tenant: str | None = None


class AgentProvider(BaseModel):
    """A2A AgentProvider (spec §4.4.2)."""

    url: str
    organization: str


class AgentSkill(BaseModel):
    """A2A AgentSkill (spec §4.4.5)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str
    tags: list[str]

    examples: list[str] | None = None
    input_modes: list[str] | None = Field(default=None, alias="inputModes")
    output_modes: list[str] | None = Field(default=None, alias="outputModes")


class AgentCard(BaseModel):
    """A2A AgentCard (spec §4.4.1)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    version: str
    supported_interfaces: list[AgentInterface] = Field(alias="supportedInterfaces")
    capabilities: AgentCapabilities
    default_input_modes: list[str] = Field(alias="defaultInputModes")
    default_output_modes: list[str] = Field(alias="defaultOutputModes")
    skills: list[AgentSkill]

    provider: AgentProvider | None = None
    documentation_url: str | None = Field(default=None, alias="documentationUrl")
    icon_url: str | None = Field(default=None, alias="iconUrl")

    # 서명(`signatures[]`)은 초기 범위 제외 — 부록 메모 참조.


def build_agent_card(config: dict[str, Any]) -> AgentCard:
    """Role Config 의 공개 부분으로부터 AgentCard 를 생성.

    기대하는 config 키:
    - `role` (필수)
    - `specialty` (선택) — 있으면 name 에 반영
    - `persona` (필수) — description 의 소스 (첫 줄/첫 문단)
    - `agent_card` (선택 블록):
        - `version` (기본 "0.1.0")
        - `url` (필수) — supportedInterfaces[0].url
        - `protocol_binding` (기본 "JSONRPC")
        - `capabilities.streaming`, `capabilities.pushNotifications` 등
        - `skills[]` — 각 항목은 AgentSkill 필드 구조
        - `default_input_modes`, `default_output_modes` (기본 ["text/plain"])
        - `provider.organization`, `provider.url`
    """
    role = config.get("role")
    if not role:
        raise ValueError("config.role is required to build an AgentCard")

    specialty = config.get("specialty")
    name = f"{role}:{specialty}" if specialty else role

    persona = config.get("persona")
    if not persona:
        raise ValueError("config.persona is required to build an AgentCard")
    description = _first_meaningful_line(persona)

    card_cfg = config.get("agent_card") or {}

    url = card_cfg.get("url")
    if not url:
        raise ValueError("config.agent_card.url is required to build an AgentCard")

    protocol_binding = card_cfg.get("protocol_binding", "JSONRPC")
    interfaces = [AgentInterface(url=url, protocol_binding=protocol_binding)]

    capabilities_cfg = card_cfg.get("capabilities") or {}
    capabilities = AgentCapabilities.model_validate(capabilities_cfg)

    default_input = card_cfg.get("default_input_modes") or ["text/plain"]
    default_output = card_cfg.get("default_output_modes") or ["text/plain"]

    skills_cfg = card_cfg.get("skills") or []
    skills = [AgentSkill.model_validate(s) for s in skills_cfg]

    provider_cfg = card_cfg.get("provider")
    provider = AgentProvider.model_validate(provider_cfg) if provider_cfg else None

    return AgentCard(
        name=name,
        description=description,
        version=card_cfg.get("version", "0.1.0"),
        supported_interfaces=interfaces,
        capabilities=capabilities,
        default_input_modes=default_input,
        default_output_modes=default_output,
        skills=skills,
        provider=provider,
        documentation_url=card_cfg.get("documentation_url"),
        icon_url=card_cfg.get("icon_url"),
    )


def _first_meaningful_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line:
            return line
    return text.strip()


__all__ = [
    "AgentCapabilities",
    "AgentCard",
    "AgentInterface",
    "AgentProvider",
    "AgentSkill",
    "build_agent_card",
]
