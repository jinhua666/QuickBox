"""QuickBox desktop interface."""
from dataclasses import replace
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget)
from .storage import Item, InvalidPassword
from .version import VERSION

TYPES = {"website": "网站", "account": "账号密码", "command": "常用命令", "document": "文档链接"}


class UnlockDialog(QDialog):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setWindowTitle("解锁 QuickBox" if store.initialized else "创建 QuickBox")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        title = QLabel("欢迎使用 QuickBox")
        title.setObjectName("heading")
        layout.addWidget(title)
        description = QLabel("输入主密码解锁本地数据。" if store.initialized else "请设置主密码，用于加密保存的密码。\n主密码遗失后无法恢复加密数据，请妥善保管。")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("主密码")
        layout.addWidget(self.password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("再次输入主密码")
        if not store.initialized:
            layout.addWidget(self.confirm)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("解锁" if store.initialized else "创建")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def submit(self):
        value = self.password.text()
        if not value:
            QMessageBox.warning(self, "提示", "请输入主密码。")
            return
        if not self.store.initialized and value != self.confirm.text():
            QMessageBox.warning(self, "提示", "两次输入的主密码不一致。")
            return
        try:
            if self.store.initialized:
                self.store.unlock(value)
            else:
                self.store.initialize(value)
        except InvalidPassword:
            QMessageBox.warning(self, "无法解锁", "主密码错误或验证数据损坏。")
            return
        except Exception as exc:
            QMessageBox.critical(self, "无法打开数据", str(exc))
            return
        self.password.clear()
        self.confirm.clear()
        self.accept()


class ItemDialog(QDialog):
    def __init__(self, item=None, initial_kind="website", parent=None):
        super().__init__(parent)
        self.original = item
        self.setWindowTitle("编辑项目" if item else "新增项目")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        for key, label in TYPES.items():
            self.kind.addItem(label, key)
        self.kind.setCurrentIndex(self.kind.findData(item.kind if item else initial_kind))
        self.kind.setEnabled(item is None)
        self.name = QLineEdit(item.name if item else "")
        self.url = QLineEdit(item.url if item else "")
        self.username = QLineEdit(item.username if item else "")
        self.password = QLineEdit(item.password if item else "")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password = QCheckBox("显示密码")
        self.show_password.toggled.connect(lambda yes: self.password.setEchoMode(QLineEdit.EchoMode.Normal if yes else QLineEdit.EchoMode.Password))
        password_box = QWidget()
        password_layout = QHBoxLayout(password_box)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.addWidget(self.password)
        password_layout.addWidget(self.show_password)
        self.content = QTextEdit(item.content if item else "")
        self.content.setMaximumHeight(100)
        self.notes = QTextEdit(item.notes if item else "")
        self.notes.setMaximumHeight(85)
        self.favorite = QCheckBox("收藏此项目")
        self.favorite.setChecked(item.favorite if item else False)
        form.addRow("类型", self.kind)
        form.addRow("名称", self.name)
        self.fields = {}
        for key, label, widget in [("url", "地址", self.url), ("username", "用户名", self.username), ("password", "密码", password_box), ("content", "命令内容", self.content), ("notes", "备注", self.notes)]:
            form.addRow(label, widget)
            self.fields[key] = (form.labelForField(widget), widget)
        form.addRow("", self.favorite)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(self.update_fields)
        self.update_fields()

    def update_fields(self):
        visible = {"website": {"url"}, "account": {"url", "username", "password"}, "command": {"content", "notes"}, "document": {"url", "notes"}}[self.kind.currentData()]
        for key, (label, field) in self.fields.items():
            label.setVisible(key in visible)
            field.setVisible(key in visible)

    def item(self):
        result = replace(self.original) if self.original else Item(kind=self.kind.currentData(), name="")
        result.kind = self.kind.currentData()
        result.name = self.name.text().strip()
        result.url = self.url.text().strip()
        result.username = self.username.text()
        result.password = self.password.text()
        result.content = self.content.toPlainText()
        result.notes = self.notes.toPlainText()
        result.favorite = self.favorite.isChecked()
        return result

    def validate_and_accept(self):
        item = self.item()
        if not item.name or item.kind in {"website", "document"} and not item.url or item.kind == "account" and not item.password or item.kind == "command" and not item.content.strip():
            QMessageBox.warning(self, "请填写必填项", "请填写名称以及该类型需要的地址、密码或命令。")
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.current = None
        self.copy_generation = 0
        self.copied_password = None
        self.setWindowTitle("QuickBox")
        self.resize(1020, 680)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        nav = QVBoxLayout()
        logo = QLabel("QuickBox")
        logo.setObjectName("logo")
        nav.addWidget(logo)
        self.categories = QListWidget()
        for label, key in [("全部", "all"), *[(v, k) for k, v in TYPES.items()], ("我的收藏", "favorites")]:
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, key)
            self.categories.addItem(row)
        self.categories.setFixedWidth(155)
        nav.addWidget(self.categories)
        about = QPushButton("关于")
        about.clicked.connect(self.about)
        nav.addWidget(about)
        outer.addLayout(nav)
        content = QVBoxLayout()
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索名称、地址、用户名、命令或备注")
        self.search.textChanged.connect(self.refresh)
        add = QPushButton("＋ 新增")
        add.setObjectName("primary")
        add.clicked.connect(self.add_item)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(add)
        content.addLayout(toolbar)
        body = QHBoxLayout()
        self.items = QListWidget()
        self.items.setMinimumWidth(280)
        self.items.currentItemChanged.connect(self.select_item)
        body.addWidget(self.items, 1)
        detail = QVBoxLayout()
        self.detail_name = QLabel("选择一个项目查看详情")
        self.detail_name.setObjectName("heading")
        self.detail_name.setWordWrap(True)
        detail.addWidget(self.detail_name)
        self.detail_type = QLabel("")
        detail.addWidget(self.detail_type)
        self.detail_text = QLabel("")
        self.detail_text.setWordWrap(True)
        self.detail_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail.addWidget(self.detail_text)
        pass_row = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setReadOnly(True)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password_toggle = QCheckBox("显示")
        self.show_password_toggle.toggled.connect(lambda yes: self.password.setEchoMode(QLineEdit.EchoMode.Normal if yes else QLineEdit.EchoMode.Password))
        pass_row.addWidget(self.password)
        pass_row.addWidget(self.show_password_toggle)
        detail.addLayout(pass_row)
        self.open_button = QPushButton("打开链接")
        self.copy_button = QPushButton("复制")
        self.favorite_button = QPushButton("收藏")
        self.edit_button = QPushButton("编辑")
        self.delete_button = QPushButton("删除")
        self.up_button = QPushButton("上移")
        self.down_button = QPushButton("下移")
        for row in [(self.open_button, self.copy_button), (self.favorite_button, self.edit_button, self.delete_button), (self.up_button, self.down_button)]:
            buttons = QHBoxLayout()
            for button in row:
                buttons.addWidget(button)
            detail.addLayout(buttons)
        detail.addStretch()
        body.addLayout(detail, 2)
        content.addLayout(body, 1)
        outer.addLayout(content, 1)
        self.open_button.clicked.connect(self.open_link)
        self.copy_button.clicked.connect(self.copy_value)
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.edit_button.clicked.connect(self.edit_item)
        self.delete_button.clicked.connect(self.delete_item)
        self.up_button.clicked.connect(lambda: self.move(-1))
        self.down_button.clicked.connect(lambda: self.move(1))
        self.categories.currentRowChanged.connect(self.refresh)
        self.categories.setCurrentRow(0)
        self.show_details(None)

    def refresh(self, *_):
        category = self.categories.currentItem()
        key = category.data(Qt.ItemDataRole.UserRole) if category else "all"
        old_id = self.current.id if self.current else None
        self.items.clear()
        for item in self.store.list_items(kind=key if key in TYPES else None, query=self.search.text(), favorites=key == "favorites"):
            row = QListWidgetItem(("★  " if item.favorite else "") + item.name + "\n" + TYPES[item.kind])
            row.setData(Qt.ItemDataRole.UserRole, item)
            self.items.addItem(row)
            if item.id == old_id:
                self.items.setCurrentItem(row)
        if self.items.currentItem() is None:
            self.show_details(None)

    def select_item(self, current, previous):
        self.show_details(current.data(Qt.ItemDataRole.UserRole) if current else None)

    def show_details(self, item):
        self.current = item
        self.show_password_toggle.setChecked(False)
        self.detail_name.setText(item.name if item else "选择一个项目查看详情")
        self.detail_type.setText(TYPES[item.kind] if item else "")
        parts = []
        if item:
            for label, value in [("地址", item.url), ("用户名", item.username), ("命令", item.content), ("备注", item.notes)]:
                if value:
                    parts.append(f"{label}：{value}")
        self.detail_text.setText("\n\n".join(parts))
        self.password.setText(item.password if item and item.kind == "account" else "")
        self.password.setVisible(bool(item and item.kind == "account"))
        self.show_password_toggle.setVisible(bool(item and item.kind == "account"))
        self.open_button.setEnabled(bool(item and item.url))
        self.copy_button.setEnabled(bool(item))
        self.favorite_button.setText("取消收藏" if item and item.favorite else "收藏")
        for button in (self.favorite_button, self.edit_button, self.delete_button, self.up_button, self.down_button):
            button.setEnabled(bool(item))

    def add_item(self):
        category = self.categories.currentItem().data(Qt.ItemDataRole.UserRole)
        dialog = ItemDialog(initial_kind=category if category in TYPES else "website", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.create(dialog.item())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "保存失败", str(exc))

    def edit_item(self):
        if not self.current:
            return
        dialog = ItemDialog(self.current, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.update(dialog.item())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "保存失败", str(exc))

    def delete_item(self):
        if self.current and QMessageBox.question(self, "确认删除", f"确定删除“{self.current.name}”吗？此操作无法撤销。") == QMessageBox.StandardButton.Yes:
            self.store.delete(self.current.id)
            self.refresh()

    def toggle_favorite(self):
        if self.current:
            self.current.favorite = not self.current.favorite
            self.store.update(self.current)
            self.refresh()

    def move(self, direction):
        if self.current:
            visible = [self.items.item(i).data(Qt.ItemDataRole.UserRole).id for i in range(self.items.count())]
            self.store.move(self.current.id, direction, visible)
            self.refresh()

    def open_link(self):
        if self.current and self.current.url:
            url = QUrl.fromUserInput(self.current.url)
            if not QDesktopServices.openUrl(url):
                QMessageBox.warning(self, "打开失败", "系统无法打开此地址，请检查链接或关联应用。")

    def copy_value(self):
        if not self.current:
            return
        item = self.current
        value = item.password if item.kind == "account" else item.content if item.kind == "command" else item.url
        clipboard = QApplication.clipboard()
        clipboard.setText(value)
        self.copy_generation += 1
        generation = self.copy_generation
        self.copied_password = value if item.kind == "account" else None
        if item.kind == "account":
            def clear_if_unchanged():
                if self.copy_generation == generation and clipboard.text() == value:
                    clipboard.clear()
                if self.copy_generation == generation:
                    self.copied_password = None
            QTimer.singleShot(30000, clear_if_unchanged)
        self.statusBar().showMessage("已复制" + ("，30 秒后自动清除" if item.kind == "account" else ""), 3000)

    def about(self):
        QMessageBox.information(self, "关于 QuickBox", f"QuickBox {VERSION}\n本地个人信息管理工具\n\n更新检查将在配置私有仓库安全认证后提供。")

    def closeEvent(self, event):
        clipboard = QApplication.clipboard()
        if self.copied_password is not None and clipboard.text() == self.copied_password:
            clipboard.clear()
        self.copied_password = None
        self.store.close()
        super().closeEvent(event)


STYLE = """
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #243047; }
QMainWindow, QDialog { background: #f5f7fb; }
QLabel#logo { font-size: 25px; font-weight: bold; color: #365cd1; padding: 8px; }
QLabel#heading { font-size: 20px; font-weight: bold; padding: 8px 0; }
QLineEdit, QTextEdit, QComboBox, QListWidget { background: white; border: 1px solid #dce3ef; border-radius: 7px; padding: 8px; }
QListWidget::item { padding: 12px 8px; border-radius: 5px; }
QListWidget::item:selected { background: #e4ebff; color: #2347b0; }
QPushButton { background: white; border: 1px solid #d6deeb; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background: #eef2ff; }
QPushButton#primary { background: #4268dc; color: white; border: none; }
QPushButton:disabled { color: #a6afbf; }
"""
