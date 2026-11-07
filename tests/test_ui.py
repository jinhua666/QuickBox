import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from quickbox.storage import Item, Storage
from quickbox.ui import MainWindow, ItemDialog, resize_hit_test


def test_border_hit_test_keeps_window_resizable():
    assert resize_hit_test(1, 1, 1000, 700) == 13
    assert resize_hit_test(999, 350, 1000, 700) == 11
    assert resize_hit_test(500, 699, 1000, 700) == 15
    assert resize_hit_test(500, 300, 1000, 700) is None


def test_title_bar_minimize_and_restore(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    window = MainWindow(store)
    window.show()
    buttons = window.findChildren(QPushButton, "windowButton")
    buttons[0].click()
    assert window.isMinimized()
    window.showNormal()
    buttons[1].click()
    assert window.isMaximized()
    buttons[1].click()
    assert not window.isMaximized()
    window.close()


def test_window_filters_and_shows_selected_details(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="website", name="账号", password="secret-value", login_method="微信扫码"))
    window = MainWindow(store)
    window.show()
    assert window.isVisible()
    window.search.setText("账号")
    assert window.items.count() == 1
    window.items.setCurrentRow(0)
    assert "账号" in window.detail_name.text()
    assert "微信扫码" in window.detail_text.text()
    assert window.password.echoMode() != window.password.EchoMode.Normal
    assert [window.categories.item(i).text().strip() for i in range(window.categories.count())] == ["全部", "网站", "常用命令"]
    window.close()


def test_account_dialog_accepts_password_without_url():
    app = QApplication.instance() or QApplication([])
    dialog = ItemDialog(Item(kind="website", name="账号", password="secret"))
    item = dialog.item()
    assert item.url == ""
    assert item.password == "secret"


def test_website_dialog_accepts_name_only_and_stores_login_method():
    app = QApplication.instance() or QApplication([])
    dialog = ItemDialog()
    dialog.name.setText("资料")
    dialog.login_method.setText("微信扫码")
    dialog.validate_and_accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.item().url == "" and dialog.item().login_method == "微信扫码"


def test_password_clipboard_does_not_clear_new_content(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="website", name="账号", password="password-one"))
    window = MainWindow(store)
    window.items.setCurrentRow(0)
    callbacks = []
    monkeypatch.setattr("quickbox.ui.QTimer.singleShot", lambda delay, callback: callbacks.append(callback))
    window.copy_value("password")
    assert app.clipboard().text() == "password-one"
    app.clipboard().setText("something else")
    callbacks[0]()
    assert app.clipboard().text() == "something else"
    window.close()


def test_close_clears_unchanged_password(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="website", name="账号", password="password-one"))
    window = MainWindow(store)
    window.items.setCurrentRow(0)
    monkeypatch.setattr("quickbox.ui.QTimer.singleShot", lambda delay, callback: None)
    window.copy_value("password")
    window.close()


def test_double_click_opens_only_items_with_url(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Storage(tmp_path / "data.db")
    store.initialize("secret")
    store.create(Item(kind="website", name="No URL"))
    store.create(Item(kind="website", name="With URL", url="https://example.com"))
    window = MainWindow(store)
    window.show()
    app.processEvents()
    opened = []
    monkeypatch.setattr("quickbox.ui.QDesktopServices.openUrl", lambda url: opened.append(url.toString()) or True)
    first = window.items.visualItemRect(window.items.item(0)).center()
    QTest.mouseClick(window.items.viewport(), Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseDClick(window.items.viewport(), Qt.MouseButton.LeftButton, pos=first)
    assert not opened
    second = window.items.visualItemRect(window.items.item(1)).center()
    QTest.mouseClick(window.items.viewport(), Qt.MouseButton.LeftButton, pos=second)
    QTest.mouseDClick(window.items.viewport(), Qt.MouseButton.LeftButton, pos=second)
    assert opened == ["https://example.com"]
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
