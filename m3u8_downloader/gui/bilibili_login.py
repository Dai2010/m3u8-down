from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from ..config.manager import config_path
from ..core.bilibili_auth import BilibiliLoginError, login_bilibili_web_qr


class BilibiliLoginWorker(QThread):
    status = pyqtSignal(str)
    qr_code_ready = pyqtSignal(str)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = login_bilibili_web_qr(
                config_path().parent / "bilibili-login.png",
                status_callback=self.status.emit,
                cancel_callback=lambda: self._cancelled,
                qr_code_callback=lambda path: self.qr_code_ready.emit(str(path)),
            )
        except BilibiliLoginError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - GUI displays a concise login error.
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result.cookie)
