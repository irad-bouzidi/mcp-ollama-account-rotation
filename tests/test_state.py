import threading

from app.storage import StateManager


def test_load_save(temp_state_file):
    sm = StateManager(temp_state_file)
    sm.load()
    assert sm.get_active_account() is None

    sm.set_active_account("acc-1")
    assert sm.get_active_account() == "acc-1"

    sm.save()

    sm2 = StateManager(temp_state_file)
    sm2.load()
    assert sm2.get_active_account() == "acc-1"


def test_record_failure_success(temp_state_file):
    sm = StateManager(temp_state_file)
    sm.load()

    sm.record_failure("acc-1", "Quota exceeded")
    state = sm.get_account_state("acc-1")
    assert state.status == "unhealthy"
    assert state.failure_count == 1
    assert state.last_error == "Quota exceeded"

    sm.record_success("acc-1")
    state = sm.get_account_state("acc-1")
    assert state.status == "healthy"


def test_record_request(temp_state_file):
    sm = StateManager(temp_state_file)
    sm.load()

    sm.record_request("acc-1")
    sm.record_request("acc-1")
    state = sm.get_account_state("acc-1")
    assert state.request_count == 2


def test_concurrent_mutations(temp_state_file):
    sm = StateManager(temp_state_file)
    sm.load()
    errors = []

    def worker():
        try:
            for _ in range(100):
                sm.record_request("acc-1")
                sm.record_failure("acc-1", "err")
                sm.record_success("acc-1")
                sm.get_active_account()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    state = sm.get_account_state("acc-1")
    assert state.request_count > 0
