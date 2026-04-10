"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All application configuration. Loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/blackbook"

    # Session
    session_timeout_minutes: int = 5

    # LLM
    llm_provider: str = ""  # "anthropic" or "openai"
    llm_api_key: str = ""
    llm_api_url: str = ""
    llm_model: str = ""
    llm_max_attempts: int = 3  # total attempts (initial + retries)
    llm_context_max_chars: int = 8000  # max chars for company context in LLM prompts

    # File storage
    data_dir: str = "./data"

    # IMAP (email ingestion)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_poll_interval_seconds: int = 300

    # Coverage thresholds
    coverage_org_sparse: int = 3
    coverage_tech_sparse: int = 3
    coverage_process_sparse: int = 2
    coverage_cgkra_sparse: int = 3

    # Export cleanup
    export_ttl_hours: int = 72

    model_config = {"env_prefix": "BLACKBOOK_"}


settings = Settings()
