from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataValidationError(ValueError):
    pass


@dataclass
class TelegramInitData:
    raw: str
    user: dict
    auth_date: int | None
    start_param: str | None
    query_id: str | None


def _build_check_string(data: dict) -> str:
    return "\n".join(f"{key}={value}" for key, value in sorted(data.items()))


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int | None = 86400,
) -> TelegramInitData:
    if not init_data:
        raise InitDataValidationError("initData is required")
    if not bot_token:
        raise InitDataValidationError("BOT_TOKEN is not configured")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise InitDataValidationError("Telegram hash is missing")

    data_check_string = _build_check_string(parsed)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataValidationError("Telegram initData signature is invalid")

    auth_date = int(parsed["auth_date"]) if parsed.get("auth_date") else None
    if auth_date and max_age_seconds is not None:
        if time.time() - auth_date > max_age_seconds:
            raise InitDataValidationError("Telegram initData is expired")

    raw_user = parsed.get("user")
    if not raw_user:
        raise InitDataValidationError("Telegram user payload is missing")

    try:
        user = json.loads(raw_user)
    except json.JSONDecodeError as error:
        raise InitDataValidationError("Telegram user payload is malformed") from error

    if "id" not in user:
        raise InitDataValidationError("Telegram user id is missing")

    return TelegramInitData(
        raw=init_data,
        user=user,
        auth_date=auth_date,
        start_param=parsed.get("start_param"),
        query_id=parsed.get("query_id"),
    )
