import sys
import os
import traceback
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt


# 全局异常捕获函数：避免桌面程序无声退出，便于定位运行问题。
def exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print("CRITICAL ERROR:", error_msg)

    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Application Error")
        msg.setText("An unexpected error occurred.\n程序发生意外错误。")
        msg.setDetailedText(error_msg)
        msg.exec()
    sys.exit(1)


sys.excepthook = exception_hook


def get_resource_path(relative_path):
    """获取资源绝对路径，兼容开发环境与 PyInstaller 打包环境。"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(os.path.abspath(".")) / relative_path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ECC Analyzer Pro")

    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    try:
        resource_root = get_resource_path("")
        if str(resource_root) not in sys.path:
            sys.path.insert(0, str(resource_root))

        # 正式运行窗口：基础 UI 在 app.ui.main_window 中，当前生效行为集中在 active 层维护。
        from app.ui.main_window_active import MainWindow

        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except ImportError as e:
        err_str = f"Module not found: {e}\n\n请确保依赖安装完整，并且项目根目录下包含 app 文件夹。"
        print(err_str)
        if QApplication.instance():
            QMessageBox.critical(None, "Import Error", err_str)
        sys.exit(1)
    except Exception as e:
        exception_hook(type(e), e, e.__traceback__)


if __name__ == "__main__":
    main()
