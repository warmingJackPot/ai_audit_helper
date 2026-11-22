"""vm1_local_worker — Заглушки для демонстрационной версии.

Полная версия сканирует HDFS-папку requests и выполняет задания.
В демо-версии воркер не запускается — инструменты выполняются через submit_job().
"""
import time
from threading import Thread
from typing import Dict, Any, List
from utils import log_print


class VM1LocalWorker:
    """Заглушка воркера VM1. В демо не запускается."""
    def __init__(self, poll_interval: int = 3):
        self.poll_interval = poll_interval
        self.is_running = False
        self.worker_thread = None
        self.tools_config: Dict[str, Any] = {}
        self.processed_requests = set()

    def _append_log(self, uid: str, text: str):
        """Заглушка."""
        pass

    def _update_status(self, uid: str, status: str, error: str = None):
        """Заглушка."""
        pass

    def _get_request_status(self, uid: str) -> str:
        """Заглушка."""
        return "unknown"

    def _process_request(self, request_path: str):
        """Заглушка — в демо инструменты выполняются через submit_job()."""
        pass

    def _scan_requests_directory(self) -> List[str]:
        """Заглушка — возвращает пустой список."""
        return []

    def _check_requests(self):
        """Заглушка — ничего не делает."""
        pass

    def start(self):
        """Заглушка — не запускает воркер."""
        log_print("[VM1 Worker] Демо-версия: воркер не запускается (HDFS недоступен)")
        log_print("[VM1 Worker] Инструменты выполняются через submit_job() напрямую")
        self.is_running = True

    def stop(self):
        """Заглушка."""
        self.is_running = False


# Глобальный экземпляр воркера
vm1_worker = VM1LocalWorker()