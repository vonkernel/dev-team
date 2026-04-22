"""Agent Card 빌더 단위 테스트."""

from __future__ import annotations

import pytest
from dev_team_shared.a2a import build_agent_card


def _minimal_config() -> dict:
    return {
        "role": "architect",
        "persona": "당신은 시스템 아키텍트입니다.\n추가 설명은 여기...",
        "agent_card": {
            "url": "http://architect:9000/a2a/architect",
            "skills": [
                {
                    "id": "design_proposal",
                    "name": "OO 설계안 생성",
                    "description": "복수 설계안 도출",
                    "tags": ["architecture", "design"],
                },
            ],
        },
    }


class TestBuildAgentCard:
    def test_minimal_required_fields(self) -> None:
        card = build_agent_card(_minimal_config())

        dumped = card.model_dump(by_alias=True, exclude_none=True)

        # spec §4.4.1 필수 필드 모두 존재
        for required in [
            "name",
            "description",
            "version",
            "supportedInterfaces",
            "capabilities",
            "defaultInputModes",
            "defaultOutputModes",
            "skills",
        ]:
            assert required in dumped, f"required field missing: {required}"

    def test_camelcase_serialization(self) -> None:
        card = build_agent_card(_minimal_config())
        dumped = card.model_dump(by_alias=True, exclude_none=True)
        iface = dumped["supportedInterfaces"][0]
        assert "protocolBinding" in iface  # not protocol_binding
        assert iface["protocolBinding"] == "JSONRPC"

    def test_skill_required_fields(self) -> None:
        card = build_agent_card(_minimal_config())
        skill = card.skills[0]
        assert skill.id == "design_proposal"
        assert skill.name == "OO 설계안 생성"
        assert skill.description == "복수 설계안 도출"
        assert skill.tags == ["architecture", "design"]

    def test_name_includes_specialty(self) -> None:
        cfg = _minimal_config()
        cfg["role"] = "engineer"
        cfg["specialty"] = "backend"

        card = build_agent_card(cfg)
        assert card.name == "engineer:backend"

    def test_description_is_first_non_empty_line(self) -> None:
        cfg = _minimal_config()
        cfg["persona"] = "\n  \n당신은 Backend 개발자입니다.\n자세한 설명..."

        card = build_agent_card(cfg)
        assert card.description == "당신은 Backend 개발자입니다."

    def test_default_modes_if_absent(self) -> None:
        card = build_agent_card(_minimal_config())
        assert card.default_input_modes == ["text/plain"]
        assert card.default_output_modes == ["text/plain"]

    def test_capabilities_defaults_to_empty(self) -> None:
        card = build_agent_card(_minimal_config())
        dumped = card.capabilities.model_dump(by_alias=True, exclude_none=True)
        assert dumped == {}  # 모두 Optional 이라 빈 객체

    def test_capabilities_camelcase(self) -> None:
        cfg = _minimal_config()
        cfg["agent_card"]["capabilities"] = {
            "streaming": True,
            "pushNotifications": False,
        }
        card = build_agent_card(cfg)
        assert card.capabilities.streaming is True
        assert card.capabilities.push_notifications is False

    def test_raises_without_role(self) -> None:
        cfg = _minimal_config()
        del cfg["role"]
        with pytest.raises(ValueError, match="role"):
            build_agent_card(cfg)

    def test_raises_without_persona(self) -> None:
        cfg = _minimal_config()
        del cfg["persona"]
        with pytest.raises(ValueError, match="persona"):
            build_agent_card(cfg)

    def test_raises_without_url(self) -> None:
        cfg = _minimal_config()
        del cfg["agent_card"]["url"]
        with pytest.raises(ValueError, match="url"):
            build_agent_card(cfg)
