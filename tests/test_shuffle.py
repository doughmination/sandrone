import pytest
from sandrone import mood


@pytest.fixture(autouse=True)
def store(tmp_path):
    mood.bagDb.path = tmp_path / "shuffle.jp"
    mood.bagDb.reload()
    return mood.bagDb


items = ["a", "b", "c", "d"]


def test_every_item_comes_out_once_before_any_repeat() -> None:
    bag = mood.ShuffleBag("test", items)
    assert sorted(bag.draw(1) for _ in items) == items


def test_each_guild_has_its_own_bag() -> None:
    bag = mood.ShuffleBag("test", items)
    first = [bag.draw(1) for _ in range(2)]
    # Guild 2 drawing in between must not eat into guild 1's bag.
    other = [bag.draw(2) for _ in items]
    rest = [bag.draw(1) for _ in range(2)]
    assert sorted(first + rest) == items
    assert sorted(other) == items


def test_no_repeat_straight_across_a_refill() -> None:
    bag = mood.ShuffleBag("test", items)
    previous = None
    for _ in range(200):
        drawn = bag.draw(1)
        assert drawn != previous
        previous = drawn


def test_the_bag_survives_a_reload(store) -> None:
    bag = mood.ShuffleBag("test", items)
    first = [bag.draw(1) for _ in range(2)]
    store.save()
    store.reload()
    rest = [bag.draw(1) for _ in range(2)]
    assert sorted(first + rest) == items


def test_lines_edited_out_are_dropped_from_the_bag() -> None:
    mood.ShuffleBag("test", items).draw(1)
    bag = mood.ShuffleBag("test", ["a", "z"])
    assert {bag.draw(1) for _ in range(2)} == {"a", "z"}


def test_dms_share_one_bag() -> None:
    bag = mood.ShuffleBag("test", items)
    assert sorted(bag.draw(None) for _ in items) == items
