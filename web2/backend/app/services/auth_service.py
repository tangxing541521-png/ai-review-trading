import hashlib
import json
from datetime import date, datetime

from app.core.config import settings


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_users() -> list[dict]:
    if not settings.users_path.exists():
        return []
    try:
        return json.loads(settings.users_path.read_text(encoding="utf-8"))
    except Exception:
        return []


def get_user_by_username(username: str) -> dict | None:
    for user in load_users():
        if user.get("username") == username:
            return user
    return None


def user_has_member_access(user: dict) -> bool:
    if not user or not user.get("is_active"):
        return False
    if user.get("membership_level") == "admin":
        return True
    if user.get("membership_level") != "member":
        return False
    try:
        expire = datetime.strptime(user.get("expire_date", ""), "%Y-%m-%d").date()
        return expire >= date.today()
    except Exception:
        return False


def authenticate_user(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if not user or not user.get("is_active"):
        return None
    if user.get("password_hash") != hash_password(password):
        return None
    return user
