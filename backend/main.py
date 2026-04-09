from __future__ import annotations

import os
import re
from pathlib import Path

from flask import Flask, jsonify, request

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

from db import Database, decimal_to_tenths, display_name_from_user_row, tenths_to_number
from telegram_auth import InitDataValidationError, validate_init_data


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()
BOT_APP_SHORT_NAME = os.getenv("BOT_APP_SHORT_NAME", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "main.db"))
INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("INIT_DATA_MAX_AGE_SECONDS", "86400"))
MIN_WITHDRAW_CRYSTALS = tenths_to_number(decimal_to_tenths(os.getenv("MIN_WITHDRAW_CRYSTALS", "10")))
MAX_WITHDRAW_CRYSTALS_PER_REQUEST = tenths_to_number(
    decimal_to_tenths(os.getenv("MAX_WITHDRAW_CRYSTALS_PER_REQUEST", "100"))
)
TON_RATE_PER_CRYSTAL = float(os.getenv("TON_RATE_PER_CRYSTAL", "0.01"))
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "").strip()
WITHDRAWAL_NOTE = "Вывод обрабатывается до 24 часов"
REFERRAL_TASK_MULTIPLIER_TENTHS = 3
FIRST_REFERRAL_TARGET = 3
SECOND_REFERRAL_TARGET = 10
REFERRAL_TARGET_STEP = 10
VALID_TASK_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_:-]{1,63}$")
VALID_REWARD_TYPES = {"crystal_multiplier", "crystals"}

db = Database(DATABASE_PATH)
db.migrate()

app = Flask(__name__)

CORS_ALLOWED_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "https://sklych.github.io").split(",")
    if origin.strip()
}


@app.after_request
def apply_cors_headers(response):
    origin = (request.headers.get("Origin") or "").strip().rstrip("/")
    if origin and origin in CORS_ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-Telegram-Init-Data, Authorization, X-Admin-Token"
        )
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "86400"
    return response


def ok(data: dict, status: int = 200):
    return jsonify({"ok": True, "data": data}), status


def error_response(code: str, message: str, status: int):
    return (
        jsonify(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                },
            }
        ),
        status,
    )


def extract_init_data_from_request() -> str | None:
    payload = request.get_json(silent=True) or {}
    return (
        payload.get("initData")
        or request.args.get("initData")
        or request.headers.get("X-Telegram-Init-Data")
    )


def extract_admin_token() -> str | None:
    payload = request.get_json(silent=True) or {}
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return (
        request.headers.get("X-Admin-Token")
        or payload.get("token")
    )


def require_admin_token():
    provided_token = (extract_admin_token() or "").strip()
    if not ADMIN_API_TOKEN:
        return error_response("ADMIN_TOKEN_NOT_CONFIGURED", "ADMIN_API_TOKEN не настроен.", 500)
    if not provided_token or provided_token != ADMIN_API_TOKEN:
        return error_response("FORBIDDEN", "Неверный admin token.", 403)
    return None


def parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def build_invite_url(uid: str) -> str | None:
    if not BOT_USERNAME:
        return None
    if BOT_APP_SHORT_NAME:
        return f"https://t.me/{BOT_USERNAME}/{BOT_APP_SHORT_NAME}?startapp={uid}"
    return f"https://t.me/{BOT_USERNAME}?startapp={uid}"


def normalize_referrer_uid(raw_ref: str | None) -> str | None:
    if not raw_ref:
        return None

    value = str(raw_ref).strip()
    if value.startswith("ref_"):
        value = value[4:]
    if value.startswith("ref:"):
        value = value[4:]

    return value or None


