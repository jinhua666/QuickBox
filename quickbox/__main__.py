import sys
import ctypes
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from .storage import Storage, default_path
from .ui import MainWindow, UnlockDialog, STYLE, asset_path


def main():
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QuickBox.PersonalHub.Desktop")
    app = QApplication(sys.argv)
    app.setApplicationName("QuickBox")
    app.setWindowIcon(QIcon(str(asset_path("quickbox.ico"))))
    app.setStyleSheet(STYLE)
    try:
        store = Storage(default_path())
    except Exception as exc:
        QMessageBox.critical(None, "无法打开 QuickBox 数据", str(exc))
        return 1
    dialog = UnlockDialog(store)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        store.close()
        return 0
    window = MainWindow(store)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
