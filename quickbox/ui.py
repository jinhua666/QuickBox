"""QuickBox desktop interface."""
from dataclasses import replace
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QPointF
from PySide6.QtGui import QDesktopServices, QIcon, QPainter, QPen, QColor, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget)
from .storage import Item, InvalidPassword
from .version import VERSION

TYPES = {"website": "网站", "command": "常用命令"}


def asset_path(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets" / name


def resize_hit_test(x, y, width, height, border=7):
    left, right = x < border, x >= width - border
    top, bottom = y < border, y >= height - border
    if top and left: return 13
    if top and right: return 14
    if bottom and left: return 16
    if bottom and right: return 17
    if left: return 10
    if right: return 11
    if top: return 12
    if bottom: return 15
    return None


def navigation_icon(kind):
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#8592ab"), 1.4))
    if kind == "all":
        for x, y in ((3, 3), (11, 3), (3, 11), (11, 11)):
            painter.drawRoundedRect(x, y, 5, 5, 1, 1)
    elif kind == "website":
        painter.drawEllipse(3, 3, 14, 14)
        painter.drawEllipse(7, 3, 6, 14)
        painter.drawLine(4, 10, 16, 10)
    else:
        painter.drawRoundedRect(2, 4, 16, 12, 2, 2)
        painter.drawLine(5, 7, 8, 10)
        painter.drawLine(8, 10, 5, 13)
        painter.drawLine(10, 13, 14, 13)
    painter.end()
    return QIcon(pixmap)


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(46)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 5, 0)
        mark = QLabel()
        mark.setPixmap(QIcon(str(asset_path("quickbox.ico"))).pixmap(20, 20))
        title = QLabel("QuickBox")
        title.setObjectName("titleLabel")
        layout.addWidget(mark)
        layout.addSpacing(7)
        layout.addWidget(title)
        layout.addStretch()
        for symbol, tooltip, action, name in [("minimize", "最小化", window.showMinimized, "windowButton"),
                                              ("maximize", "最大化 / 还原", self.toggle_maximize, "windowButton"),
                                              ("close", "关闭", window.close, "closeButton")]:
            button = WindowControl(symbol)
            button.setObjectName(name)
            button.setToolTip(tooltip)
            button.setFixedSize(42, 34)
            button.clicked.connect(action)
            layout.addWidget(button)

    def toggle_maximize(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.window.windowHandle():
            self.window.windowHandle().startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()
        super().mouseDoubleClickEvent(event)


class WindowControl(QPushButton):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#ffffff" if self.symbol == "close" and self.underMouse() else "#7c879b")
        pen = QPen(color, 1.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        x, y = self.width() / 2, self.height() / 2
        if self.symbol == "minimize":
            painter.drawLine(QPointF(x - 4.5, y), QPointF(x + 4.5, y))
        elif self.symbol == "maximize":
            painter.drawRect(int(x - 4), int(y - 4), 8, 8)
        else:
            painter.drawLine(QPointF(x - 3.5, y - 3.5), QPointF(x + 3.5, y + 3.5))
            painter.drawLine(QPointF(x + 3.5, y - 3.5), QPointF(x - 3.5, y + 3.5))
        painter.end()


class UnlockDialog(QDialog):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setWindowTitle("解锁 QuickBox" if store.initialized else "创建 QuickBox")
        self.setWindowIcon(QIcon(str(asset_path("quickbox.ico"))))
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(14)
        eyebrow = QLabel("QUICKBOX  /  PRIVATE SPACE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("欢迎回来" if store.initialized else "创建你的空间")
        title.setObjectName("dialogTitle")
        description = QLabel("输入主密码，解锁你的本地资料。" if store.initialized else "请设置主密码，用于加密保存的密码。\n主密码遗失后无法恢复加密数据，请妥善保管。")
        description.setObjectName("muted")
        description.setWordWrap(True)
        for widget in (eyebrow, title, description):
            layout.addWidget(widget)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("输入主密码")
        layout.addWidget(self.password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("再次输入主密码")
        if not store.initialized:
            layout.addWidget(self.confirm)
        buttons = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        submit = QPushButton("解锁" if store.initialized else "创建空间")
        submit.setObjectName("primary")
        submit.setDefault(True)
        submit.clicked.connect(self.submit)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(submit)
        layout.addLayout(buttons)

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
        self.setWindowIcon(QIcon(str(asset_path("quickbox.ico"))))
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        title = QLabel("编辑项目" if item else "添加到 QuickBox")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel("把常用信息放在一起，随时轻松找到。")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        choices = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        self.type_buttons = {}
        selected = item.kind if item else initial_kind
        for key, text in TYPES.items():
            button = QPushButton(text)
            button.setObjectName("typeButton")
            button.setCheckable(True)
            button.setChecked(selected == key)
            button.setEnabled(item is None or item.kind == key)
            self.type_group.addButton(button)
            self.type_buttons[key] = button
            choices.addWidget(button)
        choices.addStretch()
        layout.addLayout(choices)
        self.name = QLineEdit(item.name if item else "")
        self.name.setPlaceholderText("例如：常用工作平台")
        self.url = QLineEdit(item.url if item else "")
        self.url.setPlaceholderText("https://，选填")
        self.username = QLineEdit(item.username if item else "")
        self.username.setPlaceholderText("选填")
        self.login_method = QLineEdit(item.login_method if item else "")
        self.login_method.setPlaceholderText("例如：微信扫码、手机号，选填")
        self.password = QLineEdit(item.password if item else "")
        self.password.setPlaceholderText("选填")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        password_row = QWidget()
        password_layout = QHBoxLayout(password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.addWidget(self.password)
        reveal = QPushButton("显示")
        reveal.setObjectName("subtleButton")
        reveal.setCheckable(True)
        reveal.toggled.connect(lambda yes: (self.password.setEchoMode(QLineEdit.EchoMode.Normal if yes else QLineEdit.EchoMode.Password), reveal.setText("隐藏" if yes else "显示")))
        password_layout.addWidget(reveal)
        self.content = QTextEdit(item.content if item else "")
        self.content.setPlaceholderText("输入命令内容")
        self.content.setFixedHeight(90)
        self.notes = QTextEdit(item.notes if item else "")
        self.notes.setPlaceholderText("添加一点备注，选填")
        self.notes.setFixedHeight(75)
        self.fields = {}
        for key, label, widget in [("name", "名称  *", self.name), ("url", "网站地址", self.url),
                                   ("username", "用户名", self.username), ("login_method", "登录方式", self.login_method),
                                   ("password", "密码", password_row), ("content", "命令内容", self.content),
                                   ("notes", "备注", self.notes)]:
            container = QWidget()
            field_layout = QVBoxLayout(container)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(5)
            caption = QLabel(label)
            caption.setObjectName("fieldCaption")
            field_layout.addWidget(caption)
            field_layout.addWidget(widget)
            self.fields[key] = container
            layout.addWidget(container)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存项目")
        save.setObjectName("primary")
        save.clicked.connect(self.validate_and_accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addSpacing(4)
        layout.addLayout(actions)
        self.type_group.buttonClicked.connect(self.update_fields)
        self.update_fields()

    def selected_kind(self):
        return next((key for key, button in self.type_buttons.items() if button.isChecked()), "website")

    def update_fields(self, *_):
        visible = {"name", "notes"} | ({"url", "username", "login_method", "password"} if self.selected_kind() == "website" else {"content"})
        for key, container in self.fields.items():
            container.setVisible(key in visible)
        self.adjustSize()

    def item(self):
        result = replace(self.original) if self.original else Item(kind=self.selected_kind(), name="")
        result.kind = self.selected_kind()
        result.name = self.name.text().strip()
        if result.kind == "website":
            result.url = self.url.text().strip()
            result.username = self.username.text()
            result.login_method = self.login_method.text()
            result.password = self.password.text()
        else:
            result.content = self.content.toPlainText()
        result.notes = self.notes.toPlainText()
        return result

    def validate_and_accept(self):
        item = self.item()
        if not item.name or item.kind == "command" and not item.content.strip():
            QMessageBox.warning(self, "请填写必填项", "请填写名称；命令类型还需要填写命令内容。")
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.current = None
        self.copy_generation = 0
        self.copied_password = None
        self.order_mode = store.sort_mode()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh)
        self.setWindowTitle("QuickBox")
        self.setWindowIcon(QIcon(str(asset_path("quickbox.ico"))))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setMinimumSize(900, 600)
        self.resize(1200, 760)
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self))
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        outer.addLayout(columns, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(188)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(16, 26, 16, 18)
        nav.setSpacing(10)
        brand = QLabel("你的资料库")
        brand.setObjectName("sidebarHeading")
        nav.addWidget(brand)
        sub = QLabel("一切常用，都在这里")
        sub.setObjectName("muted")
        nav.addWidget(sub)
        nav.addSpacing(22)
        label = QLabel("浏览")
        label.setObjectName("navCaption")
        nav.addWidget(label)
        self.categories = QListWidget()
        self.categories.setObjectName("navigation")
        self.categories.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.categories.setIconSize(QSize(20, 20))
        for text, key in [("全部", "all"), ("网站", "website"), ("常用命令", "command")]:
            row = QListWidgetItem(text)
            row.setIcon(navigation_icon(key))
            row.setData(Qt.ItemDataRole.UserRole, key)
            self.categories.addItem(row)
        nav.addWidget(self.categories, 1)
        privacy = QLabel("●  数据保存在本机")
        privacy.setObjectName("privacyLabel")
        nav.addWidget(privacy)
        about = QPushButton("↻   检查更新")
        about.setObjectName("aboutButton")
        about.clicked.connect(self.about)
        nav.addWidget(about)
        columns.addWidget(sidebar)

        main = QFrame()
        main.setObjectName("mainArea")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(18)
        header = QHBoxLayout()
        titlebox = QVBoxLayout()
        self.page_title = QLabel("全部项目")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("你的信息，一目了然")
        self.page_subtitle.setObjectName("muted")
        titlebox.addWidget(self.page_title)
        titlebox.addWidget(self.page_subtitle)
        header.addLayout(titlebox)
        header.addStretch()
        add = QPushButton("＋  新建项目")
        add.setObjectName("primary")
        add.setMinimumHeight(42)
        add.clicked.connect(self.add_item)
        header.addWidget(add)
        main_layout.addLayout(header)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("搜索名称、网址、用户名、登录方式或备注")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        main_layout.addWidget(self.search)
        list_header = QHBoxLayout()
        self.count_label = QLabel("项目")
        self.count_label.setObjectName("sectionLabel")
        list_header.addWidget(self.count_label)
        list_header.addStretch()
        self.sort_button = QPushButton()
        self.sort_button.setObjectName("sortButton")
        self.sort_button.setToolTip("智能排序根据使用频率和近期使用情况调整顺序")
        sort_menu = QMenu(self.sort_button)
        sort_menu.addAction("智能排序", lambda: self.set_sort_mode("smart"))
        sort_menu.addAction("手动排序", lambda: self.set_sort_mode("manual"))
        self.sort_button.setMenu(sort_menu)
        list_header.addWidget(self.sort_button)
        main_layout.addLayout(list_header)
        self.sort_button.setText("智能排序" if self.order_mode == "smart" else "手动排序")

        body = QHBoxLayout()
        body.setSpacing(18)
        self.items = QListWidget()
        self.items.setObjectName("itemList")
        self.items.setMinimumWidth(310)
        self.items.currentItemChanged.connect(self.select_item)
        self.items.itemDoubleClicked.connect(self.open_item)
        self.items.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.items.customContextMenuRequested.connect(self.show_context_menu)
        body.addWidget(self.items, 1)
        detail = QFrame()
        detail.setObjectName("detailCard")
        detail.setFixedWidth(294)
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(22, 22, 22, 22)
        detail_layout.setSpacing(10)
        detail_top = QHBoxLayout()
        caption = QLabel("项目详情")
        caption.setObjectName("sectionLabel")
        detail_top.addWidget(caption)
        detail_top.addStretch()
        self.edit_button = QPushButton("编辑")
        self.edit_button.setObjectName("smallButton")
        self.edit_button.clicked.connect(self.edit_item)
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_item)
        detail_top.addWidget(self.edit_button)
        detail_top.addWidget(self.delete_button)
        detail_layout.addLayout(detail_top)
        detail_layout.addSpacing(15)
        self.detail_icon = QLabel("◇")
        self.detail_icon.setObjectName("detailIcon")
        self.detail_icon.setFixedSize(46, 46)
        self.detail_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_layout.addWidget(self.detail_icon)
        self.detail_name = QLabel("选择一个项目")
        self.detail_name.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_name.setObjectName("detailTitle")
        self.detail_name.setWordWrap(True)
        detail_layout.addWidget(self.detail_name)
        self.detail_type = QLabel("查看详细信息")
        self.detail_type.setObjectName("muted")
        detail_layout.addWidget(self.detail_type)
        line = QFrame()
        line.setObjectName("separator")
        line.setFixedHeight(1)
        detail_layout.addSpacing(10)
        detail_layout.addWidget(line)
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        detail_content = QWidget()
        detail_content.setObjectName("detailContent")
        detail_content_layout = QVBoxLayout(detail_content)
        detail_content_layout.setContentsMargins(0, 0, 0, 0)
        detail_content_layout.setSpacing(10)
        detail_scroll.setWidget(detail_content)
        self.detail_text = QLabel()
        self.detail_text.setMinimumWidth(0)
        self.detail_text.setObjectName("detailText")
        self.detail_text.setWordWrap(True)
        self.detail_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_content_layout.addWidget(self.detail_text)
        self.password_label = QLabel("密码")
        self.password_label.setObjectName("fieldCaption")
        detail_content_layout.addWidget(self.password_label)
        password_row = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setObjectName("detailPassword")
        self.password.setReadOnly(True)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password_toggle = QPushButton("显示")
        self.show_password_toggle.setObjectName("smallButton")
        self.show_password_toggle.setCheckable(True)
        self.show_password_toggle.toggled.connect(self.toggle_password)
        password_row.addWidget(self.password, 1)
        password_row.addWidget(self.show_password_toggle)
        detail_content_layout.addLayout(password_row)
        detail_content_layout.addStretch()
        detail_layout.addWidget(detail_scroll, 1)
        self.hint = QLabel("双击项目打开网址 · 右键查看更多操作")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        detail_layout.addWidget(self.hint)
        body.addWidget(detail)
        main_layout.addLayout(body, 1)
        columns.addWidget(main, 1)
        self.categories.currentRowChanged.connect(self.refresh)
        self.categories.setCurrentRow(0)
        self.show_details(None)

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32" and not self.isMaximized():
            import ctypes
            from ctypes import wintypes
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == 0x0084:  # WM_NCHITTEST
                raw = int(msg.lParam)
                rect = wintypes.RECT()
                if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(int(self.winId())), ctypes.byref(rect)):
                    return super().nativeEvent(event_type, message)
                x = ctypes.c_short(raw & 0xffff).value - rect.left
                y = ctypes.c_short((raw >> 16) & 0xffff).value - rect.top
                result = resize_hit_test(x, y, rect.right - rect.left, rect.bottom - rect.top)
                if result is not None:
                    return True, result
        return super().nativeEvent(event_type, message)

    def toggle_password(self, checked):
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.show_password_toggle.setText("隐藏" if checked else "显示")

    def refresh(self, *_):
        category = self.categories.currentItem()
        key = category.data(Qt.ItemDataRole.UserRole) if category else "all"
        self.page_title.setText({"all": "全部项目", "website": "网站", "command": "常用命令"}.get(key, "全部项目"))
        self.page_subtitle.setText({"all": "你的信息，一目了然", "website": "常用网站和登录信息，随手可得", "command": "常用命令，快速查找与复制"}.get(key, "你的信息，一目了然"))
        old_id = self.current.id if self.current else None
        results = self.store.list_items(kind=key if key in TYPES else None, query=self.search.text(), sort=self.order_mode)
        self.count_label.setText(f"项目  /  {len(results)}")
        self.items.clear()
        for item in results:
            row = QListWidgetItem()
            row.setSizeHint(QSize(0, 80))
            row.setData(Qt.ItemDataRole.UserRole, item)
            self.items.addItem(row)
            card = QWidget()
            card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout = QHBoxLayout(card)
            layout.setContentsMargins(14, 8, 14, 8)
            icon = QLabel("⌘" if item.kind == "command" else "↗")
            icon.setObjectName("rowIconCommand" if item.kind == "command" else "rowIcon")
            icon.setFixedSize(42, 42)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon)
            texts = QVBoxLayout()
            texts.setSpacing(3)
            name = QLabel(item.name)
            name.setTextFormat(Qt.TextFormat.PlainText)
            name.setMinimumWidth(0)
            name.setObjectName("rowTitle")
            secondary = (item.content.splitlines()[0] if item.content else "常用命令") if item.kind == "command" else (item.url or item.login_method or "网站 · 信息")
            subtitle = QLabel(secondary if len(secondary) <= 80 else secondary[:79] + "…")
            subtitle.setMinimumWidth(0)
            subtitle.setToolTip(secondary)
            subtitle.setObjectName("rowSubtitle")
            subtitle.setTextFormat(Qt.TextFormat.PlainText)
            texts.addWidget(name)
            texts.addWidget(subtitle)
            layout.addLayout(texts, 1)
            arrow = QLabel("›")
            arrow.setObjectName("rowArrow")
            layout.addWidget(arrow)
            self.items.setItemWidget(row, card)
            if item.id == old_id:
                self.items.setCurrentItem(row)
        if self.items.currentItem() is None:
            self.show_details(None)

    def select_item(self, current, previous):
        self.show_details(current.data(Qt.ItemDataRole.UserRole) if current else None)

    def show_details(self, item):
        self.current = item
        self.show_password_toggle.setChecked(False)
        self.detail_name.setText(item.name if item else "选择一个项目")
        self.detail_type.setText(TYPES[item.kind] if item else "查看详细信息")
        self.detail_icon.setText("⌘" if item and item.kind == "command" else "↗" if item else "◇")
        parts = []
        if item:
            for label, value in [("网站地址", item.url), ("用户名", item.username), ("登录方式", item.login_method), ("命令内容", item.content), ("备注", item.notes)]:
                if value:
                    parts.append(f"{label}\n{value}")
        self.detail_text.setText("\n\n".join(parts) if parts else ("暂无其他信息" if item else "从左侧列表选择一项\n即可在这里查看内容。"))
        self.detail_text.setTextFormat(Qt.TextFormat.PlainText)
        has_password = bool(item and item.password)
        self.password.setText(item.password if has_password else "")
        self.password.setVisible(has_password)
        self.password_label.setVisible(has_password)
        self.show_password_toggle.setVisible(has_password)
        self.edit_button.setEnabled(bool(item))
        self.delete_button.setEnabled(bool(item))

    def add_item(self):
        category = self.categories.currentItem().data(Qt.ItemDataRole.UserRole)
        dialog = ItemDialog(initial_kind=category if category in TYPES else "website", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                new = self.store.create(dialog.item())
                self.current = new
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

    def move(self, direction):
        if self.current and self.order_mode == "manual":
            visible = [self.items.item(i).data(Qt.ItemDataRole.UserRole).id for i in range(self.items.count())]
            self.store.move(self.current.id, direction, visible)
            self.refresh()

    def open_item(self, row):
        item = row.data(Qt.ItemDataRole.UserRole) if row else None
        if item and item.kind == "website" and item.url:
            if not QDesktopServices.openUrl(QUrl.fromUserInput(item.url)):
                QMessageBox.warning(self, "打开失败", "系统无法打开此地址，请检查链接或关联应用。")
            else:
                self.store.record_usage(item.id)
                self.refresh_timer.start(0)

    def set_sort_mode(self, mode):
        self.store.set_sort_mode(mode)
        self.order_mode = mode
        self.sort_button.setText("智能排序" if mode == "smart" else "手动排序")
        self.refresh()

    def show_context_menu(self, position):
        row = self.items.itemAt(position)
        if not row:
            return
        self.items.setCurrentItem(row)
        item = self.current
        menu = QMenu(self)
        if item.url:
            menu.addAction("打开网址", lambda: self.open_item(row))
            menu.addAction("复制网址", lambda: self.copy_value("url"))
        if item.username:
            menu.addAction("复制用户名", lambda: self.copy_value("username"))
        if item.password:
            menu.addAction("复制密码", lambda: self.copy_value("password"))
        if item.content:
            menu.addAction("复制命令", lambda: self.copy_value("content"))
        if self.order_mode == "manual":
            menu.addSeparator()
            menu.addAction("上移", lambda: self.move(-1))
            menu.addAction("下移", lambda: self.move(1))
        menu.exec(self.items.viewport().mapToGlobal(position))

    def copy_value(self, field):
        if not self.current:
            return
        value = getattr(self.current, field, "")
        if not value:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(value)
        if (self.current.kind == "website" and field == "url") or (self.current.kind == "command" and field == "content"):
            self.store.record_usage(self.current.id)
            self.refresh_timer.start(0)
        self.copy_generation += 1
        generation = self.copy_generation
        self.copied_password = value if field == "password" else None
        if field == "password":
            def clear_if_unchanged():
                if self.copy_generation == generation and clipboard.text() == value:
                    clipboard.clear()
                if self.copy_generation == generation:
                    self.copied_password = None
            QTimer.singleShot(30000, clear_if_unchanged)
        self.statusBar().showMessage("已复制" + ("，30 秒后自动清除" if field == "password" else ""), 3000)

    def about(self):
        from .update_dialog import UpdateDialog
        dialog = UpdateDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        self.refresh_timer.stop()
        clipboard = QApplication.clipboard()
        if self.copied_password is not None and clipboard.text() == self.copied_password:
            clipboard.clear()
        self.copied_password = None
        self.store.close()
        super().closeEvent(event)


STYLE = """
QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: #26314b; }
QMainWindow, QDialog { background: #f6f8fc; }
QFrame#titleBar { background: #ffffff; border-bottom: 1px solid #e9edf5; }
QLabel#titleLabel { font-size: 12px; font-weight: 600; color: #35425b; }
QPushButton#windowButton, QPushButton#closeButton { background: transparent; border: 0; border-radius: 5px; padding: 0; font-size: 17px; color: #7c879b; }
QPushButton#windowButton:hover { background: #edf1f8; color: #2d3950; }
QPushButton#closeButton:hover { background: #e95c65; color: white; }
QFrame#sidebar { background: #ffffff; border-right: 1px solid #e9edf4; }
QFrame#mainArea { background: #f6f8fc; }
QLabel#sidebarHeading { font-size: 16px; font-weight: 700; color: #293653; }
QLabel#pageTitle { font-size: 25px; font-weight: 700; color: #202d49; }
QLabel#dialogTitle { font-size: 23px; font-weight: 700; color: #202d49; }
QLabel#eyebrow, QLabel#navCaption, QLabel#sectionLabel { font-size: 11px; font-weight: 700; color: #8a96aa; }
QLabel#muted, QLabel#hint { color: #96a1b2; font-size: 12px; }
QLabel#privacyLabel { color: #8fa69e; font-size: 11px; padding: 5px 9px; }
QListWidget#navigation { background: transparent; border: 0; outline: 0; padding: 0; }
QListWidget#navigation::item { border-radius: 8px; min-height: 42px; padding-left: 15px; color: #77839a; margin: 2px 0; }
QListWidget#navigation::item:selected { background: #edf1ff; color: #5068d8; font-weight: 700; }
QListWidget#navigation::item:hover:!selected { background: #f5f7fb; }
QPushButton { background: white; border: 1px solid #e0e6ef; border-radius: 8px; padding: 9px 16px; color: #4a5871; }
QPushButton:hover { background: #f4f6fc; border-color: #cbd6e9; }
QPushButton#primary { background: #586fdf; border: 1px solid #586fdf; color: white; font-weight: 600; padding: 10px 19px; }
QPushButton#primary:hover { background: #4960cf; }
QPushButton#aboutButton { text-align: left; background: transparent; border: 0; color: #9ba7b8; padding: 10px; }
QPushButton#smallButton, QPushButton#dangerButton, QPushButton#subtleButton { padding: 5px 9px; font-size: 11px; background: #f6f8fc; border: 0; }
QPushButton#sortButton { background: #ffffff; border: 1px solid #e9edf5; border-radius: 7px; padding: 5px 12px; color: #73819b; font-size: 11px; }
QPushButton#sortButton::menu-indicator { subcontrol-origin: padding; subcontrol-position: right center; width: 0px; }
QPushButton#dangerButton { color: #c76a72; }
QPushButton:disabled { color: #c7cfdb; }
QPushButton#typeButton { padding: 8px 17px; background: #f1f4f9; border: 1px solid transparent; }
QPushButton#typeButton:checked { background: #edf1ff; border: 1px solid #cbd5ff; color: #5267d0; font-weight: 600; }
QLineEdit, QTextEdit { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 8px; padding: 9px 11px; selection-background-color: #667ce4; }
QLineEdit:focus, QTextEdit:focus { border: 1px solid #a7b6f4; }
QLineEdit#search { min-height: 25px; padding-left: 15px; background: #ffffff; }
QListWidget#itemList { background: transparent; border: 0; outline: 0; padding: 0; }
QListWidget#itemList::item { background: #ffffff; border: 1px solid #e9edf5; border-radius: 10px; margin-bottom: 7px; }
QListWidget#itemList::item:selected { background: #eef2ff; border: 1px solid #cbd5ff; }
QListWidget#itemList::item:hover:!selected { background: #fbfcff; border: 1px solid #d4ddec; }
QLabel#rowIcon, QLabel#detailIcon { background: #edf1ff; color: #657be1; border-radius: 11px; font-size: 20px; font-weight: 700; }
QLabel#rowIconCommand { background: #eaf7f5; color: #58a99d; border-radius: 11px; font-size: 19px; font-weight: 700; }
QLabel#rowTitle { color: #2d3951; font-size: 14px; font-weight: 600; background: transparent; }
QLabel#rowSubtitle { color: #98a4b5; font-size: 12px; background: transparent; }
QLabel#rowArrow { color: #aeb8c8; font-size: 22px; background: transparent; }
QFrame#detailCard { background: #ffffff; border: 1px solid #e9edf5; border-radius: 12px; }
QWidget#detailContent, QScrollArea { background: #ffffff; border: 0; }
QLabel#detailTitle { font-size: 18px; font-weight: 700; color: #27334d; }
QLabel#detailText { color: #65728a; line-height: 1.5; }
QLabel#fieldCaption { color: #7c899e; font-size: 12px; font-weight: 600; }
QFrame#separator { background: #eef1f6; border: 0; }
QLineEdit#detailPassword { background: #f8f9fc; }
QMenu { background: white; border: 1px solid #e1e7f0; padding: 5px; }
QMenu::item { padding: 7px 24px 7px 12px; border-radius: 5px; }
QMenu::item:selected { background: #edf1ff; }
"""
