import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from quickbox.storage import Item, Storage
from quickbox.ui import MainWindow, ItemDialog


def test_window_filters_and_shows_selected_details(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="account", name="账号", password="secret-value"))
    window = MainWindow(store)
    window.show()
    assert window.isVisible()
    window.search.setText("账号")
    assert window.items.count() == 1
    window.items.setCurrentRow(0)
    assert "账号" in window.detail_name.text()
    assert window.password.echoMode() != window.password.EchoMode.Normal
    window.close()


def test_account_dialog_accepts_password_without_url():
    app = QApplication.instance() or QApplication([])
    dialog = ItemDialog(Item(kind="account", name="账号", password="secret"))
    item = dialog.item()
    assert item.url == ""
    assert item.password == "secret"


def test_password_clipboard_does_not_clear_new_content(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="account", name="账号", password="password-one"))
    window = MainWindow(store)
    window.items.setCurrentRow(0)
    callbacks = []
    monkeypatch.setattr("quickbox.ui.QTimer.singleShot", lambda delay, callback: callbacks.append(callback))
    window.copy_value()
    assert app.clipboard().text() == "password-one"
    app.clipboard().setText("something else")
    callbacks[0]()
    assert app.clipboard().text() == "something else"
    window.close()


def test_close_clears_unchanged_password(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="account", name="账号", password="password-one"))
    window = MainWindow(store)
    window.items.setCurrentRow(0)
    monkeypatch.setattr("quickbox.ui.QTimer.singleShot", lambda delay, callback: None)
    window.copy_value()
    window.close()
    assert app.clipboard().text() == ""


def test_sorting_in_a_category_moves_visible_items(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="website", name="First", url="https://first.example"))
    store.create(Item(kind="command", name="Other", content="echo hi"))
    store.create(Item(kind="website", name="Second", url="https://second.example"))
    window = MainWindow(store)
    window.categories.setCurrentRow(1)
    window.items.setCurrentRow(1)
    window.move(-1)
    assert [store.list_items(kind="website")[i].name for i in range(2)] == ["Second", "First"]
    window.close()
