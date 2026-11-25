"""vm1_mcp_logger_client — Заглушки для демонстрационной версии.

Полная версия отправляет задания в HDFS-очередь и ждёт выполнения.
В демо-версии выполняет инструменты локально и возвращает заглушённые результаты.
"""
import json
import importlib

from audit_helper.tools_utils import load_tools_config


def submit_job(method: str, params: dict, timeout: int = 1200) -> str:
    """
    Отправляет задание на выполнение. В демо-версии пытается выполнить
    инструмент локально, если он доступен, иначе возвращает заглушку.
    """
    print(f"[DEMO] Отправка задания: {method} с params {params}")
    print(f"[DEMO] HDFS недоступен в демо-версии, пытаюсь выполнить локально...")

    tools_cfg = load_tools_config()

    # Пытаюсь найти инструмент в конфиге
    tool_config = tools_cfg.get(method)
    if tool_config and tool_config.get("host") == "vm1" and tool_config.get("type") == "python_fn":
        entrypoint = tool_config.get("entrypoint")
        if entrypoint and ":" in entrypoint:
            try:
                module_name, func_name = entrypoint.split(":", 1)
                module = importlib.import_module(module_name)
                func = getattr(module, func_name)
                result = func(**params)
                print(f"[DEMO] Инструмент {method} выполнен локально")
                return json.dumps({"result": result, "status": "done"}, ensure_ascii=False)
            except Exception as e:
                print(f"[DEMO] Ошибка локального выполнения: {e}")

    # Инструмент не найден или не local — возвращаем заглушку
    result = {
        "method": method,
        "params": params,
        "status": "demo_placeholder",
        "message": f"Инструмент '{method}' недоступен в демо-версии.",
        "note": "Полная версия требует HDFS и Spark-кластер ОАИТ.",
        "available_tools": list(tools_cfg.keys())
    }
    print(f"[DEMO] Возвращён placeholder: {method}")
    return json.dumps(result, ensure_ascii=False, indent=2)