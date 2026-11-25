"""tools_utils — Заглушки для демонстрационной версии.

Полная версия загружает tools_config.json из HDFS.
В демо-версии загружает из локального файла или возвращает заглушку.
"""
import json
from pathlib import Path

LOCAL_TOOLS_CONFIG = Path(__file__).resolve().parents[1] / "tools_config.sample.json"


def load_tools_config() -> dict:
    """Загружает список инструментов. Сначала из локального файла, потом из заглушки."""
    try:
        if LOCAL_TOOLS_CONFIG.exists():
            with open(LOCAL_TOOLS_CONFIG, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                return config_data.get("tools", {})
    except Exception:
        pass
    return {
        "cur_datetime": {
            "name": "cur_datetime",
            "host": "vm1",
            "type": "python_fn",
            "entrypoint": "audit_helper.tools.time_tool:cur_datetime",
            "args": [],
            "description": "Показывает текущую дату и время"
        },
        "calculate_numbers": {
            "name": "calculate_numbers",
            "host": "vm1",
            "type": "python_fn",
            "entrypoint": "audit_helper.tools.math_tools:calculate_numbers",
            "args": ["a", "b", "operation"],
            "description": "Выполняет арифметическую операцию"
        }
    }


def format_tools_for_prompt(tools: dict) -> str:
    """Форматирует список инструментов в человекочитаемый текст."""
    lines = []
    for name, cfg in tools.items():
        args = ", ".join(cfg.get("args", []))
        server = cfg.get("host", "vm1")
        lines.append(f"- {name} (host={server}, args: {args}): {cfg.get('description', '')}")
    return "\n".join(lines)