from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clinora"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://clinora:clinora@localhost:5432/clinora"
    jwt_secret_key: str = "change-this-before-use"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 45
    refresh_token_days: int = 30
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    google_maps_api_key: str = ""
    google_client_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    password_reset_minutes: int = 20
    frontend_base_url: str = "http://localhost:5173"
    calendar_api_base_url: str = "https://calendar-api-d7a8.onrender.com"
    cors_origins: str = "http://localhost:5173"
    upload_dir: str = "private_uploads"
    max_upload_mb: int = 10
    app_timezone: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