def serialize_user(row):
    if not row:
        return None
    return {
        "id": row["tg_uid"],
        "username": row["username"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "displayName": display_name_from_user_row(row),
        "avatarUrl": row["photo_url"],
        "languageCode": row["language_code"],
        "balance": tenths_to_number(int(row["crystals_balance_tenths"])),
        "bestScore": int(row["best_score"]),
    }


def serialize_leaderboard_row(row):
    return {
        "position": int(row["position"]),
        "bestScore": int(row["best_score"]),
        "username": row["username"],
        "firstName": row["first_name"],
        "displayName": display_name_from_user_row(row),
        "avatarUrl": row["photo_url"],
        "userId": row["tg_uid"],
    }


def leaderboard_name_from_row(row) -> str:
    return row["username"] or row["first_name"] or "Unknown"


def serialize_leaderboard_entry(row, kind: str):
    value = int(row["best_score"]) if kind == "distance" else int(row["referral_count"])
    value_label = f"{value} м" if kind == "distance" else str(value)

    return {
        "position": int(row["position"]),
        "value": value,
        "valueLabel": value_label,
        "username": row["username"],
        "firstName": row["first_name"],
        "displayName": leaderboard_name_from_row(row),
        "avatarUrl": row["photo_url"],
        "userId": row["tg_uid"],
    }


def build_reward_payload(reward_type: str, reward_value_tenths: int) -> dict:
    reward_value = tenths_to_number(int(reward_value_tenths))

    if reward_type == "crystal_multiplier":
        label = f"+{reward_value}x к множителю кристаллов"
    elif reward_type == "crystals":
        label = f"+{reward_value} кристаллов"
    else:
        label = str(reward_value)

    return {
        "kind": reward_type,
        "label": label,
        "value": reward_value,
    }


def serialize_task_definition(row, completed_task_keys: set[str]):
    task_key = row["task_key"]
    is_completed = task_key in completed_task_keys
    return {
        "id": task_key,
        "type": row["type"],
        "title": row["title"],
        "description": row["description"],
        "status": "completed" if is_completed else "pending",
        "reward": build_reward_payload(row["reward_type"], int(row["reward_value_tenths"])),
        "meta": {
            "canClaimViaClient": bool(row["client_completable"]),
        },
    }


def get_referral_targets(referral_count: int) -> list[int]:
    targets = [FIRST_REFERRAL_TARGET]
    next_target = SECOND_REFERRAL_TARGET

    while True:
        targets.append(next_target)
        if referral_count < next_target:
            break
        next_target += REFERRAL_TARGET_STEP

    return targets


def build_tasks_payload(uid: str) -> dict:
    user_row = db.get_user(uid)
    referral_count = db.get_referral_count(uid)
    completions = db.get_task_completions(uid)
    completed_task_keys = {row["task_key"] for row in completions}
    task_definitions = db.get_active_task_definitions()

    crystal_multiplier_tenths = 10
    for row in completions:
        if row["reward_type"] == "crystal_multiplier":
            crystal_multiplier_tenths += int(row["reward_value_tenths"])

    tasks = [serialize_task_definition(row, completed_task_keys) for row in task_definitions]

    for target in get_referral_targets(referral_count):
        is_completed = referral_count >= target
        if is_completed:
            crystal_multiplier_tenths += REFERRAL_TASK_MULTIPLIER_TENTHS

        tasks.append(
            {
                "id": f"invite_{target}",
                "type": "invite_users",
                "title": f"Пригласить {target} пользователей",
                "description": "Это задание засчитывается автоматически по количеству приглашённых рефералов.",
                "status": "completed" if is_completed else "pending",
                "reward": {
                    "kind": "crystal_multiplier",
                    "label": "+0.3x к множителю кристаллов",
                    "value": 0.3,
                },
                "meta": {
                    "current": referral_count,
                    "target": target,
                    "canClaimViaClient": False,
                },
            }
        )

    return {
        "items": tasks,
        "referralCount": referral_count,
        "crystalMultiplier": tenths_to_number(crystal_multiplier_tenths),
        "balance": tenths_to_number(int(user_row["crystals_balance_tenths"])) if user_row else 0,
        "inviteUrl": build_invite_url(uid),
    }


def get_authenticated_user():
    init_data = extract_init_data_from_request()
    if not init_data:
        return None, error_response(
            "INIT_DATA_REQUIRED",
            "Не удалось получить Telegram initData.",
            401,
        )

    try:
        telegram_init = validate_init_data(
            init_data=init_data,
            bot_token=BOT_TOKEN,
            max_age_seconds=INIT_DATA_MAX_AGE_SECONDS,
        )
    except InitDataValidationError as error:
        return None, error_response(
            "INVALID_INIT_DATA",
            f"Не удалось подтвердить вход через Telegram: {error}.",
            401,
        )

    user_row = db.upsert_user(telegram_init.user)
    return (telegram_init, user_row), None


@app.route("/api/health", methods=["GET"])
def health():
    return ok({"status": "ok"})


@app.route("/api/auth/init", methods=["POST"])
def auth_init():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    telegram_init, user_row = auth_result
    payload = request.get_json(silent=True) or {}

    referrer_uid = normalize_referrer_uid(
        payload.get("ref") or payload.get("referrerUid") or telegram_init.start_param
    )
    if referrer_uid:
        db.link_referral(referrer_uid=str(referrer_uid), referred_uid=str(user_row["tg_uid"]))

    user_row = db.get_user(user_row["tg_uid"])
    referrals_count = db.get_referral_count(user_row["tg_uid"])
    leaderboard_row = db.get_user_rank(user_row["tg_uid"])
    tasks_payload = build_tasks_payload(user_row["tg_uid"])

    return ok(
        {
            "user": serialize_user(user_row),
            "referral": {
                "count": referrals_count,
                "inviteCode": user_row["tg_uid"],
                "inviteUrl": build_invite_url(user_row["tg_uid"]),
                "referrerUid": user_row["referrer_uid"],
            },
            "leaderboard": {
                "currentPosition": int(leaderboard_row["position"]) if leaderboard_row else None,
            },
            "withdraw": {
                "minAmount": MIN_WITHDRAW_CRYSTALS,
                "maxAmount": MAX_WITHDRAW_CRYSTALS_PER_REQUEST,
                "tonRatePerCrystal": TON_RATE_PER_CRYSTAL,
                "processingText": WITHDRAWAL_NOTE,
            },
            "tasks": tasks_payload,
        }
    )


@app.route("/api/game/finish", methods=["POST"])
def game_finish():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    _, user_row = auth_result
    payload = request.get_json(silent=True) or {}

    score = payload.get("score", 0)
    crystals_earned = payload.get("crystalsEarned", 0)

    try:
        score = max(0, int(score))
        crystals_earned_tenths = max(0, decimal_to_tenths(crystals_earned))
    except ValueError:
        return error_response("INVALID_GAME_RESULT", "Некорректный результат игры.", 400)

    updated_user = db.update_game_result(user_row["tg_uid"], score, crystals_earned_tenths)
    rank_row = db.get_user_rank(user_row["tg_uid"])

    return ok(
        {
            "user": serialize_user(updated_user),
            "leaderboard": {
                "currentPosition": int(rank_row["position"]) if rank_row else None,
            },
        }
    )


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    _, user_row = auth_result
    kind = (request.args.get("kind") or "distance").strip().lower()
    if kind not in {"distance", "referrals"}:
        return error_response("LEADERBOARD_KIND_INVALID", "kind должен быть distance или referrals.", 400)

    if kind == "referrals":
        top_rows = db.get_referral_leaderboard(limit=10)
        current_row = db.get_referral_user_rank(user_row["tg_uid"])
    else:
        top_rows = db.get_distance_leaderboard(limit=10)
        current_row = db.get_distance_user_rank(user_row["tg_uid"])

    return ok(
        {
            "kind": kind,
            "top": [serialize_leaderboard_entry(row, kind) for row in top_rows],
            "currentUser": serialize_leaderboard_entry(current_row, kind) if current_row else None,
            "inviteUrl": build_invite_url(user_row["tg_uid"]),
        }
    )


@app.route("/api/tasks", methods=["GET"])
def tasks():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    _, user_row = auth_result
    return ok(build_tasks_payload(user_row["tg_uid"]))


@app.route("/api/tasks/complete-task", methods=["POST"])
def complete_task():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    _, user_row = auth_result
    payload = request.get_json(silent=True) or {}
    task_id = (
        payload.get("taskId")
        or payload.get("task_id")
        or payload.get("id")
    )

    if not task_id:
        return error_response("TASK_ID_REQUIRED", "Нужно передать идентификатор задания.", 400)

    task_definition = db.get_task_definition(task_id)
    if task_definition and not bool(task_definition["is_active"]):
        task_definition = None

    if not task_definition and str(task_id).startswith("invite_"):
        return error_response(
            "TASK_NOT_CLIENT_COMPLETABLE",
            "Это задание выполняется только на backend.",
            400,
        )

    if not task_definition:
        return error_response("TASK_NOT_FOUND", "Задание не найдено.", 404)

    if not bool(task_definition["client_completable"]):
        return error_response(
            "TASK_NOT_CLIENT_COMPLETABLE",
            "Это задание нельзя выполнить с клиента.",
            400,
        )

    completed = db.complete_task(
        uid=user_row["tg_uid"],
        task_key=task_definition["task_key"],
        reward_type=task_definition["reward_type"],
        reward_value_tenths=int(task_definition["reward_value_tenths"]),
    )
    if not completed:
        return error_response("TASK_ALREADY_COMPLETED", "Это задание уже выполнено.", 400)

    return ok(build_tasks_payload(user_row["tg_uid"]))


@app.route("/api/admin/tasks", methods=["POST"])
def create_task():
    admin_error = require_admin_token()
    if admin_error:
        return admin_error

    payload = request.get_json(silent=True) or {}

    task_key = str(
        payload.get("taskId")
        or payload.get("task_id")
        or payload.get("id")
        or ""
    ).strip()
    task_type = str(payload.get("type") or "custom").strip()
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    reward_type = str(payload.get("rewardType") or payload.get("reward_type") or "").strip()
    client_completable = parse_bool(payload.get("clientCompletable"), True)
    is_active = parse_bool(payload.get("isActive"), True)
    sort_order = payload.get("sortOrder", 100)

    if not task_key:
        return error_response("TASK_ID_REQUIRED", "Нужно передать task id.", 400)
    if not VALID_TASK_KEY_PATTERN.match(task_key):
        return error_response("TASK_ID_INVALID", "task id должен содержать только латиницу, цифры, _, : или -.", 400)
    if not title:
        return error_response("TASK_TITLE_REQUIRED", "Нужно передать title.", 400)
    if not description:
        return error_response("TASK_DESCRIPTION_REQUIRED", "Нужно передать description.", 400)
    if reward_type not in VALID_REWARD_TYPES:
        return error_response("TASK_REWARD_TYPE_INVALID", "rewardType должен быть crystal_multiplier или crystals.", 400)

    try:
        reward_value_tenths = decimal_to_tenths(payload.get("rewardValue") or payload.get("reward_value"))
    except ValueError:
        return error_response("TASK_REWARD_VALUE_INVALID", "Некорректное значение rewardValue.", 400)

    if reward_value_tenths <= 0:
        return error_response("TASK_REWARD_VALUE_INVALID", "rewardValue должен быть больше нуля.", 400)

    try:
        sort_order = int(sort_order)
    except (TypeError, ValueError):
        return error_response("TASK_SORT_ORDER_INVALID", "sortOrder должен быть целым числом.", 400)

    existing_task = db.get_task_definition(task_key)
    if existing_task:
        return error_response("TASK_ALREADY_EXISTS", "Задание с таким id уже существует.", 400)

    created_task = db.create_task_definition(
        task_key=task_key,
        task_type=task_type,
        title=title,
        description=description,
        reward_type=reward_type,
        reward_value_tenths=reward_value_tenths,
        pending_reason=None,
        client_completable=client_completable,
        is_active=is_active,
        sort_order=sort_order,
    )

    return ok(
        {
            "task": {
                "id": created_task["task_key"],
                "type": created_task["type"],
                "title": created_task["title"],
                "description": created_task["description"],
                "reward": build_reward_payload(
                    created_task["reward_type"],
                    int(created_task["reward_value_tenths"]),
                ),
                "clientCompletable": bool(created_task["client_completable"]),
                "isActive": bool(created_task["is_active"]),
                "sortOrder": int(created_task["sort_order"]),
            }
        },
        201,
    )


@app.route("/api/withdraw/request", methods=["POST"])
def withdraw_request():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    _, user_row = auth_result
    payload = request.get_json(silent=True) or {}

    amount = payload.get("amount")
    if amount is None:
        return error_response("WITHDRAW_AMOUNT_REQUIRED", "Нужно указать сумму вывода.", 400)

    wallet_info = payload.get("wallet_info") or payload.get("walletInfo")
    if not isinstance(wallet_info, dict):
        return error_response(
            "WALLET_INFO_REQUIRED",
            "Нужно передать wallet_info из TON Connect.",
            400,
        )

    try:
        amount_tenths = decimal_to_tenths(amount)
    except ValueError:
        return error_response("WITHDRAW_AMOUNT_INVALID", "Некорректная сумма вывода.", 400)

    if tenths_to_number(amount_tenths) < MIN_WITHDRAW_CRYSTALS:
        return error_response(
            "WITHDRAW_AMOUNT_TOO_SMALL",
            f"Минимальная сумма вывода: {MIN_WITHDRAW_CRYSTALS}",
            400,
        )

    try:
        result = db.create_withdrawal_request(
            uid=user_row["tg_uid"],
            amount_tenths=amount_tenths,
            wallet_info=wallet_info,
            max_amount_tenths=decimal_to_tenths(MAX_WITHDRAW_CRYSTALS_PER_REQUEST),
            note=WITHDRAWAL_NOTE,
        )
    except ValueError as error:
        message = str(error)
        status = 400
        code = {
            "Insufficient balance": "INSUFFICIENT_BALANCE",
            "Amount must be greater than zero": "WITHDRAW_AMOUNT_INVALID",
            "User not found": "USER_NOT_FOUND",
            "Wallet info is invalid": "WALLET_INFO_INVALID",
            "Wallet address is missing": "WALLET_ADDRESS_MISSING",
            "Pending withdrawal request already exists for this user or wallet": "WITHDRAW_ALREADY_PENDING",
            "Withdrawal amount exceeds the per-request limit": "WITHDRAW_AMOUNT_TOO_LARGE",
        }.get(message, "WITHDRAW_FAILED")
        if message == "Withdrawal amount exceeds the per-request limit":
            message = f"Нельзя вывести более {MAX_WITHDRAW_CRYSTALS_PER_REQUEST} за раз."
        elif message == "Pending withdrawal request already exists for this user or wallet":
            message = "Нельзя создать больше одной транзакции, пока предыдущая в обработке."
        return error_response(code, message, status)

    updated_user = db.get_user(user_row["tg_uid"])

    return ok(
        {
            "requestId": result.request_id,
            "status": "pending",
            "walletAddress": result.wallet_address,
            "balance": tenths_to_number(result.remaining_balance_tenths),
            "processingText": WITHDRAWAL_NOTE,
            "user": serialize_user(updated_user),
        }
    )


@app.route("/api/withdraw/history", methods=["GET"])
def withdraw_history():
    auth_result, auth_error = get_authenticated_user()
    if auth_error:
        return auth_error

    _, user_row = auth_result
    rows = db.get_recent_withdrawals(user_row["tg_uid"])
    return ok(
        {
            "items": [
                {
                    "id": int(row["id"]),
                    "amount": tenths_to_number(int(row["amount_tenths"])),
                    "walletAddress": row["wallet_address"],
                    "status": row["status"],
                    "note": row["note"],
                    "createdAt": row["created_at"],
                    "completedAt": row["completed_at"],
                }
                for row in rows
            ]
        }
    )


@app.route("/api/admin/withdraw/complete", methods=["POST"])
def complete_withdrawals():
    admin_error = require_admin_token()
    if admin_error:
        return admin_error

    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids")
    if not isinstance(ids, list):
        return error_response("IDS_REQUIRED", "Нужно передать список ids.", 400)

    try:
        result = db.complete_withdrawal_requests(ids)
    except (TypeError, ValueError):
        return error_response("IDS_INVALID", "ids должны содержать положительные числа.", 400)

    return ok(
        {
            "completedIds": result["completed_ids"],
            "alreadyCompletedIds": result["already_completed_ids"],
            "notFoundIds": result["not_found_ids"],
        }
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        debug=os.getenv("DEBUG", "true").lower() == "true",
    )
