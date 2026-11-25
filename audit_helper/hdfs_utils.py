"""hdfs_utils — Заглушки для демонстрационной версии.

Полная версия использует реальные HDFS-методы (hdfs://arnsdpsbx).
В демо-версии все методы возвращают заглушённые данные.
"""
import json
import os

HDFS_FOLDER = os.path.expanduser("~/.oait_skillhub_hdfs")


def hdfs_exists(path: str) -> bool:
    """Проверяет существование файла на HDFS."""
    return False


def hdfs_read(path: str) -> str:
    """Читает файл с HDFS. В демо возвращает заглушку."""
    return json.dumps({"tools": {}, "error": "HDFS недоступен в демо-версии"})


def hdfs_write(path: str, content: str) -> None:
    """Записывает файл на HDFS. В демо ничего не делает."""
    pass


def hdfs_delete(path: str) -> None:
    """Удаляет файл с HDFS. В демо ничего не делает."""
    pass


def hdfs_list(path: str) -> str:
    """Возвращает список файлов на HDFS. В демо возвращает заглушку."""
    return ""


def hdfs_delete_dir(path: str) -> None:
    """Удаляет директорию на HDFS. В демо ничего не делает."""
    pass


def hdfs_mkdir(path: str) -> None:
    """Создаёт директорию на HDFS. В демо ничего не делает."""
    pass