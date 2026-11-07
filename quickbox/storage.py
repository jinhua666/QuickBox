"""Local SQLite persistence and authenticated encryption of passwords."""
from dataclasses import dataclass
from pathlib import Path
import os
import sqlite3
import time
from datetime import datetime

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SCHEMA_VERSION = 3
HALF_LIFE_SECONDS = 14 * 86400
KINDS = {"website", "command"}


class InvalidPassword(Exception):
    pass


@dataclass
class Item:
    kind: str
    name: str
    url: str = ""
    username: str = ""
    login_method: str = ""
    password: str = ""
    content: str = ""
    notes: str = ""
    favorite: bool = False
    id: int | None = None
    position: int = 0


def default_path() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        raise RuntimeError("无法确定 LOCALAPPDATA 数据目录")
    return Path(root) / "QuickBox" / "data.db"


def _key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def _encrypt(key: bytes, value: str) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, value.encode("utf-8"), None)


def _decrypt(key: bytes, value: bytes) -> str:
    return AESGCM(key).decrypt(value[:12], value[12:], None).decode("utf-8")


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.key = None
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            self.db.close()
            raise RuntimeError("数据库版本高于此软件支持的版本")
        if version == 0:
            tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if tables:
                self.db.close()
                raise RuntimeError("无法识别数据库结构，未进行修改")
            with self.db:
                self.db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
                self.db.execute("""CREATE TABLE items (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '',
                    password BLOB, content TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', login_method TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL,
                    usage_score REAL NOT NULL DEFAULT 0, usage_updated REAL NOT NULL DEFAULT 0)""")
                self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        elif version < SCHEMA_VERSION:
            try:
                self._backup_before_migration()
                if version not in (1, 2):
                    raise RuntimeError("此数据库版本尚无可用的迁移程序")
                with self.db:
                    self.db.execute("BEGIN IMMEDIATE")
                    if version == 1:
                        self.db.execute("ALTER TABLE items ADD COLUMN login_method TEXT NOT NULL DEFAULT ''")
                        self.db.execute("UPDATE items SET kind='website' WHERE kind IN ('account','document')")
                    self.db.execute("ALTER TABLE items ADD COLUMN usage_score REAL NOT NULL DEFAULT 0")
                    self.db.execute("ALTER TABLE items ADD COLUMN usage_updated REAL NOT NULL DEFAULT 0")
                    self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            except Exception:
                self.db.close()
                raise

    def _backup_before_migration(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self.path.with_name(f"{self.path.name}.backup-{stamp}")
        with sqlite3.connect(backup_path) as backup:
            self.db.backup(backup)

    @property
    def initialized(self):
        return self.db.execute("SELECT 1 FROM settings WHERE key='salt'").fetchone() is not None

    def initialize(self, password: str):
        if self.initialized:
            raise RuntimeError("数据库已初始化")
        if not password:
            raise ValueError("主密码不能为空")
        salt = os.urandom(16)
        key = _key(password, salt)
        with self.db:
            self.db.executemany("INSERT INTO settings (key,value) VALUES (?,?)", [
                ("salt", salt), ("verifier", _encrypt(key, "QuickBox verification v1"))])
        self.key = key

    def unlock(self, password: str):
        self.key = None
        values = dict(self.db.execute("SELECT key,value FROM settings").fetchall())
        if "salt" not in values or "verifier" not in values:
            raise RuntimeError("数据库尚未初始化或验证信息损坏")
        key = _key(password, values["salt"])
        try:
            if _decrypt(key, values["verifier"]) != "QuickBox verification v1":
                raise InvalidPassword()
        except (InvalidTag, ValueError, UnicodeError) as exc:
            raise InvalidPassword() from exc
        self.key = key

    def _require_key(self):
        if self.key is None:
            raise RuntimeError("请先解锁数据库")
        return self.key

    def _validate(self, item):
        if item.kind not in KINDS or not item.name.strip():
            raise ValueError("请选择有效类型并填写名称")
        if item.kind == "command" and not item.content.strip():
            raise ValueError("请填写命令")

    def create(self, item: Item) -> Item:
        key = self._require_key()
        self._validate(item)
        with self.db:
            pos = self.db.execute("SELECT COALESCE(MAX(position), -1)+1 FROM items").fetchone()[0]
            cur = self.db.execute("INSERT INTO items(kind,name,url,username,password,content,notes,favorite,position,login_method) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (item.kind, item.name.strip(), item.url, item.username, _encrypt(key, item.password) if item.password else None, item.content, item.notes, int(item.favorite), pos, item.login_method))
        item.id, item.position = cur.lastrowid, pos
        return item

    def update(self, item: Item):
        key = self._require_key()
        self._validate(item)
        with self.db:
            cur = self.db.execute("UPDATE items SET kind=?, name=?, url=?, username=?, password=?, content=?, notes=?, favorite=?, login_method=? WHERE id=?",
                (item.kind, item.name.strip(), item.url, item.username, _encrypt(key, item.password) if item.password else None, item.content, item.notes, int(item.favorite), item.login_method, item.id))
            if cur.rowcount != 1:
                raise ValueError("条目不存在")

    def delete(self, item_id: int):
        self._require_key()
        with self.db:
            self.db.execute("DELETE FROM items WHERE id=?", (item_id,))

    def list_items(self, kind=None, query="", favorites=False, now=None):
        key = self._require_key()
        rows = self.db.execute("SELECT * FROM items ORDER BY position,id").fetchall()
        timestamp = time.time() if now is None else now
        rows = sorted(rows, key=lambda row: (-row["usage_score"] * 2 ** (-max(0, timestamp - row["usage_updated"]) / HALF_LIFE_SECONDS), row["position"], row["id"]))
        result = []
        for row in rows:
            item = Item(id=row["id"], kind=row["kind"], name=row["name"], url=row["url"], username=row["username"], login_method=row["login_method"],
                        password=_decrypt(key, row["password"]) if row["password"] else "", content=row["content"],
                        notes=row["notes"], favorite=bool(row["favorite"]), position=row["position"])
            if kind and item.kind != kind or favorites and not item.favorite:
                continue
            if query.casefold() not in " ".join((item.name, item.url, item.username, item.login_method, item.content, item.notes)).casefold():
                continue
            result.append(item)
        return result

    def record_usage(self, item_id, now=None):
        self._require_key()
        timestamp = time.time() if now is None else now
        with self.db:
            row = self.db.execute("SELECT usage_score, usage_updated FROM items WHERE id=?", (item_id,)).fetchone()
            if row is None:
                raise ValueError("条目不存在")
            elapsed = max(0, timestamp - row["usage_updated"])
            score = row["usage_score"] * 2 ** (-elapsed / HALF_LIFE_SECONDS) + 1
            self.db.execute("UPDATE items SET usage_score=?, usage_updated=? WHERE id=?", (score, max(timestamp, row["usage_updated"]), item_id))

    def close(self):
        self.key = None
        self.db.close()
