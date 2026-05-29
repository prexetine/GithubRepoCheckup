import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.utils.yaml_config import load_simple_yaml


@dataclass(frozen=True)
class Settings:
    app_name: str
    github_api_base: str
    github_token: str | None
    request_timeout_seconds: int
    ai_request_timeout_seconds: int
    llm_config_path: str
    cache_ttl_seconds: int


@lru_cache
def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parent.parent
    llm_config_path = os.getenv(
        "LLM_CONFIG_PATH",
        str(base_dir / "models" / "config.yaml"),
    )
    yaml_data: dict[str, str] = {}
    try:
        yaml_data = load_simple_yaml(llm_config_path)
    except Exception:
        yaml_data = {}

    return Settings(
        app_name=os.getenv("APP_NAME", "Github Repo Checkup"),
        github_api_base=os.getenv("GITHUB_API_BASE", "https://api.github.com"),
        github_token=os.getenv("GITHUB_TOKEN") or yaml_data.get("github_token"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        ai_request_timeout_seconds=int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "45")),
        llm_config_path=llm_config_path,
        cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
    )
