import os


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "approval-service")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./approval_service.db")


settings = Settings()
