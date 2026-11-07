"""Non-blocking, user-confirmed GitHub Release update flow."""
import shutil
import subprocess
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout
from .updates import check_latest, download_installer
from .version import VERSION


class UpdateWorker(QThread):
    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as exc:
            self.error = str(exc)


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("检查更新")
        self.setMinimumWidth(480)
        self.worker = None
        self.release = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(14)
        title = QLabel("软件更新")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        self.status = QLabel(f"当前版本  {VERSION}  ·  从 GitHub 获取正式版本")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setPlaceholderText("检查后将在这里显示更新说明。")
        self.notes.setMinimumHeight(150)
        layout.addWidget(self.notes)
        actions = QHBoxLayout()
        actions.addStretch()
        self.check_button = QPushButton("检查更新")
        self.check_button.clicked.connect(self.check_updates)
        self.install_button = QPushButton("下载并安装")
        self.install_button.setObjectName("primary")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.download_update)
        actions.addWidget(self.check_button)
        actions.addWidget(self.install_button)
        layout.addLayout(actions)

    def _start(self, action, operation, message):
        if self.worker and self.worker.isRunning():
            return
        self.status.setText(message)
        self.check_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.worker = UpdateWorker(operation, self)
        self.worker.finished.connect(lambda: self._finished(action))
        self.worker.start()

    def check_updates(self):
        self.release = None
        self.notes.clear()
        self._start("check", lambda: check_latest(VERSION), "正在检查更新…")

    def download_update(self):
        if not self.release:
            return
        answer = QMessageBox.question(self, "下载更新", f"确定下载 QuickBox {self.release.version} 的安装包吗？")
        if answer == QMessageBox.StandardButton.Yes:
            self._start("download", lambda: download_installer(self.release), "正在下载并校验安装包，请稍候…")

    def _finished(self, action):
        worker = self.worker
        self.check_button.setEnabled(True)
        if worker.error:
            self.status.setText(worker.error)
            self.install_button.setEnabled(self.release is not None)
            return
        if action == "check":
            self.release = worker.result
            if self.release is None:
                self.status.setText("当前已是最新版本，或仓库尚未发布正式版本。")
            else:
                self.status.setText(f"发现新版本  {self.release.version}")
                self.notes.setPlainText(self.release.notes or "此版本没有填写更新说明。")
                self.install_button.setEnabled(True)
            return
        path = worker.result
        self.install_button.setEnabled(True)
        answer = QMessageBox.question(self, "准备安装", "安装包下载并校验完成。现在关闭 QuickBox 并启动安装程序吗？")
        if answer != QMessageBox.StandardButton.Yes:
            shutil.rmtree(path.parent, ignore_errors=True)
            self.status.setText("已取消安装。")
            return
        try:
            subprocess.Popen([str(path)], close_fds=True)
        except OSError as exc:
            shutil.rmtree(path.parent, ignore_errors=True)
            self.status.setText(f"无法启动安装程序：{exc}")
            return
        self.accept()
        if self.parent():
            self.parent().close()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.status.setText("正在处理更新，请等待完成。")
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.status.setText("正在处理更新，请等待完成。")
            return
        super().reject()
