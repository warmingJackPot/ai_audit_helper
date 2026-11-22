"""multi_tool_handler.py"""
import json
import re
from typing import List, Dict, Any
from vm1_mcp_logger_client import submit_job
# from vm1_fast_worker import vm1_fast_worker  # Если используете быстрый воркер


class MultiToolHandler:
    """MultiToolHandler"""
    def __init__(self):
        self.results = {}

    def safe_extract_json(self, text: str) -> Dict[str, Any]:
        """Извлекает JSON из текста с поддержкой multi_tool_call"""
        try:
            # Ищем JSON объект
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                json_str = match.group()
                data = json.loads(json_str)

                # Проверяем поддерживаемые форматы
                # if data.get("action") in ["tool_call", "multi_tool_call", "text_response"]:
                if isinstance(data.get("action"), str):
                    if data["action"] in ["tool_call", "multi_tool_call", "text_response"]:
                        return data

        except Exception as e:
            print(f"Ошибка парсинга JSON: {e}")

        return None

    def execute_multi_tool_call(self, calls: List[Dict], tools_cfg: Dict) -> tuple:
        """
        Выполняет несколько инструментов последовательно.
        Важно: возвращает (summary_text, per_call_results)
        per_call_results = [{"tool_name":..., "params":..., "result":...}, ...]
        """
        results_summary = []
        per_call_results = []

        for i, call in enumerate(calls):
            tool_name = call.get("tool_name")
            params = call.get("params", {}) or {}

            if not tool_name:
                results_summary.append(f"❌ Ошибка: отсутствует tool_name в вызове {i+1}")
                continue

            if tool_name not in tools_cfg:
                results_summary.append(f"❌ Инструмент {tool_name} не найден")
                continue

            try:
                # submit_job уже ждёт выполнения и возвращает результат
                tool_res = submit_job(tool_name, params)

                per_call_results.append({
                    "tool_name": tool_name,
                    "params": params,
                    "result": tool_res
                })

                # summary — коротко, чтобы не раздувать
                short = str(tool_res)
                if len(short) > 200:
                    short = short[:200] + "...(truncated)"
                results_summary.append(f"✅ {tool_name}: {short}")

            except Exception as e:
                results_summary.append(f"❌ {tool_name}: ошибка выполнения - {str(e)}")

        return "\n".join(results_summary), per_call_results

    def handle_llm_response(self, response: str, tools_cfg: Dict, memory) -> str:
        """Обрабатывает ответ LLM с поддержкой multiple tool calls"""
        parsed = self.safe_extract_json(response)

        if not parsed:
            # return "Не удалось распознать команду"
            return None
            # return "_"
            # pass

        action = parsed.get("action")

        if action == "text_response":
            return parsed.get("text", "Пустой ответ")

        elif action == "tool_call":
            # Одиночный вызов (обратная совместимость)
            tool_name = parsed.get("tool_name")
            params = parsed.get("params", {})

            if tool_name and tool_name in tools_cfg:
                from vm1_mcp_logger_client import submit_job
                test_tool_res = submit_job(tool_name, params)

                #вывод странный, каждый раз пигет что запрос отправлен в очередь на hdfs, а что это значит на 14.11.25 уже не помню)
                return test_tool_res , f"Запрос {tool_name} отправлен в очередь на HDFS"
            else:
                return f"Инструмент {tool_name} не найден"

        elif action == "multi_tool_call":
            # Множественный вызов
            calls = parsed.get("calls", [])
            if calls:
                return self.execute_multi_tool_call(calls, tools_cfg)
            else:
                return "Пустой список вызовов"

        return "Неизвестная команда"


# Глобальный экземпляр
multi_tool_handler = MultiToolHandler()