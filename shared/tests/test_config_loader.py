"""config_loader 단위 테스트."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from dev_team_shared.config_loader import (
    ConfigLoadError,
    load_config,
    merge_configs,
    substitute_env_vars,
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestMergeConfigs:
    def test_deep_merges_nested_dicts(self) -> None:
        base = {"llm": {"model": "sonnet", "temperature": 0.2}, "role": "engineer"}
        override = {"llm": {"model": "opus"}}

        merged = merge_configs(base, override)

        assert merged == {
            "llm": {"model": "opus", "temperature": 0.2},
            "role": "engineer",
        }

    def test_replaces_list_values(self) -> None:
        base = {"mcp_servers": [{"name": "a"}, {"name": "b"}]}
        override = {"mcp_servers": [{"name": "c"}]}

        merged = merge_configs(base, override)

        assert merged == {"mcp_servers": [{"name": "c"}]}

    def test_denies_top_level_persona_override(self, caplog: pytest.LogCaptureFixture) -> None:
        base = {"persona": "base", "llm": {"model": "sonnet"}}
        override = {"persona": "overridden", "llm": {"model": "opus"}}

        with caplog.at_level(logging.WARNING):
            merged = merge_configs(base, override)

        assert merged["persona"] == "base"
        assert merged["llm"]["model"] == "opus"
        assert any("persona" in rec.message for rec in caplog.records)

    def test_denies_top_level_workflow_override(self) -> None:
        base = {"workflow": {"base": "default", "extensions": ["a"]}}
        override = {"workflow": {"base": "other"}}

        merged = merge_configs(base, override)

        assert merged == {"workflow": {"base": "default", "extensions": ["a"]}}

    def test_denies_role_and_specialty_override(self) -> None:
        base = {"role": "engineer", "specialty": "backend"}
        override = {"role": "qa", "specialty": "frontend"}

        merged = merge_configs(base, override)

        assert merged == base

    def test_nested_fields_under_allowed_key_can_be_overridden(self) -> None:
        """persona 가 denied 여도, 예컨대 llm 아래 중첩된 persona-named 필드는 통과."""
        base = {"llm": {"persona": "unused_nested"}}
        override = {"llm": {"persona": "changed"}}

        merged = merge_configs(base, override)

        assert merged["llm"]["persona"] == "changed"


class TestSubstituteEnvVars:
    def test_simple_substitution(self) -> None:
        env = {"FOO": "bar"}
        assert substitute_env_vars("${FOO}", env) == "bar"

    def test_with_default(self) -> None:
        assert substitute_env_vars("${MISSING:-fallback}", env={}) == "fallback"

    def test_missing_without_default_becomes_empty(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.WARNING):
            result = substitute_env_vars("${MISSING}", env={})

        assert result == ""
        assert any("MISSING" in rec.message for rec in caplog.records)

    def test_multiple_refs_in_one_string(self) -> None:
        env = {"A": "1", "B": "2"}
        assert substitute_env_vars("A=${A}, B=${B}", env) == "A=1, B=2"

    def test_recurses_into_nested_structures(self) -> None:
        env = {"KEY": "secret-value"}
        result = substitute_env_vars(
            {"llm": {"api_key": "${KEY}", "models": ["${KEY}-a", "static"]}},
            env,
        )
        assert result == {
            "llm": {"api_key": "secret-value", "models": ["secret-value-a", "static"]},
        }

    def test_leaves_non_strings_alone(self) -> None:
        assert substitute_env_vars(42, env={}) == 42
        assert substitute_env_vars(None, env={}) is None
        assert substitute_env_vars(True, env={}) is True


class TestLoadConfig:
    def test_loads_base_only(self, tmp_path: Path) -> None:
        base = _write(tmp_path / "base.yaml", "role: engineer\nllm:\n  model: sonnet\n")
        cfg = load_config(base)
        assert cfg == {"role": "engineer", "llm": {"model": "sonnet"}}

    def test_merges_with_override(self, tmp_path: Path) -> None:
        base = _write(
            tmp_path / "base.yaml",
            "role: engineer\nllm:\n  model: sonnet\n  temperature: 0.2\n",
        )
        override = _write(tmp_path / "override.yaml", "llm:\n  model: opus\n")

        cfg = load_config(base, override)

        assert cfg == {"role": "engineer", "llm": {"model": "opus", "temperature": 0.2}}

    def test_substitutes_env_vars_from_override(self, tmp_path: Path) -> None:
        base = _write(tmp_path / "base.yaml", 'llm:\n  api_key: ""\n')
        override = _write(tmp_path / "override.yaml", "llm:\n  api_key: ${ANTHROPIC_API_KEY}\n")

        cfg = load_config(base, override, env={"ANTHROPIC_API_KEY": "sk-test-123"})

        assert cfg["llm"]["api_key"] == "sk-test-123"

    def test_missing_override_file_is_ignored(self, tmp_path: Path) -> None:
        base = _write(tmp_path / "base.yaml", "role: engineer\n")
        cfg = load_config(base, tmp_path / "nope.yaml")
        assert cfg == {"role": "engineer"}

    def test_raises_on_missing_base(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigLoadError):
            load_config(tmp_path / "nope.yaml")

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        bad = _write(tmp_path / "bad.yaml", "key: : :")
        with pytest.raises(ConfigLoadError):
            load_config(bad)

    def test_raises_when_base_is_not_mapping(self, tmp_path: Path) -> None:
        bad = _write(tmp_path / "list.yaml", "- 1\n- 2\n")
        with pytest.raises(ConfigLoadError):
            load_config(bad)
