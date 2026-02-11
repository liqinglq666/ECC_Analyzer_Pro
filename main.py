import sys
import traceback
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt


# 全局异常捕获函数 (防止程序无声崩溃)
def exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    print("CRITICAL ERROR:", error_msg)

    # 尝试弹窗显示错误 (只有在 QApplication 启动后才能弹窗)
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Application Error")
        msg.setText("An unexpected error occurred.\n程序发生意外错误。")
        msg.setDetailedText(error_msg)
        msg.exec()

    # 保持非零退出码，方便 IDE 识别错误
    sys.exit(1)


sys.excepthook = exception_hook


def main():
    # 1. 创建应用实例
    app = QApplication(sys.argv)
    app.setApplicationName("ECC Analyzer Pro")

    # [Fix] Qt 6 默认已开启 High DPI，移除废弃的 setAttribute 以消除警告
    # 仅在极少数特殊情况下需要手动调整缩放策略
    if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
        app.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    # 2. 延迟导入主窗口 (确保 excepthook 已生效)
    try:
        # 检查关键目录是否存在
        root_dir = Path(__file__).parent
        if not (root_dir / "app").exists():
            raise FileNotFoundError("Critical folder 'app' not found in project root.")

        from app.ui.main_window import MainWindow

        # 3. 初始化并显示
        window = MainWindow()
        window.show()

        # 4. 进入事件循环
        sys.exit(app.exec())

    except ImportError as e:
        err_str = f"Missing required files.\n缺少必要模块: {e}\n\nPlease check your 'app' folder structure."
        print(err_str)
        QMessageBox.critical(None, "Import Error", err_str)
        sys.exit(1)

    except Exception as e:
        # 手动触发异常处理
        exception_hook(type(e), e, e.__traceback__)


if __name__ == "__main__":
    main()