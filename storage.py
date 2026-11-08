from typing import Any

USERS: dict[int, dict[str, Any]] = {}


def get_user(tg_id: int) -> dict[str, Any]:
    user = USERS.get(tg_id)
    if user is None:
        user = {
            "awaiting_profile": True,
            "profile_text": "",
            "tasks": [],
            "question_index": 0,
        }
        USERS[tg_id] = user
    return user


def save_user(tg_id: int, user: dict[str, Any]) -> None:
    USERS[tg_id] = user
