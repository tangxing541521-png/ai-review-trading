from pathlib import Path


class Settings:
    # Web2/backend/app/core/config.py -> ai-review-trading
    project_root = Path(__file__).resolve().parents[4]
    sqlite_path = project_root / "web2" / "backend" / "web2.sqlite3"
    users_path = project_root / "users.json"
    secret_key = "local-dev-secret-change-before-production"
    algorithm = "HS256"
    access_token_minutes = 60 * 12
    cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    disclaimer = "本系统仅用于学习研究和模拟验证，不构成任何投资建议，不承诺收益，交易风险自担。"


settings = Settings()
