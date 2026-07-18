from app.retry import RoundRobinRotation


def test_round_robin_order():
    rot = RoundRobinRotation()
    ids = ["a", "b", "c"]
    result = rot.next(ids, lambda x: True)
    assert result == "a"
    result = rot.next(ids, lambda x: True)
    assert result == "b"
    result = rot.next(ids, lambda x: True)
    assert result == "c"
    result = rot.next(ids, lambda x: True)
    assert result == "a"


def test_skip_unhealthy():
    rot = RoundRobinRotation()
    ids = ["a", "b", "c"]
    result = rot.next(ids, lambda x: x != "b")
    assert result == "a"
    result = rot.next(ids, lambda x: x != "b")
    assert result == "c"
    result = rot.next(ids, lambda x: x != "b")
    assert result == "a"


def test_all_unhealthy():
    rot = RoundRobinRotation()
    result = rot.next(["a", "b"], lambda x: False)
    assert result is None


def test_empty_list():
    rot = RoundRobinRotation()
    result = rot.next([], lambda x: True)
    assert result is None
