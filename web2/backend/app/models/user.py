from dataclasses import dataclass


@dataclass
class User:
    username: str
    password_hash: str
    membership_level: str
    expire_date: str
    is_active: bool
