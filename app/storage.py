import json
import tempfile
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.logging import get_logger

logger = get_logger(__name__)


class AccountState(BaseModel):
    status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    failure_count: int = 0
    last_error: str | None = None
    last_used: str | None = None
    request_count: int = 0


class RuntimeState(BaseModel):
    active_account: str | None = None
    last_rotation: str | None = None
    accounts: dict[str, AccountState] = {}


class StateManager:
    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file
        self._lock = threading.RLock()
        self._state = RuntimeState()
        self._dirty = False
        self._last_save: float = 0.0

    def load(self) -> None:
        with self._lock:
            if not self._state_file.exists():
                self._state = RuntimeState()
                return
            try:
                with open(self._state_file) as f:
                    raw = json.load(f)
                self._state = RuntimeState.model_validate(raw) if raw else RuntimeState()
            except (json.JSONDecodeError, ValueError, KeyError):
                logger.warning("state_file_corrupt", path=str(self._state_file))
                self._state = RuntimeState()

    def save(self) -> None:
        with self._lock:
            self._do_save()

    def _do_save(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", dir=self._state_file.parent, delete=False, suffix=".tmp") as tf:
                tf.write(self._state.model_dump_json(indent=2))
                tmp_path = tf.name
            import os

            os.replace(tmp_path, str(self._state_file))
            self._dirty = False
            self._last_save = time.time()
        except OSError as e:
            logger.error("state_save_failed", error=str(e))

    def get_active_account(self) -> str | None:
        with self._lock:
            return self._state.active_account

    def set_active_account(self, account_id: str) -> None:
        with self._lock:
            self._state.active_account = account_id
            self._dirty = True

    def record_failure(self, account_id: str, error: str) -> None:
        with self._lock:
            state = self._state.accounts.setdefault(account_id, AccountState())
            state.status = "unhealthy"
            state.failure_count += 1
            state.last_error = error
            state.last_used = _now_iso()
            self._dirty = True

    def record_success(self, account_id: str) -> None:
        with self._lock:
            state = self._state.accounts.setdefault(account_id, AccountState())
            state.status = "healthy"
            state.last_used = _now_iso()
            self._dirty = True

    def record_request(self, account_id: str) -> None:
        with self._lock:
            state = self._state.accounts.setdefault(account_id, AccountState())
            state.request_count += 1
            self._dirty = True

    def set_status(self, account_id: str, status: Literal["healthy", "unhealthy", "unknown"]) -> None:
        with self._lock:
            state = self._state.accounts.setdefault(account_id, AccountState())
            state.status = status
            self._dirty = True

    def get_account_state(self, account_id: str) -> AccountState:
        with self._lock:
            return self._state.accounts.get(account_id, AccountState())

    def get_all_account_states(self) -> dict[str, AccountState]:
        with self._lock:
            return dict(self._state.accounts)

    def auto_save(self, interval: float = 2.0) -> None:
        while True:
            time.sleep(interval)
            with self._lock:
                if self._dirty:
                    self._do_save()


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.UTC).isoformat()
