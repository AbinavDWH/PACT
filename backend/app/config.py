"""Runtime configuration. Everything has a working default so the app boots with no .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database -----------------------------------------------------------
    # Empty means "no Mongo configured": repositories fall back to in-memory
    # stores so the demo still runs when the venue wifi dies. See db/mongo.py.
    mongo_uri: str = ""
    mongo_db: str = "pact"

    # --- LLM ----------------------------------------------------------------
    groq_api_key: str = ""
    # Model availability is per-account. Verified present on this key;
    # llama-3.3-70b-versatile is NOT (404 model_not_found).
    groq_model: str = "openai/gpt-oss-120b"       # judgement: triage, arbiter
    groq_model_fast: str = "openai/gpt-oss-20b"   # volume: advocates, narrator
    groq_timeout_s: float = 6.0
    # Free tier is 8000 tokens/minute -- TPM binds long before RPM (1000/day).
    groq_max_inflight: int = 4

    # --- Admin gate ---------------------------------------------------------
    gate_timeout_s: int = 25
    autopilot: bool = True

    # --- Web credentials ----------------------------------------------------
    require_auth: bool = True
    pact_admin_user: str = "admin"
    pact_admin_pass: str = "pact-admin"
    # Shared organization-portal password. Seeded orgs carry web_pass_hash:
    # None; a per-org hash overrides this when one is set.
    pact_org_pass: str = "pact-org"

    # --- Privacy ------------------------------------------------------------
    # Key material for name_enc / phone_enc (privacy/crypto.py). Falls back to
    # the admin password so the app boots with no .env; set it properly in any
    # deployment that matters.
    pact_secret: str = ""

    # --- Demo ---------------------------------------------------------------
    # Deliberately slows event emission so judges can read the deliberation.
    # Groq at ~275 tok/s is too fast to follow; this is a presentation dial.
    demo_latency_ms: int = 0

    @property
    def mongo_enabled(self) -> bool:
        return bool(self.mongo_uri)

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
