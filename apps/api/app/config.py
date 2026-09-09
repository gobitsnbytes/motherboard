from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_client_id: str = Field(validation_alias="DISCORD_CLIENT_ID")
    discord_client_secret: str = Field(validation_alias="DISCORD_CLIENT_SECRET")
    discord_bot_token: str = Field(validation_alias="DISCORD_BOT_TOKEN")
    discord_guild_id: str = Field(validation_alias="DISCORD_GUILD_ID")
    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    session_secret: str = Field(validation_alias="SESSION_SECRET")
    api_internal_secret: str = Field(validation_alias="API_INTERNAL_SECRET")
    nextauth_secret: str = Field(validation_alias="NEXTAUTH_SECRET")
    nextauth_url: str = Field(default="http://localhost:3000", validation_alias="NEXTAUTH_URL")
    api_url: str = Field(default="http://localhost:8000", validation_alias="API_URL")
    app_version: str = Field(default="0.85.5-beta", validation_alias="APP_VERSION")
    # Comma-separated list of allowed CORS origins (overrides nextauth_url for multi-origin setups)
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")
    sync_interval_minutes: int = Field(default=15, validation_alias="SYNC_INTERVAL_MINUTES")
    enable_sync_scheduler: bool = Field(default=False, validation_alias="ENABLE_SYNC_SCHEDULER")
    # RazorpayX API key — optional until real banking integration is wired
    razorpayx_api_key: str | None = Field(default=None, validation_alias="RAZORPAYX_API_KEY")

    # Finance governance (OKF Rule 35 / Authority Matrix §3.2):
    # commitments at or above the threshold need TWO distinct approvers
    # (neither may be the requester); FY runs 1 April – 31 March.
    finance_dual_approval_threshold_paise: int = Field(
        default=10_000_000, validation_alias="FINANCE_DUAL_APPROVAL_THRESHOLD_PAISE"
    )
    finance_dual_approval_enabled: bool = Field(
        default=True, validation_alias="FINANCE_DUAL_APPROVAL_ENABLED"
    )

    # RazorpayX credential pair — when both are set build_adapter() selects the
    # live adapter seam; unset (default) keeps the pure paper-ledger adapter.
    razorpayx_key_id: str | None = Field(default=None, validation_alias="RAZORPAYX_KEY_ID")
    razorpayx_secret: str | None = Field(default=None, validation_alias="RAZORPAYX_SECRET")

    # Gemini API settings
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")

    # Dyslexic uses its own model setting so sponsorship research and email
    # drafting can move independently of the meeting transcription pipeline.
    dyslexic_gemini_model: str = Field(
        default="gemini-3.6-flash", validation_alias="DYSLEXIC_GEMINI_MODEL"
    )

    # SMTP Mailer settings
    smtp_host: str | None = Field(default="mail.gobitsnbytes.org", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default="legal@gobitsnbytes.org", validation_alias="SMTP_USER")
    smtp_pass: str | None = Field(default=None, validation_alias="SMTP_PASS")
    smtp_from: str = Field(default="bits&bytes Legal <legal@gobitsnbytes.org>", validation_alias="SMTP_FROM")
    smtp_cc: str = Field(default="gobitsnbytes@gmail.com", validation_alias="SMTP_CC")
    smtp_bcc: str | None = Field(default="gobitsnbytes@gmail.com", validation_alias="SMTP_BCC")

    # SparkCloud Verification settings
    discord_cloud_approval_webhook_url: str | None = Field(default=None, validation_alias="DISCORD_CLOUD_APPROVAL_WEBHOOK_URL")
    sparkcloud_join_url: str = Field(default="https://sparkden.org/org/join/HJ6POGpRWhZRvT8jtEYqmMpMhmLiMOEo", validation_alias="SPARKCLOUD_JOIN_URL")

    # SparkCloud AI Proxy settings
    sparkcloud_api_key: str | None = Field(default=None, validation_alias="SPARKCLOUD_API_KEY")
    sparkcloud_base_url: str = Field(default="https://cloud.sparkden.org/api/ai/v1", validation_alias="SPARKCLOUD_BASE_URL")
    sparkcloud_model: str = Field(default="auto", validation_alias="SPARKCLOUD_MODEL")

    # Inbound Email Webhook Security
    inbound_email_webhook_secret: str | None = Field(default=None, validation_alias="INBOUND_EMAIL_WEBHOOK_SECRET")

    # Legal Agent inbox polling (Dottr-style email-native contract teammate).
    # Polling runs only when imap_host, imap_user and imap_password are set;
    # poll_seconds <= 0 disables the scheduled job entirely.
    legal_inbox_imap_host: str | None = Field(default=None, validation_alias="LEGAL_INBOX_IMAP_HOST")
    legal_inbox_imap_port: int = Field(default=993, validation_alias="LEGAL_INBOX_IMAP_PORT")
    legal_inbox_imap_user: str | None = Field(default=None, validation_alias="LEGAL_INBOX_IMAP_USER")
    legal_inbox_imap_password: str | None = Field(default=None, validation_alias="LEGAL_INBOX_IMAP_PASSWORD")
    legal_inbox_mailbox: str = Field(default="INBOX", validation_alias="LEGAL_INBOX_MAILBOX")
    legal_inbox_poll_seconds: int = Field(default=60, validation_alias="LEGAL_INBOX_POLL_SECONDS")
    legal_nudge_enabled: bool = Field(default=True, validation_alias="LEGAL_NUDGE_ENABLED")
    legal_org_mailbox: str = Field(default="legal@gobitsnbytes.org", validation_alias="LEGAL_ORG_MAILBOX")

    # Notion Sync Settings
    notion_token: str | None = Field(default=None, validation_alias="NOTION_TOKEN")
    notion_fork_registry_db: str = Field(default="a5472585-73cd-4f6c-99b8-40c7cb63ce9e", validation_alias="NOTION_FORK_REGISTRY_DB")
    notion_team_db: str | None = Field(default=None, validation_alias="NOTION_TEAM_DB")


    @property
    def allowed_cors_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or [self.nextauth_url]



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
