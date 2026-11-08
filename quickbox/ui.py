"""QuickBox desktop interface."""
from dataclasses import replace
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QPointF
from PySide6.QtGui import QDesktopServices, QIcon, QPainter, QPen, QColor, QPixmap, QKeySequence, QFontDatabase
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QTextEdit, QPlainTextEdit, QVBoxLayout, QWidget)
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
    painter.setPen(QPen(QColor("#a6b6ce"), 1.4))
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


def search_icon():
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#97a3b5"), 1.6))
    painter.drawEllipse(3, 3, 10, 10)
    painter.drawLine(12, 12, 17, 17)
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


class CopyPasswordField(QLineEdit):
    def __init__(self, on_click):
        super().__init__()
        self.on_click = on_click

    def click(self):
        self.on_click()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.click()
        super().mousePressEvent(event)


class CommandView(QPlainTextEdit):
    def __init__(self, on_copy):
        super().__init__()
        self.on_copy = on_copy
        self.setReadOnly(True)
        self.setObjectName("commandView")
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMinimumHeight(360)

    def copy(self):
        if self.textCursor().hasSelection():
            super().copy()
            self.on_copy()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            event.accept()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy = menu.addAction("复制选中内容")
        copy.setEnabled(self.textCursor().hasSelection())
        copy.triggered.connect(self.copy)
        menu.addAction("全选", self.selectAll)
        menu.exec(event.globalPos())


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
        if store.initialized:
            self.unlock_timer = QTimer(self)
            self.unlock_timer.setSingleShot(True)
            self.unlock_timer.setInterval(600)
            self.unlock_timer.timeout.connect(self.try_unlock)
            self.password.textChanged.connect(lambda text: self.unlock_timer.start() if text else self.unlock_timer.stop())
            self.password.returnPressed.connect(self.try_unlock)
        else:
            buttons = QHBoxLayout()
            cancel = QPushButton("取消")
            cancel.clicked.connect(self.reject)
            submit = QPushButton("创建空间")
            submit.setObjectName("primary")
            submit.setDefault(True)
            submit.clicked.connect(self.submit)
            buttons.addStretch()
            buttons.addWidget(cancel)
            buttons.addWidget(submit)
            layout.addLayout(buttons)

    def try_unlock(self):
        value = self.password.text()
        if not value:
            return
        try:
            self.store.unlock(value)
        except InvalidPassword:
            return
        except Exception as exc:
            self.unlock_timer.stop()
            QMessageBox.critical(self, "无法打开数据", str(exc))
            return
        self.unlock_timer.stop()
        self.password.clear()
        self.accept()

    def reject(self):
        if hasattr(self, "unlock_timer"):
            self.unlock_timer.stop()
        self.password.clear()
        self.confirm.clear()
        super().reject()

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
        self.setMinimumWidth(650)
        screen = parent.screen() if parent else QApplication.primaryScreen()
        if screen:
            self.setMaximumHeight(int(screen.availableGeometry().height() * 0.9))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 26)
        layout.setSpacing(12)
        eyebrow = QLabel("QUICKBOX   /   YOUR SPACE")
        eyebrow.setObjectName("dialogEyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("编辑项目" if item else "添加新项目")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel("为常用信息找个安心的位置。")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        layout.addSpacing(5)
        type_caption = QLabel("选择类型")
        type_caption.setObjectName("fieldCaption")
        layout.addWidget(type_caption)
        choices = QHBoxLayout()
        choices.setSpacing(10)
        self.type_group = QButtonGroup(self)
        self.type_buttons = {}
        selected = item.kind if item else initial_kind
        for key, text in TYPES.items():
            button = QPushButton(("↗   网站 / 账号" if key == "website" else "⌘   常用命令"))
            button.setObjectName("typeButton")
            button.setCheckable(True)
            button.setChecked(selected == key)
            button.setEnabled(item is None or item.kind == key)
            self.type_group.addButton(button)
            self.type_buttons[key] = button
            choices.addWidget(button, 1)
        layout.addLayout(choices)
        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 17, 20, 18)
        form_layout.setSpacing(12)
        form_head = QHBoxLayout()
        form_title = QLabel("项目信息")
        form_title.setObjectName("formTitle")
        self.form_hint = QLabel()
        self.form_hint.setObjectName("formHint")
        form_head.addWidget(form_title)
        form_head.addStretch()
        form_head.addWidget(self.form_hint)
        form_layout.addLayout(form_head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.addLayout(grid)
        form_layout.addStretch()
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
        self.content = QPlainTextEdit(item.content if item else "")
        self.content.setObjectName("commandEditor")
        self.content.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.content.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.content.setPlaceholderText("输入命令内容")
        self.content.setMinimumHeight(190)
        self.notes = QTextEdit(item.notes if item else "")
        self.notes.setPlaceholderText("添加一点备注，选填")
        self.notes.setFixedHeight(64)
        self.fields = {}
        for key, label, widget, row, column, span in [
            ("name", "名称  *", self.name, 0, 0, 2), ("url", "网站地址", self.url, 1, 0, 2),
            ("username", "用户名", self.username, 2, 0, 1), ("login_method", "登录方式", self.login_method, 2, 1, 1),
            ("password", "密码", password_row, 3, 0, 2), ("content", "命令内容  *", self.content, 1, 0, 2),
            ("notes", "备注", self.notes, 4, 0, 2)]:
            container = QWidget()
            field_layout = QVBoxLayout(container)
            field_layout.setContentsMargins(0, 0, 0, 5)
            field_layout.setSpacing(5)
            caption = QLabel(label)
            caption.setObjectName("fieldCaption")
            field_layout.addWidget(caption)
            field_layout.addWidget(widget)
            self.fields[key] = container
            grid.addWidget(container, row, column, 1, span)
        form_scroll = QScrollArea()
        form_scroll.setObjectName("formScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_scroll.setMinimumHeight(180)
        form_scroll.setWidget(form_card)
        layout.addWidget(form_scroll, 1)
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
        self.resize(680, 770)

    def selected_kind(self):
        return next((key for key, button in self.type_buttons.items() if button.isChecked()), "website")

    def update_fields(self, *_):
        visible = {"name", "notes"} | ({"url", "username", "login_method", "password"} if self.selected_kind() == "website" else {"content"})
        self.form_hint.setText("带 * 为必填项")
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
        sidebar.setFixedWidth(208)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(18, 29, 18, 20)
        nav.setSpacing(9)
        brand_caption = QLabel("YOUR PERSONAL SPACE")
        brand_caption.setObjectName("sidebarCaption")
        nav.addWidget(brand_caption)
        brand = QLabel("你的资料库")
        brand.setObjectName("sidebarHeading")
        nav.addWidget(brand)
        sub = QLabel("一切常用，都在这里")
        sub.setObjectName("sidebarSub")
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
        privacy = QLabel("●   数据保存在本机")
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
        main_layout.setContentsMargins(36, 27, 36, 30)
        main_layout.setSpacing(15)
        header = QHBoxLayout()
        titlebox = QVBoxLayout()
        titlebox.setSpacing(4)
        page_caption = QLabel("QUICK ACCESS   /   YOUR LIBRARY")
        page_caption.setObjectName("pageCaption")
        titlebox.addWidget(page_caption)
        self.page_title = QLabel("全部项目")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("你的信息，一目了然")
        self.page_subtitle.setObjectName("muted")
        titlebox.addWidget(self.page_title)
        titlebox.addWidget(self.page_subtitle)
        header.addLayout(titlebox)
        header.addStretch()
        add = QPushButton("＋   新建项目")
        add.setObjectName("primary")
        add.setMinimumHeight(42)
        add.clicked.connect(self.add_item)
        header.addWidget(add)
        main_layout.addLayout(header)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.addAction(search_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setPlaceholderText("搜索名称、网址、用户名、登录方式或备注")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        main_layout.addWidget(self.search)
        list_header = QHBoxLayout()
        self.count_label = QLabel("项目")
        self.count_label.setObjectName("sectionLabel")
        list_header.addWidget(self.count_label)
        list_header.addStretch()
        main_layout.addLayout(list_header)

        body = QHBoxLayout()
        body.setSpacing(18)
        self.items = QListWidget()
        self.items.setObjectName("itemList")
        self.items.setMinimumWidth(310)
        self.items.currentItemChanged.connect(self.select_item)
        self.items.itemDoubleClicked.connect(self.open_item)
        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.items)
        empty = QFrame()
        empty.setObjectName("emptyState")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel("✦")
        empty_icon.setObjectName("emptyIcon")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title = QLabel("这里还没有项目")
        self.empty_title.setObjectName("emptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint = QLabel("添加常用网站或命令，随时轻松找到。")
        self.empty_hint.setObjectName("muted")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addSpacing(6)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_hint)
        self.list_stack.addWidget(empty)
        body.addWidget(self.list_stack, 1)
        detail = QFrame()
        detail.setObjectName("detailCard")
        detail.setMinimumWidth(280)
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
        self.detail_fields = {}
        for key, label in [("url", "网址"), ("username", "用户名")]:
            caption = QLabel(label + "  ·  点击复制")
            caption.setObjectName("fieldCaption")
            button = QPushButton()
            button.setObjectName("copyField")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, field=key: self.copy_value(field))
            detail_content_layout.addWidget(caption)
            detail_content_layout.addWidget(button)
            self.detail_fields[key] = button
            self.detail_fields[key + "_label"] = caption
        self.command_container = QWidget()
        command_layout = QVBoxLayout(self.command_container)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command_header = QHBoxLayout()
        command_caption = QLabel("命令内容")
        command_caption.setObjectName("fieldCaption")
        command_header.addWidget(command_caption)
        command_header.addStretch()
        self.copy_command_button = QPushButton("复制全部")
        self.copy_command_button.setObjectName("smallButton")
        self.copy_command_button.clicked.connect(lambda: self.copy_value("content"))
        command_header.addWidget(self.copy_command_button)
        command_layout.addLayout(command_header)
        self.command_view = CommandView(self.record_command_selection)
        command_layout.addWidget(self.command_view, 1)
        command_tip = QLabel("拖动选择部分内容后按 Ctrl+C 复制")
        command_tip.setObjectName("hint")
        command_layout.addWidget(command_tip)
        detail_content_layout.addWidget(self.command_container, 1)
        self.password_label = QLabel("密码")
        self.password_label.setObjectName("fieldCaption")
        detail_content_layout.addWidget(self.password_label)
        password_row = QHBoxLayout()
        self.password = CopyPasswordField(lambda: self.copy_value("password"))
        self.password.setCursor(Qt.CursorShape.PointingHandCursor)
        self.password.setToolTip("点击复制密码")
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
        self.hint = QLabel("双击项目打开网址 · 点击信息复制")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        detail_layout.addWidget(self.hint)
        body.addWidget(detail, 1)
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
        results = self.store.list_items(kind=key if key in TYPES else None, query=self.search.text())
        self.count_label.setText(f"项目  /  {len(results)}")
        self.list_stack.setCurrentIndex(0 if results else 1)
        self.empty_title.setText("没有找到匹配项目" if self.search.text().strip() else "这里还没有项目")
        self.empty_hint.setText("试试其他关键词。" if self.search.text().strip() else "添加常用网站或命令，随时轻松找到。")
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
            for label, value in [("登录方式", item.login_method), ("备注", item.notes)]:
                if value:
                    parts.append(f"{label}\n{value}")
        self.detail_text.setText("\n\n".join(parts) if parts else ("" if item else "从左侧列表选择一项\n即可在这里查看内容。"))
        self.detail_text.setVisible(bool(parts) or not item)
        self.detail_text.setTextFormat(Qt.TextFormat.PlainText)
        for key in ("url", "username"):
            value = getattr(item, key, "") if item else ""
            self.detail_fields[key].setText(value)
            self.detail_fields[key].setToolTip(value)
            self.detail_fields[key].setVisible(bool(value))
            self.detail_fields[key + "_label"].setVisible(bool(value))
        self.command_container.setVisible(bool(item and item.kind == "command"))
        self.command_view.setPlainText(item.content if item and item.kind == "command" else "")
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

    def open_item(self, row):
        item = row.data(Qt.ItemDataRole.UserRole) if row else None
        if item and item.kind == "website" and item.url:
            if not QDesktopServices.openUrl(QUrl.fromUserInput(item.url)):
                QMessageBox.warning(self, "打开失败", "系统无法打开此地址，请检查链接或关联应用。")
            else:
                self.store.record_usage(item.id)
                self.refresh_timer.start(0)

    def record_command_selection(self):
        if self.current and self.current.kind == "command":
            self.store.record_usage(self.current.id)

    def copy_value(self, field):
        if not self.current:
            return
        value = getattr(self.current, field, "")
        if not value:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(value)
        if (self.current.kind == "website" and field in {"url", "password"}) or (self.current.kind == "command" and field == "content"):
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
QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: #28374d; }
QMainWindow, QDialog { background: #f3f5f9; }
QFrame#titleBar { background: #ffffff; border-bottom: 1px solid #ebedf2; }
QLabel#titleLabel { font-size: 12px; font-weight: 700; color: #33415a; }
QPushButton#windowButton, QPushButton#closeButton { background: transparent; border: 0; border-radius: 5px; padding: 0; font-size: 17px; color: #7c879b; }
QPushButton#windowButton:hover { background: #edf1f8; color: #2d3950; }
QPushButton#closeButton:hover { background: #e95c65; color: white; }
QFrame#sidebar { background: #1c2b43; border: 0; }
QFrame#mainArea { background: #f3f5f9; }
QLabel#sidebarCaption { color: #8198b8; font-size: 9px; font-weight: 700; }
QLabel#sidebarHeading { font-size: 19px; font-weight: 700; color: #f4f7ff; }
QLabel#sidebarSub { color: #91a3bd; font-size: 12px; }
QLabel#pageCaption, QLabel#dialogEyebrow { font-size: 10px; font-weight: 700; color: #6480c6; }
QLabel#pageTitle { font-size: 26px; font-weight: 700; color: #1e2b40; }
QLabel#dialogTitle { font-size: 23px; font-weight: 700; color: #1e2b40; }
QLabel#eyebrow, QLabel#sectionLabel { font-size: 11px; font-weight: 700; color: #8390a4; }
QLabel#navCaption { color: #7388a7; font-size: 11px; font-weight: 600; padding-left: 10px; }
QLabel#muted, QLabel#hint { color: #8f9bae; font-size: 12px; }
QLabel#privacyLabel { background: #24364f; border-radius: 8px; color: #a7c5be; font-size: 11px; padding: 10px; }
QListWidget#navigation { background: transparent; border: 0; outline: 0; padding: 0; }
QListWidget#navigation::item { border-radius: 8px; min-height: 43px; padding-left: 12px; color: #a8b8d0; margin: 2px 0; }
QListWidget#navigation::item:selected { background: #344b6c; color: #ffffff; font-weight: 700; }
QListWidget#navigation::item:hover:!selected { background: #293b56; color: #f2f6ff; }
QPushButton { background: white; border: 1px solid #dfe6ee; border-radius: 8px; padding: 9px 16px; color: #485b74; text-transform: none; }
QPushButton:hover { background: #f4f7fd; border-color: #cbd6e9; }
QPushButton#primary { background: #506ed4; border: 1px solid #506ed4; color: white; font-weight: 700; padding: 10px 19px; }
QPushButton#primary:hover { background: #415fc5; }
QPushButton#aboutButton { text-align: left; background: transparent; border: 0; color: #a2b3ca; padding: 10px; }
QPushButton#aboutButton:hover { background: #293b56; color: #ffffff; }
QPushButton#smallButton, QPushButton#dangerButton, QPushButton#subtleButton { padding: 6px 10px; font-size: 11px; background: #f2f5fa; border: 0; }
QPushButton#dangerButton { color: #c76a72; }
QPushButton#copyField { text-align: left; background: #f5f7fb; border: 1px solid #e7edf4; padding: 9px; }
QPushButton#copyField:hover { background: #edf2ff; border-color: #b8c8ed; }
QPushButton:disabled { color: #c7cfdb; }
QPushButton#typeButton { min-height: 30px; text-align: left; padding: 8px 16px; background: #ffffff; border: 1px solid #e2e8f1; color: #708097; }
QPushButton#typeButton:checked { background: #edf2ff; border: 1px solid #aebfe9; color: #4867bc; font-weight: 700; }
QPushButton#typeButton:checked:disabled { background: #edf2ff; color: #4867bc; }
QFrame#formCard { background: #ffffff; border: 1px solid #e5eaf1; border-radius: 12px; }
QScrollArea#formScroll { background: transparent; border: 0; }
QLabel#formTitle { color: #33445e; font-size: 13px; font-weight: 700; }
QLabel#formHint { color: #a4afbe; font-size: 11px; }
QLineEdit, QTextEdit, QPlainTextEdit { background: #fbfcfe; border: 1px solid #e2e8f0; border-radius: 8px; padding: 9px 11px; selection-background-color: #667ce4; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { background: #ffffff; border: 1px solid #8fa9eb; }
QPlainTextEdit#commandView, QPlainTextEdit#commandEditor { font-family: 'Consolas', 'Microsoft YaHei UI'; background: #f4f6fa; color: #283b58; border: 1px solid #e1e7f0; padding: 12px; }
QLineEdit#search { min-height: 27px; padding: 8px 12px; background: #ffffff; border: 1px solid #e5eaf2; }
QListWidget#itemList, QListWidget#itemList QWidget { background: transparent; border: 0; outline: 0; padding: 0; }
QListWidget#itemList::item { background: #ffffff; border: 1px solid #e9edf3; border-radius: 11px; margin-bottom: 7px; }
QListWidget#itemList::item:selected { background: #edf3ff; border: 1px solid #b9c9eb; }
QListWidget#itemList::item:hover:!selected { background: #fbfcff; border: 1px solid #d2dceb; }
QLabel#rowIcon, QLabel#detailIcon { background: #eaf0ff; color: #5c79cd; border-radius: 11px; font-size: 20px; font-weight: 700; }
QLabel#rowIconCommand { background: #e8f4ef; color: #5ca391; border-radius: 11px; font-size: 19px; font-weight: 700; }
QLabel#rowTitle { color: #2d3951; font-size: 14px; font-weight: 600; background: transparent; }
QLabel#rowSubtitle { color: #98a4b5; font-size: 12px; background: transparent; }
QLabel#rowArrow { color: #aeb8c8; font-size: 22px; background: transparent; }
QFrame#detailCard { background: #ffffff; border: 1px solid #e7ecf2; border-radius: 12px; }
QFrame#emptyState { background: #ffffff; border: 1px solid #e8edf4; border-radius: 12px; }
QLabel#emptyIcon { background: #edf2ff; color: #6b87d4; border-radius: 24px; font-size: 22px; min-width: 48px; min-height: 48px; max-width: 48px; max-height: 48px; }
QLabel#emptyTitle { color: #51627b; font-size: 15px; font-weight: 700; }
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
