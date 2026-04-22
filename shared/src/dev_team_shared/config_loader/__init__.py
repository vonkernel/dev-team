"""Role Config 로더.

Base config (이미지 baked-in) 와 Override config (선택적 마운트) 를 deep merge.
`${ENV_VAR}` 참조는 로더가 환경변수에서 치환.
Override 가 허용되지 않은 필드는 경고 로그와 함께 무시.
"""

from dev_team_shared.config_loader.loader import (
    ConfigLoadError,
    load_config,
    merge_configs,
    substitute_env_vars,
)

__all__ = [
    "ConfigLoadError",
    "load_config",
    "merge_configs",
    "substitute_env_vars",
]
