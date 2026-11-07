import sqlite3

import pytest

from quickbox.storage import Storage, InvalidPassword, Item


def test_unlock_and_password_is_not_stored_in_plaintext(tmp_path):
    path = tmp_path / "data.db"
    store = Storage(path)
    store.initialize("master secret")
    store.create(Item(kind="account", name="Example", password="unique-password"))
    store.close()
    assert b"unique-password" not in path.read_bytes()
    store = Storage(path)
    with pytest.raises(InvalidPassword):
        store.unlock("wrong")
    store.unlock("master secret")
    assert store.list_items()[0].password == "unique-password"
    store.close()


def test_crud_search_favorites_and_sort(tmp_path):
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    first = store.create(Item(kind="website", name="Alpha", url="https://example.com"))
    second = store.create(Item(kind="command", name="Beta", content="git status", favorite=True))
    assert [i.name for i in store.list_items(query="status")] == ["Beta"]
    assert [i.name for i in store.list_items(favorites=True)] == ["Beta"]
    store.move(second.id, -1)
    assert [i.name for i in store.list_items()] == ["Beta", "Alpha"]
    first.name = "Changed"
    store.update(first)
    assert store.list_items(kind="website")[0].name == "Changed"
    store.delete(first.id)
    assert len(store.list_items()) == 1
    store.close()


def test_rejects_future_schema_version(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(RuntimeError, match="版本"):
        Storage(path)
