"""Role Config 로더 핵심 구현."""

from __future__ import annotations

import logging
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# docs/proposal/architecture-role-config.md: 오버라이드 허용 규칙
# 허용되지 않은 필드의 override 는 경고와 함께 무시한다.
#
# - 코드·정체성 관련 필드 (persona, workflow, role, specialty) 는 override 금지.
# - 나머지 필드 (llm, mcp_servers, a2a_peers, allowed_clients, code_agent, workspace) 는 허용.
_OVERRIDE_DENYLIST: frozenset[str] = frozenset(
    {"persona", "workflow", "role", "specialty"},
)

# `${VAR}` 또는 `${VAR:-default}` 형태의 참조를 찾는 패턴.
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


class ConfigLoadError(Exception):
    """Role Config 로딩 중 복구 불가능한 오류."""


def load_config(
    base_path: str | Path,
    override_path: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Base config 와 선택적 Override config 를 읽어 병합 + env 치환 후 반환.

    Args:
        base_path: 필수 — 이미지에 baked-in 된 기본 config 파일 경로.
        override_path: 선택 — 호스트에서 마운트된 override 파일 경로.
            `None` 이거나 파일이 존재하지 않으면 무시.
        env: 환경변수 치환에 사용할 맵. 기본은 `os.environ`.

    Returns:
        병합·치환이 끝난 config dict.

    Raises:
        ConfigLoadError: base 파일이 없거나 YAML 파싱 실패 시.
    """
    env_map = dict(os.environ) if env is None else env

    base = _read_yaml(Path(base_path))
    if not isinstance(base, dict):
        raise ConfigLoadError(f"base config must be a mapping, got {type(base).__name__}")

    override: dict[str, Any] | None = None
    if override_path is not None:
        op = Path(override_path)
        if op.exists():
            loaded = _read_yaml(op)
            if loaded is not None and not isinstance(loaded, dict):
                raise ConfigLoadError(
                    f"override config must be a mapping, got {type(loaded).__name__}",
                )
            override = loaded or {}
        else:
            logger.debug("override config %s not present, skipping", op)

    merged = merge_configs(base, override) if override else deepcopy(base)
    return substitute_env_vars(merged, env_map)


def merge_configs(
    base: dict[str, Any],
    override: dict[str, Any],
    *,
    _path: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Base 위에 Override 를 deep merge 한 새 dict 를 반환.

    - Mapping 끼리는 재귀적으로 병합.
    - 그 외 (scalar, list) 는 override 값으로 교체.
    - 최상위 레벨에서 `_OVERRIDE_DENYLIST` 에 속한 키는 경고 후 무시.
    """
    result: dict[str, Any] = deepcopy(base)

    for key, ov_val in override.items():
        full_key = ".".join((*_path, key))

        # 최상위 denylist 체크 (중첩 필드는 허용 필드 아래에서 자유롭게 override 가능)
        if not _path and key in _OVERRIDE_DENYLIST:
            logger.warning(
                "override for '%s' is not allowed; ignoring (code-tied field)",
                full_key,
            )
            continue

        base_val = result.get(key)
        if isinstance(base_val, dict) and isinstance(ov_val, dict):
            result[key] = merge_configs(base_val, ov_val, _path=(*_path, key))
        else:
            result[key] = deepcopy(ov_val)

    return result


def substitute_env_vars(value: Any, env: dict[str, str]) -> Any:  # noqa: ANN401
    """config 트리 전체를 순회하며 문자열 안의 `${VAR}` 를 env 에서 치환.

    - 치환 대상 형식: `${VAR_NAME}` 또는 `${VAR_NAME:-default}`.
    - 문자열 내부에 여러 참조가 있으면 모두 치환.
    - 치환할 변수가 env 에도 없고 default 도 없으면 빈 문자열로 치환 (경고 로그).
    """
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: _resolve_env(m.group(1), m.group(2), env), value)
    if isinstance(value, list):
        return [substitute_env_vars(v, env) for v in value]
    if isinstance(value, dict):
        return {k: substitute_env_vars(v, env) for k, v in value.items()}
    return value


def _resolve_env(name: str, default: str | None, env: dict[str, str]) -> str:
    if name in env:
        return env[name]
    if default is not None:
        return default
    logger.warning("env var '%s' not set and no default provided; substituting empty string", name)
    return ""


def _read_yaml(path: Path) -> Any:  # noqa: ANN401
    if not path.exists():
        raise ConfigLoadError(f"config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"failed to parse {path}: {e}") from e
