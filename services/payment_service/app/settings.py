from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGEPAY_", env_file=".env", extra="ignore")

    service_name: str = "payment-service"
    database_url: str = "postgresql+asyncpg://forgepay:forgepay@localhost:5432/forgepay"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_events: str = "forgepay.events"
    webhook_max_attempts: int = 6
    webhook_secret_master_key: str = Field(default="dev-only-local-master-key")
