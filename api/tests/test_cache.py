"""Probability cache tests (docs/PRD.md 6.6)."""

import asyncio

import pytest

from app.cache import CachedEndor, cache_key
from app.gate.types import State
from tests.fakes import FakeClient

STATE: State = {"task": "build", "command": "npm run build"}


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _call(cache: CachedEndor, model: str = "m", state: State = STATE, question: str = "q"):
    return asyncio.run(cache.decide(model, state, question))


def test_identical_second_call_is_a_free_hit() -> None:
    inner = FakeClient(lambda _m, _s, _q: 0.7)
    cache = CachedEndor(inner, "v1")
    first, second = _call(cache), _call(cache)
    assert (first.cache_hit, second.cache_hit) == (False, True)
    assert second.p == first.p
    assert second.input_tokens == 0
    assert len(inner.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"model": "other"},
        {"question": "other question"},
        {"state": {"task": "build", "command": "npm run build "}},  # whitespace matters
        {"state": {"task": "Build", "command": "npm run build"}},  # case matters
    ],
)
def test_any_input_change_misses(change: dict[str, object]) -> None:
    inner = FakeClient(lambda _m, _s, _q: 0.7)
    cache = CachedEndor(inner, "v1")
    _call(cache)
    _call(cache, **change)  # type: ignore[arg-type]
    assert len(inner.calls) == 2


def test_gate_version_is_part_of_the_key() -> None:
    assert cache_key("m", "q", STATE, "v1") != cache_key("m", "q", STATE, "v2")


def test_key_ignores_dict_order_but_not_values() -> None:
    a = cache_key("m", "q", {"task": "t", "command": "c"}, "v")
    b = cache_key("m", "q", {"command": "c", "task": "t"}, "v")
    assert a == b


def test_errors_are_not_cached() -> None:
    inner = FakeClient(fail_models={"m"})
    cache = CachedEndor(inner, "v1")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            _call(cache)
    assert len(inner.calls) == 2
    assert len(cache) == 0


def test_entries_expire_after_ttl() -> None:
    clock = Clock()
    inner = FakeClient(lambda _m, _s, _q: 0.7)
    cache = CachedEndor(inner, "v1", ttl_s=10, clock=clock)
    _call(cache)
    clock.now = 9.9
    assert _call(cache).cache_hit is True
    clock.now = 10.0
    assert _call(cache).cache_hit is False
    assert len(inner.calls) == 2


def test_lru_evicts_oldest_when_full() -> None:
    inner = FakeClient(lambda _m, _s, _q: 0.7)
    cache = CachedEndor(inner, "v1", max_entries=2)
    _call(cache, model="a")
    _call(cache, model="b")
    _call(cache, model="a")  # touch a: b is now oldest
    _call(cache, model="c")  # evicts b
    assert len(cache) == 2
    assert _call(cache, model="a").cache_hit is True
    assert _call(cache, model="b").cache_hit is False
