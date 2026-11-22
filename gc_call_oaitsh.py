"""gc_call_oaitsh"""
import os
import json
import requests
from langchain.llms.base import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from typing import Any, List, Optional, Dict
import tools_utils


class CustomLLM(LLM):
    """Кастомная LLM для работы с GigaChat API."""

    @property
    def _llm_type(self) -> str:
        return "custom_gigachat"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        MODEL_URL = "http://liveaccess/v1/gc/chat/completions"
        HEADERS = {
            'Authorization': f'Bearer {os.environ.get("JPY_API_TOKEN")}',
            'Content-Type': 'application/json',
        }

        # Формируем полный промпт
#         full_prompt = f"""Ты интеллектуальный помощник по имени Трофим_2.0.
# Помогаешь в подготовке материалов для актов аудиторской проверки.
# Ты МОЖЕШЬ запускать зарегистрированные инструменты (функции), если это необходимо для ответа на вопрос.
# Если ты не уверен, что инструмент подходит, или не нашел подходящий инструмент, вежливо откажись и предложи задать другой вопрос.
# ВСЕГДА вызывай инструменты для выполнения расчетов или получения данных. Не пытайся вычислять или предполагать ответ сам.

# {prompt}"""

        full_prompt = f"""Ты интеллектуальный помощник по имени ai_BP_helper.
Помогаешь в подготовке материалов для актов аудиторской проверки.
Будь внимателен!

Сначала составь план того, что будешь делать, а потом следуй ему.

Не нужно делать запрос заново, если на вопрос пользователя можно ответить на основе той информации, что получена до этого.
Также не надо делать один и тот же запрос в надежде получить новый результат!

{prompt}"""

        # print(f'ПОЛНЫЙ ПРОМТ КОТОРЫЙ ИДЕТ МОДЕЛИ НА ВХОД\n/////////////{full_prompt}\n///////////////')

        # assert 1 == full_prompt, "Остановочка"

        data = {
            "model": "GigaChat-2-Max",
            "messages": [{"role": "user", "content": full_prompt}],
            # 'temperature': 0.1,
            # 'temperature': 0.9,
            "temperature": 0.9,
            "top_p": 0.2,
            "stream": False,
        }
        try:
            r = requests.post(MODEL_URL, headers=HEADERS, json=data, timeout=120)
            r.raise_for_status()
            answer = r.json()
            return answer["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            return f"Ошибка запроса к API: {e}"
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return f"Ошибка парсинга ответа от API: {e}. Ответ: {r.text}"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_name": "GigaChat-2-Max"}


def init_agent():
    # Загружаем инструменты
    tools_cfg = tools_utils.load_tools_config()
    if not tools_cfg:
        raise RuntimeError("⚠️ Не удалось загрузить tools_config.json")

    # Инициализируем нашу кастомную LLM
    llm = CustomLLM()

    return llm, tools_cfg


# if __name__ == "__main__":
#     llm, tools_cfg = init_agent()
#     print("✅ Агент инициализирован. Готов к работе.")
#     print(f"Доступные инструменты: {list(tools_cfg.keys())}")