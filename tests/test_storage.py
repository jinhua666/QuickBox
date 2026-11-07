import sqlite3

import pytest

from quickbox.storage import Storage, InvalidPassword, Item


def test_upgrade_old_items_preserves_encrypted_password_and_backs_up(tmp_path):
    from quickbox.storage import _key, _encrypt
    path = tmp_path / "data.db"
    salt = b"0123456789abcdef"
    key = _key("master", salt)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
        db.executemany("INSERT INTO settings VALUES (?, ?)", [("salt", salt), ("verifier", _encrypt(key, "QuickBox verification v1"))])
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '', password BLOB, content TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', favorite INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL)")
        db.executemany("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)", [
            (1, "account", "账号", "", "user", _encrypt(key, "secret"), "", "memo", 1, 0),
            (2, "document", "文档", "https://example.com", "", None, "", "notes", 0, 1),
            (3, "command", "命令", "", "", None, "echo hi", "", 0, 2)])
        db.execute("PRAGMA user_version=1")
    store = Storage(path)
    store.unlock("master")
    items = store.list_items()
    assert [(i.kind, i.name) for i in items] == [("website", "账号"), ("website", "文档"), ("command", "命令")]
    assert items[0].password == "secret" and items[0].username == "user" and items[0].notes == "memo"
    assert items[1].url == "https://example.com" and items[1].notes == "notes"
    backups = list(tmp_path.glob("data.db.backup-*"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
        assert backup.execute("SELECT kind FROM items WHERE id=1").fetchone()[0] == "account"
    store.close()


def test_website_only_requires_name_and_login_method_is_searchable(tmp_path):
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="website", name="无链接"))
    store.create(Item(kind="website", name="服务", login_method="微信扫码"))
    assert store.list_items(query="微信扫码")[0].login_method == "微信扫码"
    store.close()


def test_failed_migration_rolls_back_and_keeps_backup(tmp_path):
    path = tmp_path / "broken.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        db.execute("PRAGMA user_version=1")
    with pytest.raises(sqlite3.OperationalError):
        Storage(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert [row[1] for row in db.execute("PRAGMA table_info(items)")] == ["id"]
    assert len(list(tmp_path.glob("broken.db.backup-*"))) == 1


def test_usage_scores_decay_and_do_not_store_history(tmp_path):
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    first = store.create(Item(kind="website", name="First"))
    second = store.create(Item(kind="website", name="Second"))
    day = 86400
    store.record_usage(first.id, now=100000)
    store.record_usage(first.id, now=100001)
    store.record_usage(second.id, now=100000 + 42 * day)
    assert [i.id for i in store.list_items(sort="smart", now=100000 + 42 * day)] == [second.id, first.id]
    assert [i.id for i in store.list_items(sort="manual")] == [first.id, second.id]
    assert store.db.execute("SELECT count(*) FROM items").fetchone()[0] == 2
    store.close()


def test_v2_upgrade_keeps_order_and_creates_backup(tmp_path):
    path = tmp_path / "data.db"
    store = Storage(path)
    store.initialize("secret")
    store.create(Item(kind="website", name="Site", password="secret-password"))
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=2")
        db.execute("ALTER TABLE items DROP COLUMN usage_score")
        db.execute("ALTER TABLE items DROP COLUMN usage_updated")
    store = Storage(path)
    store.unlock("secret")
    assert store.list_items()[0].password == "secret-password"
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == 3
    assert len(list(tmp_path.glob("data.db.backup-*"))) == 1
    store.close()


def test_unlock_and_password_is_not_stored_in_plaintext(tmp_path):
    path = tmp_path / "data.db"
    store = Storage(path)
    store.initialize("master secret")
    store.create(Item(kind="website", name="Example", password="unique-password"))
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
