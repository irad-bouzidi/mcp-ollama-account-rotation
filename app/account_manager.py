import json
import threading
from pathlib import Path

from app.account import Account, AccountsFile


class AccountManager:
    def __init__(self, accounts_file: Path) -> None:
        self._accounts_file = accounts_file
        self._lock = threading.Lock()
        self._accounts: dict[str, Account] = {}
        self._healthy: set[str] = set()
        self._active: str | None = None
        self._rotation_index = 0
        self._sorted_ids: list[str] = []
        self._stop_event = threading.Event()

    def load(self) -> None:
        with self._lock:
            self._do_load()

    def _do_load(self) -> None:
        if not self._accounts_file.exists():
            self._accounts = {}
            self._healthy = set()
            self._active = None
            self._sorted_ids = []
            self._rotation_index = 0
            return
        with open(self._accounts_file) as f:
            raw = json.load(f)
        if isinstance(raw, list):
            raw = {"accounts": raw}
        accounts_file = AccountsFile.model_validate(raw)
        self._accounts = {a.id: a for a in accounts_file.accounts}
        self._healthy = {a.id for a in accounts_file.accounts if a.enabled}
        self._sorted_ids = sorted(a.id for a in accounts_file.accounts if a.enabled)
        if self._active is None and self._sorted_ids:
            self._active = self._sorted_ids[0]
        elif self._active is not None and self._active not in self._accounts:
            self._active = self._sorted_ids[0] if self._sorted_ids else None
        self._rotation_index = self._sorted_ids.index(self._active) if self._active in self._sorted_ids else 0

    def get_active(self) -> Account | None:
        with self._lock:
            if self._active is None:
                return None
            return self._accounts.get(self._active)

    def get_all(self) -> list[Account]:
        with self._lock:
            return [a for a in self._accounts.values() if a.enabled]

    def select(self, account_id: str) -> None:
        with self._lock:
            if account_id in self._accounts:
                self._active = account_id

    def mark_unhealthy(self, account_id: str) -> None:
        with self._lock:
            self._healthy.discard(account_id)

    def mark_healthy(self, account_id: str) -> None:
        with self._lock:
            if account_id in self._accounts and self._accounts[account_id].enabled:
                self._healthy.add(account_id)

    def is_healthy(self, account_id: str) -> bool:
        with self._lock:
            return account_id in self._healthy

    def rotate(self) -> Account | None:
        with self._lock:
            if not self._sorted_ids:
                return None
            healthy_ids = [aid for aid in self._sorted_ids if aid in self._healthy]
            if not healthy_ids:
                return None
            if self._rotation_index >= len(healthy_ids):
                self._rotation_index = 0
            selected = healthy_ids[self._rotation_index]
            self._rotation_index = (self._rotation_index + 1) % len(healthy_ids)
            self._active = selected
            return self._accounts.get(selected)

    async def start_watcher(self) -> None:
        from watchfiles import awatch

        self._stop_event.clear()
        async for _ in awatch(str(self._accounts_file.parent)):
            if self._stop_event.is_set():
                break
            self.load()

    def stop_watcher(self) -> None:
        self._stop_event.set()
