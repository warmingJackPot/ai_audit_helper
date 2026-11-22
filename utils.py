"""utils — вспомогательные утилиты."""
import sys


def log_print(*args, **kwargs):
    """Печатает диагностику в stderr (не мешает UI rich-панелей)."""
    print(*args, file=sys.stderr, **kwargs)