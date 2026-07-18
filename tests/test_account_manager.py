import json
import threading


def test_load(account_manager):
    accounts = account_manager.get_all()
    assert len(accounts) == 3
    assert account_manager.get_active() is not None


def test_select(account_manager):
    account_manager.select("acc-2")
    active = account_manager.get_active()
    assert active is not None
    assert active.id == "acc-2"


def test_rotate(account_manager):
    first = account_manager.rotate()
    assert first is not None
    second = account_manager.rotate()
    assert second is not None
    assert first.id != second.id


def test_rotate_skips_unhealthy(account_manager):
    account_manager.mark_unhealthy("acc-1")
    account_manager.mark_unhealthy("acc-2")
    acc = account_manager.rotate()
    assert acc is not None
    assert acc.id == "acc-3"


def test_rotate_all_unhealthy(account_manager):
    for a in account_manager.get_all():
        account_manager.mark_unhealthy(a.id)
    acc = account_manager.rotate()
    assert acc is None


def test_mark_healthy(account_manager):
    account_manager.mark_unhealthy("acc-1")
    assert account_manager.is_healthy("acc-1") is False
    account_manager.mark_healthy("acc-1")
    assert account_manager.is_healthy("acc-1") is True


def test_concurrent_access(account_manager):
    errors = []

    def worker():
        try:
            for _ in range(100):
                account_manager.rotate()
                account_manager.mark_unhealthy("acc-1")
                account_manager.mark_healthy("acc-1")
                account_manager.get_active()
                account_manager.get_all()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors


def test_reload(account_manager, temp_accounts_file):
    with open(temp_accounts_file) as f:
        data = json.load(f)
    data["accounts"].append({"id": "acc-4", "email": "u4@x.com", "api_key": "k4"})
    with open(temp_accounts_file, "w") as f:
        json.dump(data, f)

    account_manager.load()
    assert len(account_manager.get_all()) == 4
