from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "main.db"

_lock = Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decimal_to_tenths(value) -> int:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError("Invalid decimal value") from error

    return int((decimal_value * Decimal("10")).quantize(Decimal("1")))


def tenths_to_number(value: int):
    if value % 10 == 0:
        return value // 10
    return value / 10


def display_name_from_user_row(row: sqlite3.Row) -> str:
    username = row["username"] or ""
    first_name = row["first_name"] or ""
    last_name = row["last_name"] or ""

    if username:
        return username

    full_name = f"{first_name} {last_name}".strip()
    return full_name or "Unknown"


@dataclass
class WithdrawCreationResult:
    request_id: int
    remaining_balance_tenths: int
    wallet_address: str
    wallet_info_json: str


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = str(path)

    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def migrate(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    tg_uid TEXT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    photo_url TEXT,
                    language_code TEXT,
                    best_score INTEGER NOT NULL DEFAULT 0,
                    crystals_balance_tenths INTEGER NOT NULL DEFAULT 0,
                    wallet_address TEXT,
                    referrer_uid TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_uid TEXT NOT NULL,
                    referred_uid TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    UNIQUE(referrer_uid, referred_uid)
                );

                CREATE TABLE IF NOT EXISTS task_completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_uid TEXT NOT NULL,
                    task_key TEXT NOT NULL,
                    reward_type TEXT NOT NULL,
                    reward_value_tenths INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    UNIQUE(tg_uid, task_key)
                );

                CREATE TABLE IF NOT EXISTS task_definitions (
                    task_key TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reward_type TEXT NOT NULL,
                    reward_value_tenths INTEGER NOT NULL,
                    pending_reason TEXT,
                    client_completable INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS withdrawal_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_uid TEXT NOT NULL,
                    amount_tenths INTEGER NOT NULL,
                    wallet_address TEXT NOT NULL,
                    wallet_info TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_users_best_score
                ON users(best_score DESC, tg_uid ASC);

                CREATE INDEX IF NOT EXISTS idx_referrals_referrer_uid
                ON referrals(referrer_uid);

                CREATE INDEX IF NOT EXISTS idx_task_completions_tg_uid
                ON task_completions(tg_uid, task_key);

                CREATE INDEX IF NOT EXISTS idx_task_definitions_active_sort
                ON task_definitions(is_active, sort_order, created_at);

                CREATE INDEX IF NOT EXISTS idx_withdrawals_tg_uid
                ON withdrawal_requests(tg_uid, created_at DESC);

                CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_withdrawal_uid_unique
                ON withdrawal_requests(tg_uid)
                WHERE status = 'pending';

                CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_withdrawal_wallet_unique
                ON withdrawal_requests(wallet_address)
                WHERE status = 'pending';
                """
            )
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(withdrawal_requests)").fetchall()
            }
            if "wallet_info" not in columns:
                conn.execute("ALTER TABLE withdrawal_requests ADD COLUMN wallet_info TEXT")
            if "completed_at" not in columns:
                conn.execute("ALTER TABLE withdrawal_requests ADD COLUMN completed_at TEXT")
            task_definition_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(task_definitions)").fetchall()
            }
            if task_definition_columns and "pending_reason" not in task_definition_columns:
                conn.execute("ALTER TABLE task_definitions ADD COLUMN pending_reason TEXT")
            if task_definition_columns and "client_completable" not in task_definition_columns:
                conn.execute(
                    "ALTER TABLE task_definitions ADD COLUMN client_completable INTEGER NOT NULL DEFAULT 0"
                )
            if task_definition_columns and "is_active" not in task_definition_columns:
                conn.execute("ALTER TABLE task_definitions ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
            if task_definition_columns and "sort_order" not in task_definition_columns:
                conn.execute("ALTER TABLE task_definitions ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                """
                INSERT OR IGNORE INTO task_definitions (
                    task_key,
                    type,
                    title,
                    description,
                    reward_type,
                    reward_value_tenths,
                    pending_reason,
                    client_completable,
                    is_active,
                    sort_order,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "share_app",
                    "share",
                    "Рассказать друзьям",
                    "Поделись приложением через Telegram.",
                    "crystal_multiplier",
                    1,
                    "Поделись приложением, чтобы завершить задание.",
                    1,
                    1,
                    10,
                    now_iso(),
                    now_iso(),
                ),
            )

    def upsert_user(self, telegram_user: dict) -> sqlite3.Row:
        uid = str(telegram_user["id"])
        timestamp = now_iso()

        with _lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (
                        tg_uid, username, first_name, last_name, photo_url, language_code,
                        best_score, crystals_balance_tenths, wallet_address, referrer_uid,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0, NULL, NULL, ?, ?)
                    ON CONFLICT(tg_uid) DO UPDATE SET
                        username = excluded.username,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name,
                        photo_url = excluded.photo_url,
                        language_code = excluded.language_code,
                        updated_at = excluded.updated_at
                    """,
                    (
                        uid,
                        telegram_user.get("username"),
                        telegram_user.get("first_name"),
                        telegram_user.get("last_name"),
                        telegram_user.get("photo_url"),
                        telegram_user.get("language_code"),
                        timestamp,
                        timestamp,
                    ),
                )
                return conn.execute(
                    "SELECT * FROM users WHERE tg_uid = ?",
                    (uid,),
                ).fetchone()

    def get_user(self, uid: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE tg_uid = ?",
                (str(uid),),
            ).fetchone()

    def set_user_balance_tenths(self, uid: str, balance_tenths: int) -> sqlite3.Row | None:
        uid = str(uid)
        with _lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET crystals_balance_tenths = ?, updated_at = ?
                    WHERE tg_uid = ?
                    """,
                    (int(balance_tenths), now_iso(), uid),
                )
                return conn.execute(
                    "SELECT * FROM users WHERE tg_uid = ?",
                    (uid,),
                ).fetchone()

    def link_referral(self, referrer_uid: str | None, referred_uid: str) -> bool:
        if not referrer_uid:
            return False

        referrer_uid = str(referrer_uid)
        referred_uid = str(referred_uid)

        if referrer_uid == referred_uid:
            return False

        with _lock:
            with self.connection() as conn:
                referrer = conn.execute(
                    "SELECT 1 FROM users WHERE tg_uid = ?",
                    (referrer_uid,),
                ).fetchone()
                if not referrer:
                    return False

                existing_referral = conn.execute(
                    "SELECT 1 FROM referrals WHERE referred_uid = ?",
                    (referred_uid,),
                ).fetchone()
                if existing_referral:
                    return False

                conn.execute(
                    """
                    INSERT OR IGNORE INTO referrals (referrer_uid, referred_uid, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (referrer_uid, referred_uid, now_iso()),
                )
                conn.execute(
                    """
                    UPDATE users
                    SET referrer_uid = COALESCE(referrer_uid, ?), updated_at = ?
                    WHERE tg_uid = ?
                    """,
                    (referrer_uid, now_iso(), referred_uid),
                )
                return True

    def get_referral_count(self, uid: str) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM referrals WHERE referrer_uid = ?",
                (str(uid),),
            ).fetchone()
            return int(row["count"]) if row else 0

    def add_mock_referrals(self, referrer_uid: str, count: int) -> list[str]:
        referrer_uid = str(referrer_uid)
        count = int(count)
        if count <= 0:
            return []

        created_uids: list[str] = []
        timestamp = now_iso()

        with _lock:
            with self.connection() as conn:
                referrer = conn.execute(
                    "SELECT 1 FROM users WHERE tg_uid = ?",
                    (referrer_uid,),
                ).fetchone()
                if not referrer:
                    raise ValueError("Referrer not found")

                for index in range(count):
                    referred_uid = f"mock_{referrer_uid}_{timestamp}_{index}".replace(":", "_").replace("+", "_")
                    conn.execute(
                        """
                        INSERT INTO users (
                            tg_uid, username, first_name, last_name, photo_url, language_code,
                            best_score, crystals_balance_tenths, wallet_address, referrer_uid,
                            created_at, updated_at
                        )
                        VALUES (?, NULL, ?, NULL, NULL, 'ru', 0, 0, NULL, ?, ?, ?)
                        """,
                        (
                            referred_uid,
                            f"Моковый друг {index + 1}",
                            referrer_uid,
                            timestamp,
                            timestamp,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO referrals (referrer_uid, referred_uid, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (referrer_uid, referred_uid, timestamp),
                    )
                    created_uids.append(referred_uid)

        return created_uids

    def get_task_completions(self, uid: str) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                """
                SELECT task_key, reward_type, reward_value_tenths, completed_at
                FROM task_completions
                WHERE tg_uid = ?
                ORDER BY completed_at ASC
                """,
                (str(uid),),
            ).fetchall()

    def get_active_task_definitions(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                """
                SELECT
                    task_key,
                    type,
                    title,
                    description,
                    reward_type,
                    reward_value_tenths,
                    pending_reason,
                    client_completable,
                    is_active,
                    sort_order,
                    created_at,
                    updated_at
                FROM task_definitions
                WHERE is_active = 1
                ORDER BY sort_order ASC, created_at ASC, task_key ASC
                """
            ).fetchall()

    def get_task_definition(self, task_key: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(
                """
                SELECT
                    task_key,
                    type,
                    title,
                    description,
                    reward_type,
                    reward_value_tenths,
                    pending_reason,
                    client_completable,
                    is_active,
                    sort_order,
                    created_at,
                    updated_at
                FROM task_definitions
                WHERE task_key = ?
                """,
                (str(task_key),),
            ).fetchone()

    def create_task_definition(
        self,
        task_key: str,
        task_type: str,
        title: str,
        description: str,
        reward_type: str,
        reward_value_tenths: int,
        pending_reason: str | None,
        client_completable: bool,
        is_active: bool,
        sort_order: int,
    ) -> sqlite3.Row:
        timestamp = now_iso()
        with _lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO task_definitions (
                        task_key,
                        type,
                        title,
                        description,
                        reward_type,
                        reward_value_tenths,
                        pending_reason,
                        client_completable,
                        is_active,
                        sort_order,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(task_key),
                        str(task_type),
                        title,
                        description,
                        str(reward_type),
                        int(reward_value_tenths),
                        pending_reason,
                        1 if client_completable else 0,
                        1 if is_active else 0,
                        int(sort_order),
                        timestamp,
                        timestamp,
                    ),
                )
                return conn.execute(
                    "SELECT * FROM task_definitions WHERE task_key = ?",
                    (str(task_key),),
                ).fetchone()

    def complete_task(
        self,
        uid: str,
        task_key: str,
        reward_type: str,
        reward_value_tenths: int,
    ) -> bool:
        with _lock:
            with self.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO task_completions (
                        tg_uid, task_key, reward_type, reward_value_tenths, completed_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (str(uid), task_key, reward_type, reward_value_tenths, now_iso()),
                )
                if cursor.rowcount > 0 and reward_type == "crystals":
                    conn.execute(
                        """
                        UPDATE users
                        SET crystals_balance_tenths = crystals_balance_tenths + ?, updated_at = ?
                        WHERE tg_uid = ?
                        """,
                        (int(reward_value_tenths), now_iso(), str(uid)),
                    )
                return cursor.rowcount > 0

    def update_game_result(self, uid: str, score: int, crystals_earned_tenths: int) -> sqlite3.Row:
        uid = str(uid)
        timestamp = now_iso()
        with _lock:
            with self.connection() as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET
                        best_score = CASE WHEN ? > best_score THEN ? ELSE best_score END,
                        crystals_balance_tenths = crystals_balance_tenths + ?,
                        updated_at = ?
                    WHERE tg_uid = ?
                    """,
                    (score, score, crystals_earned_tenths, timestamp, uid),
                )
                return conn.execute(
                    "SELECT * FROM users WHERE tg_uid = ?",
                    (uid,),
                ).fetchone()

    @staticmethod
    def extract_wallet_address(wallet_info: dict) -> str:
        if not isinstance(wallet_info, dict):
            raise ValueError("Wallet info is invalid")

        address = wallet_info.get("address")
        if not address and isinstance(wallet_info.get("account"), dict):
            address = wallet_info["account"].get("address")

        address = str(address or "").strip()
        if not address:
            raise ValueError("Wallet address is missing")

        return address

    def create_withdrawal_request(
        self,
        uid: str,
        amount_tenths: int,
        wallet_info: dict,
        max_amount_tenths: int,
        note: str,
    ) -> WithdrawCreationResult:
        uid = str(uid)
        wallet_address = self.extract_wallet_address(wallet_info)
        wallet_info_json = json.dumps(wallet_info, ensure_ascii=False, separators=(",", ":"))

        with _lock:
            with self.connection() as conn:
                row = conn.execute(
                    """
                    SELECT crystals_balance_tenths
                    FROM users
                    WHERE tg_uid = ?
                    """,
                    (uid,),
                ).fetchone()

                if not row:
                    raise ValueError("User not found")

                balance_tenths = int(row["crystals_balance_tenths"])
                if amount_tenths <= 0:
                    raise ValueError("Amount must be greater than zero")
                if amount_tenths > max_amount_tenths:
                    raise ValueError("Withdrawal amount exceeds the per-request limit")
                if balance_tenths < amount_tenths:
                    raise ValueError("Insufficient balance")

                pending_request = conn.execute(
                    """
                    SELECT id
                    FROM withdrawal_requests
                    WHERE status = 'pending' AND (tg_uid = ? OR wallet_address = ?)
                    LIMIT 1
                    """,
                    (uid, wallet_address),
                ).fetchone()
                if pending_request:
                    raise ValueError("Pending withdrawal request already exists for this user or wallet")

                conn.execute(
                    """
                    UPDATE users
                    SET crystals_balance_tenths = crystals_balance_tenths - ?, updated_at = ?
                    WHERE tg_uid = ?
                    """,
                    (amount_tenths, now_iso(), uid),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO withdrawal_requests (
                        tg_uid, amount_tenths, wallet_address, wallet_info, status, note, created_at
                    )
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (uid, amount_tenths, wallet_address, wallet_info_json, note, now_iso()),
                )

                updated_balance = conn.execute(
                    "SELECT crystals_balance_tenths FROM users WHERE tg_uid = ?",
                    (uid,),
                ).fetchone()

                return WithdrawCreationResult(
                    request_id=int(cursor.lastrowid),
                    remaining_balance_tenths=int(updated_balance["crystals_balance_tenths"]),
                    wallet_address=wallet_address,
                    wallet_info_json=wallet_info_json,
                )

    def get_distance_leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                """
                WITH ranked AS (
                    SELECT
                        tg_uid,
                        username,
                        first_name,
                        last_name,
                        photo_url,
                        best_score,
                        ROW_NUMBER() OVER (ORDER BY best_score DESC, tg_uid ASC) AS position
                    FROM users
                )
                SELECT *
                FROM ranked
                ORDER BY position ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def get_distance_user_rank(self, uid: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(
                """
                WITH ranked AS (
                    SELECT
                        tg_uid,
                        username,
                        first_name,
                        last_name,
                        photo_url,
                        best_score,
                        ROW_NUMBER() OVER (ORDER BY best_score DESC, tg_uid ASC) AS position
                    FROM users
                )
                SELECT *
                FROM ranked
                WHERE tg_uid = ?
                """,
                (str(uid),),
            ).fetchone()

    def get_referral_leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                """
                WITH referral_counts AS (
                    SELECT
                        u.tg_uid,
                        u.username,
                        u.first_name,
                        u.last_name,
                        u.photo_url,
                        COUNT(r.id) AS referral_count
                    FROM users u
                    LEFT JOIN referrals r ON r.referrer_uid = u.tg_uid
                    GROUP BY u.tg_uid, u.username, u.first_name, u.last_name, u.photo_url
                ),
                ranked AS (
                    SELECT
                        tg_uid,
                        username,
                        first_name,
                        last_name,
                        photo_url,
                        referral_count,
                        ROW_NUMBER() OVER (ORDER BY referral_count DESC, tg_uid ASC) AS position
                    FROM referral_counts
                )
                SELECT *
                FROM ranked
                ORDER BY position ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def get_referral_user_rank(self, uid: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(
                """
                WITH referral_counts AS (
                    SELECT
                        u.tg_uid,
                        u.username,
                        u.first_name,
                        u.last_name,
                        u.photo_url,
                        COUNT(r.id) AS referral_count
                    FROM users u
                    LEFT JOIN referrals r ON r.referrer_uid = u.tg_uid
                    GROUP BY u.tg_uid, u.username, u.first_name, u.last_name, u.photo_url
                ),
                ranked AS (
                    SELECT
                        tg_uid,
                        username,
                        first_name,
                        last_name,
                        photo_url,
                        referral_count,
                        ROW_NUMBER() OVER (ORDER BY referral_count DESC, tg_uid ASC) AS position
                    FROM referral_counts
                )
                SELECT *
                FROM ranked
                WHERE tg_uid = ?
                """,
                (str(uid),),
            ).fetchone()

    def get_leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.get_distance_leaderboard(limit=limit)

    def get_user_rank(self, uid: str) -> sqlite3.Row | None:
        return self.get_distance_user_rank(uid)

    def get_recent_withdrawals(self, uid: str, limit: int = 20) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                """
                SELECT id, amount_tenths, wallet_address, wallet_info, status, note, created_at, completed_at
                FROM withdrawal_requests
                WHERE tg_uid = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (str(uid), limit),
            ).fetchall()

    def get_completed_withdrawal_count(self, uid: str) -> int:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM withdrawal_requests
                WHERE tg_uid = ? AND status = 'completed'
                """,
                (str(uid),),
            ).fetchone()
            return int(row["count"]) if row else 0

    def complete_withdrawal_requests(self, ids: list[int]) -> dict:
        normalized_ids = []
        seen = set()
        for raw_id in ids:
            request_id = int(raw_id)
            if request_id > 0 and request_id not in seen:
                normalized_ids.append(request_id)
                seen.add(request_id)

        if not normalized_ids:
            return {
                "completed_ids": [],
                "already_completed_ids": [],
                "not_found_ids": [],
            }

        placeholders = ",".join("?" for _ in normalized_ids)

        with _lock:
            with self.connection() as conn:
                rows = conn.execute(
                    f"""
                    SELECT id, status
                    FROM withdrawal_requests
                    WHERE id IN ({placeholders})
                    """,
                    normalized_ids,
                ).fetchall()

                found_by_id = {int(row["id"]): row["status"] for row in rows}
                not_found_ids = [request_id for request_id in normalized_ids if request_id not in found_by_id]
                already_completed_ids = [
                    request_id
                    for request_id in normalized_ids
                    if found_by_id.get(request_id) == "completed"
                ]
                pending_ids = [
                    request_id
                    for request_id in normalized_ids
                    if found_by_id.get(request_id) == "pending"
                ]

                if pending_ids:
                    pending_placeholders = ",".join("?" for _ in pending_ids)
                    conn.execute(
                        f"""
                        UPDATE withdrawal_requests
                        SET status = 'completed', completed_at = ?
                        WHERE id IN ({pending_placeholders}) AND status = 'pending'
                        """,
                        [now_iso(), *pending_ids],
                    )

                return {
                    "completed_ids": pending_ids,
                    "already_completed_ids": already_completed_ids,
                    "not_found_ids": not_found_ids,
                }
