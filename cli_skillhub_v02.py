"""cli_skillhub_v02.py"""
import os
import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from gc_call_oaitsh import init_agent
from vm1_mcp_logger_client import submit_job
from vm1_local_worker import vm1_worker
from langchain.memory import ConversationBufferMemory

from multi_tool_handler import multi_tool_handler
from utils import log_print

from rich.console import Console
from rich.panel import Panel

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

console = Console()


# =========================
# Красивый ввод
# =========================
def beautiful_input() -> str:
    session = PromptSession()
    user_input = session.prompt(HTML('<style fg="cyan" bg="black">>> MASTER: </style>'))
    return user_input


# =========================
# Локальная память на VM1 (НЕ HDFS)
# =========================
_MEM_ROOT = os.path.expanduser("memory")
_SESS_DIR = os.path.join(_MEM_ROOT, "sessions")
_GLOBAL_MEM_PATH = os.path.join(_MEM_ROOT, "global_memory.jsonl")


def _ensure_mem_dirs():
    os.makedirs(_MEM_ROOT, exist_ok=True)
    os.makedirs(_SESS_DIR, exist_ok=True)


def session_state_path(session_id: str) -> str:
    _ensure_mem_dirs()
    return os.path.join(_SESS_DIR, f"session_{session_id}.json")


def load_session_state(session_id: str) -> Dict[str, Any]:
    path = session_state_path(session_id)
    if not os.path.exists(path):
        return {
            "session_id": session_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role_prompt": "",
            "goal": "",
            "plan": [],
            "executed_trace": [],
            "facts": [],
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "session_id": session_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role_prompt": "",
            "goal": "",
            "plan": [],
            "executed_trace": [],
            "facts": [],
        }


def save_session_state(state: Dict[str, Any]) -> None:
    _ensure_mem_dirs()
    path = session_state_path(state["session_id"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def append_trace(state: Dict[str, Any], tool_name: str, params: Dict[str, Any], result_ref: str) -> None:
    state.setdefault("executed_trace", [])
    state["executed_trace"].append(
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool": tool_name,
            "params": params or {},
            # "result_ref": (result_ref or "")[:800],
            "result_ref": (result_ref or ""),
        }
    )


def append_global_memory(items: List[Dict[str, Any]], session_id: str) -> None:
    """
    items: [{"key":"...", "value":"...", "source":"..."}]
    """
    _ensure_mem_dirs()
    with open(_GLOBAL_MEM_PATH, "a", encoding="utf-8") as f:
        for it in items:
            row = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session_id": session_id,
                "key": it.get("key", ""),
                "value": it.get("value", ""),
                "source": it.get("source", ""),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def search_global_memory(query: str, limit: int = 12) -> str:
    """
    1) Сначала ищем совпадения по key/value (а не по сырой строке).
    2) Если ничего не нашли — возвращаем последние N записей (fallback),
    """
    _ensure_mem_dirs()
    if not os.path.exists(_GLOBAL_MEM_PATH):
        return ""

    q = (query or "").strip().lower()

    rows = []
    try:
        with open(_GLOBAL_MEM_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return ""

    if not rows:
        return ""

    # фильтруем только полезные записи
    allowed_sources = {"user_pref", "env_limit", "domain_fact", "artifact_ref"}
    rows = [r for r in rows if (r.get("source") in allowed_sources)]

    # 1) релевантные
    hits = []
    if q:
        for r in rows:
            kv = f"{r.get('key','')} {r.get('value','')}".lower()
            if q in kv:
                hits.append(r)

    # 2) fallback: последние N, если пусто
    if not hits:
        hits = rows[-min(limit, len(rows)):]
    else:
        hits = hits[-min(limit, len(hits)):]

    # форматируем компактно (не сырой json)
    out = []
    for r in hits:
        out.append(f"- ({r.get('source')}) {r.get('key')}: {str(r.get('value'))[:240]}")
    return "\n".join(out)


# =========================
# Парсинг ручного run ...
# =========================
def parse_manual_run(cmdline: str):
    """
    Пример:
    run check_illegal_access subdivision=блокТ script_name=pyspark_request_test.py timeframe=14
    """
    parts = cmdline.strip().split()
    if not parts:
        return None
    if parts[0] != "run":
        return None
    if len(parts) < 2:
        return None

    method = parts[1]
    params = {}
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            if v.isdigit():
                v = int(v)
            else:
                try:
                    v = float(v)
                except Exception:
                    pass
            params[k] = v
    return method, params


# =========================
# JSON extraction (из ответа LLM)
# =========================
def _extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        return json.loads(m.group())
    except Exception:
        return None


def _short(s: Any, n: int = 1400) -> str:
    t = str(s)
    return t if len(t) <= n else t[:n] + "...(truncated)"


# =========================
# Prompt builders
# =========================
def _tools_list_for_prompt(tools_cfg: Dict[str, Any]) -> str:
    out = []
    for name, details in tools_cfg.items():
        out.append(
            f"- {name}: {details.get('description', '')} | args={details.get('args', [])} | host={details.get('host', 'vm1')}"
        )
    return "\n".join(out)


def build_main_prompt(
    state: Dict[str, Any],
    user_query: str,
    history: str,
    tools_cfg: Dict[str, Any],
) -> str:
    mem_hits = search_global_memory(user_query, limit=10)
    if mem_hits:
        log_print(f"[DOMAIN_KNOWLEDGE] mem_hits:\n{_short(mem_hits, 400)}")
    else:
        log_print("[DOMAIN_KNOWLEDGE] mem_hits: (empty)")


    role_prompt = (state.get("role_prompt") or "").strip()

    role_block = f"[ROLE UPDATE]\n{role_prompt}\n\n" if role_prompt else ""

    tools_list = _tools_list_for_prompt(tools_cfg)

    prompt = f"""
{role_block}Ты AI-агент. Твоя задача — отвечать на запрос пользователя и при необходимости вызывать инструменты.

Требования (Reasoning/Reflection/Memory/Role):
- Всегда сначала формируй ПЛАН (список шагов).
- После результатов инструментов план МОЖНО И НУЖНО корректировать, если это помогает цели.
- Не делай повторный запрос, если уже есть данные для ответа.
- Будь автономен в выборе шагов — просто не спрашивай подтверждений.

Локальная память (из прошлых сессий; используй как дополнительные предметные знания при релевантности):
{mem_hits if mem_hits else "(пока пусто)"}

История диалога:
//////////////////
{history}
//////////////////

Доступные инструменты:
{tools_list}

Запрос пользователя: {user_query}

ФОРМАТ (ВАЖНО): отвечай ТОЛЬКО одним JSON-объектом (без текста вокруг).
Допускаются ТОЛЬКО 3 типа:

1) tool_call:
{{"action":"tool_call","plan":[...],"tool_name":"...","params":{{...}}}}

2) multi_tool_call:
{{"action":"multi_tool_call","plan":[...],"calls":[{{"tool_name":"...","params":{{...}}}}, ...]}}

3) text_response:
{{"action":"text_response","plan":[...],"text":"..."}}

Правила:
- Не выдумывай параметры инструментов.
- Если инструмент не нужен — верни text_response.
"""
    return prompt.strip()


def build_followup_prompt(
    state: Dict[str, Any],
    original_user_query: str,
    history: str,
    tools_cfg: Dict[str, Any],
    last_tool_result: str,
) -> str:
    """
    После выполнения инструментов просим модель:
    - отрефлексировать в голове и продолжить (либо еще инструменты, либо финальный text_response)
    """
    mem_hits = search_global_memory(original_user_query, limit=10)
    # if mem_hits:
    #     log_print(f"[DOMAIN_KNOWLEDGE] mem_hits:\n{_short(mem_hits, 400)}")
    # else:
    #     log_print("[DOMAIN_KNOWLEDGE] mem_hits: (empty)")
    role_prompt = (state.get("role_prompt") or "").strip()
    role_block = f"[ROLE UPDATE]\n{role_prompt}\n\n" if role_prompt else ""
    tools_list = _tools_list_for_prompt(tools_cfg)
    plan_now = state.get("plan", [])

    prompt = f"""
{role_block}Ты AI-агент. Продолжай решение задачи с учетом результата инструмента.

ЦЕЛЬ (исходный запрос пользователя):
{original_user_query}

ТЕКУЩИЙ ПЛАН:
{json.dumps(plan_now, ensure_ascii=False)}

Последний результат инструментов:
{last_tool_result}

Локальная память (доп. знания):
{mem_hits if mem_hits else "(пока пусто)"}

История диалога:
//////////////////
{history}
//////////////////

Доступные инструменты:
{tools_list}

ФОРМАТ (ВАЖНО): отвечай ТОЛЬКО одним JSON-объектом (без текста вокруг).
Допускаются ТОЛЬКО 3 типа:

1) tool_call:
{{"action":"tool_call","plan":[...],"tool_name":"...","params":{{...}}}}

2) multi_tool_call:
{{"action":"multi_tool_call","plan":[...],"calls":[{{"tool_name":"...","params":{{...}}}}, ...]}}

3) text_response:
{{"action":"text_response","plan":[...],"text":"..."}}

Правила:
- Не повторяй уже сделанные вызовы без причины.
- Если данных уже достаточно — возвращай text_response.
"""
    return prompt.strip()

# old build version
# def build_reflection_prompt(
#     state: Dict[str, Any],
#     original_user_query: str,
#     last_tool_result: str,
# ) -> str:
#     trace_tail = state.get("executed_trace", [])[-8:]
#     plan_now = state.get("plan", [])

#     prompt = f"""
# Ты модуль РЕФЛЕКСИИ AI-агента.
# Сравни: (1) ЦЕЛЬ, (2) ТЕКУЩИЙ ПЛАН, (3) ФАКТИЧЕСКИЕ ДЕЙСТВИЯ И РЕЗУЛЬТАТ.
# Если видишь несоответствие — предложи новый план и/или следующие tool-вызовы.
# Также реши, что важно сохранить в долгосрочную локальную память.

# Верни ТОЛЬКО JSON строго такого вида:
# {{
#   "reflection_ok": true/false,
#   "mismatches": ["..."],
#   "new_plan": ["..."],
#   "next_actions": [{{"tool_name":"...", "params":{{...}}}}, ...],
#   "memory_write": [{{"key":"...", "value":"...", "source":"tool/analysis"}}],
#   "role_update": "короткое обновление роли или пустая строка"
# }}

# ЦЕЛЬ:
# {original_user_query}

# ТЕКУЩИЙ ПЛАН:
# {json.dumps(plan_now, ensure_ascii=False)}

# ФАКТИЧЕСКИЕ ДЕЙСТВИЯ (последние):
# {json.dumps(trace_tail, ensure_ascii=False)}

# ПОСЛЕДНИЙ РЕЗУЛЬТАТ ИНСТРУМЕНТА:
# {last_tool_result}
# """
#     return prompt.strip()

def build_reflection_prompt(
    state: Dict[str, Any],
    original_user_query: str,
    last_tool_result: str,
) -> str:
    trace_tail = state.get("executed_trace", [])[-8:]
    plan_now = state.get("plan", [])

    prompt = f"""
Ты модуль РЕФЛЕКСИИ AI-агента.

Твоя задача:
1) Сравнить ЦЕЛЬ, ТЕКУЩИЙ ПЛАН и ФАКТИЧЕСКИЕ ДЕЙСТВИЯ (trace) + РЕЗУЛЬТАТ.
2) Понять, достигнута ли цель, и соответствует ли результат плану.
3) Если есть несоответствия — предложить исправление: новый план и/или следующие tool-вызовы.
4) Решить, что полезно сохранить в долгосрочную локальную память (НЕ логи).

КРИТИЧЕСКИ ВАЖНО ПРО ПАМЯТЬ (memory_write):
- НЕЛЬЗЯ сохранять "логи", "trace", "что какой инструмент вызвали", "статусы submitted/done", "сырой вывод stdout/stderr", длинные CSV.
- МОЖНО сохранять ТОЛЬКО полезные устойчивые знания:
  A) предпочтения пользователя/стиль ("не сглаживать углы", "формат как аудиторский акт"),
  B) устойчивые правила поведения агента ("сначала сводка, затем ссылка на файл"),
  C) ссылки/пути к важным артефактам/результатам ("результат выгрузки лежит в ..."),
  D) доменные факты/расшифровки, которые помогут позже.
- Максимум 3 пункта в memory_write.
- Текст для сохранения должен быть в таком виде, чтобы он отражал какой-то произошедший факт, чтобы модели было полезно на него оринетироваться в будущем.
- Если нечего полезного сохранять — memory_write = [].

ПРО РОЛЬ (role_update):
- Запросы требуют смены ролей, будь в этом свободен!
- Если выявлен повторяющийся паттерн/ошибка/требование к стилю (например: "слишком большие выдачи", "часто нужно резюмировать", "пользователь хочет актовый стиль")
  — ОБЯЗАТЕЛЬНО заполни role_update как постоянное правило поведения (1–3 предложения).
- Если обновление роли не нужно — role_update = ""

Формат ответа: верни ТОЛЬКО JSON строго такого вида:
{{
  "reflection_ok": true/false,
  "mismatches": ["..."],
  "new_plan": ["..."],
  "next_actions": [{{"tool_name":"...", "params":{{...}}}}, ...],
  "memory_write": [{{"key":"...", "value":"...", "source":"user_pref|env_limit|domain_fact|artifact_ref"}}],
  "role_update": "короткое обновление роли или пустая строка"
}}

Правила:
- next_actions заполняй ТОЛЬКО если без дополнительных инструментов цель НЕ достигнуть.
- new_plan заполняй, если текущий план надо корректировать.
- mismatches пиши кратко и по делу.

ЦЕЛЬ (исходный запрос пользователя):
{original_user_query}

ТЕКУЩИЙ ПЛАН:
{json.dumps(plan_now, ensure_ascii=False)}

ФАКТИЧЕСКИЕ ДЕЙСТВИЯ (последние):
{json.dumps(trace_tail, ensure_ascii=False)}

ПОСЛЕДНИЙ РЕЗУЛЬТАТ ИНСТРУМЕНТА:
{last_tool_result}
"""
    return prompt.strip()


# =========================
# Main
# =========================
def main():
    llm, tools_cfg = init_agent()
    memory = ConversationBufferMemory()

    # создаем локальную сессию
    session_id = str(uuid.uuid4())
    state = load_session_state(session_id)
    save_session_state(state)

    # запускаем воркер VM1 (HDFS queue)
    vm1_worker.start()
    log_print("💬 Введите запрос. Напишите 'exit' для выхода. Команда: list_tools")

    try:
        while True:
            user_input = beautiful_input().strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            # ручной вызов инструмента: run ...
            manual = parse_manual_run(user_input)
            if manual:
                method, params = manual
                print(f"[CLI] Отправляю job {method} с params {params}")
                submit_job(method, params)
                continue

            # показать инструменты
            if user_input.lower() == "list_tools":
                print("\n📋 Доступные инструменты:")
                for name, details in tools_cfg.items():
                    print(f" - {name}: {details.get('description', 'Нет описания')}")
                    print(f" Аргументы: {', '.join(details.get('args', []))}")
                    print(f" Host: {details.get('host', 'N/A')}\n")
                continue

            original_user_query = user_input

            # сохраняем в память разговора (langchain)
            memory.chat_memory.add_user_message(original_user_query)
            print("...")

            # обновим цель в session state
            state["goal"] = original_user_query
            save_session_state(state)

            # 1) первый вызов модели
            history = memory.load_memory_variables({}).get("history", "")
            prompt = build_main_prompt(state, original_user_query, history, tools_cfg)

            response = llm.invoke(prompt)
            time.sleep(4)

            console.print(
                Panel(
                    response,
                    style="green",
                    border_style="green",
                    title="ai_BP_helper",
                    title_align="left",
                )
            )
            memory.chat_memory.add_ai_message(response)

            # 2) цикл: tool -> reflection -> (maybe next tools) -> followup -> ... -> final text_response
            max_iterations = 12
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                cmd = _extract_json_obj(response)
                if not isinstance(cmd, dict):
                    # модель вернула не-json — прекращаем без падения
                    break
                if isinstance(cmd, dict) and isinstance(cmd.get("plan"), list):
                    log_print(f"[REASONING] plan={cmd.get('plan')}")

                action = cmd.get("action")
                plan = cmd.get("plan")
                if isinstance(plan, list) and plan:
                    state["plan"] = plan
                    save_session_state(state)

                # если это финальный ответ
                if action == "text_response":
                    txt = cmd.get("text", "")
                    if txt:
                        # можно красиво вывести "человеческий" текст отдельной панелью
                        console.print(
                            Panel(
                                txt,
                                style="green",
                                border_style="green",
                                title="Ответ",
                                title_align="left",
                            )
                        )
                        memory.chat_memory.add_ai_message(txt)
                    break

                # если модель хочет инструменты — выполним через твой multi_tool_handler
                handler_result = multi_tool_handler.handle_llm_response(response, tools_cfg, memory)
                if not handler_result:
                    break

                tool_result_raw = handler_result[0]
                per_call_results = None
                if isinstance(handler_result, tuple) and len(handler_result) > 1 and isinstance(handler_result[1], list):
                    per_call_results = handler_result[1]

                # ВАЖНО: если есть per_call_results — делаем нормальный last_tool_result для followup
                if per_call_results:
                    parts = []
                    for r in per_call_results:
                        parts.append(f"{r['tool_name']}: {_short(r.get('result'), 35600)}")
                    tool_result_short = "\n\n".join(parts)
                else:
                    tool_result_short = _short(tool_result_raw, n=35600)

                # trace: записываем отдельный result_ref для каждого вызова
                if per_call_results:
                    for r in per_call_results:
                        tn = r.get("tool_name") or "unknown_tool"
                        pr = r.get("params", {}) or {}
                        rr = _short(r.get("result"), 35800)
                        append_trace(state, tn, pr, rr)
                        log_print(f"[TRACE] +tool={tn} params={pr}")
                else:
                    # fallback (если по какой-то причине нет per_call_results)
                    cmd = _extract_json_obj(response) or {}
                    if action == "tool_call":
                        tn = cmd.get("tool_name") or "unknown_tool"
                        pr = cmd.get("params", {}) or {}
                        append_trace(state, tn, pr, tool_result_short)
                        log_print(f"[TRACE] +tool={tn} params={pr}")
                    elif action == "multi_tool_call":
                        calls = cmd.get("calls", []) or []
                        for c in calls:
                            tn = (c.get("tool_name") or "unknown_tool")
                            pr = (c.get("params", {}) or {})
                            append_trace(state, tn, pr, tool_result_short)
                            log_print(f"[TRACE] +tool={tn} params={pr}")

                save_session_state(state)

                # добавляем в историю (модель будет видеть РЕАЛЬНЫЕ результаты, а не "в процессе")
                memory.chat_memory.add_ai_message(f"[TOOL_RESULT]\n{tool_result_short}")


                # 3) reflection
                refl_prompt = build_reflection_prompt(state, original_user_query, tool_result_short)
                refl_raw = llm.invoke(refl_prompt)
                time.sleep(5)
                refl = _extract_json_obj(refl_raw) or {}
                log_print(f"[REFLECTION] raw={_short(refl_raw, 35400)}")
                if isinstance(refl, dict):
                    log_print(f"[REFLECTION] ok={refl.get('reflection_ok')} mismatches={refl.get('mismatches')}")
                    log_print(f"[REFLECTION] new_plan={refl.get('new_plan')}")
                    log_print(f"[REFLECTION] next_actions={refl.get('next_actions')}")

                # применяем reflection: новый план, роль, память
                if isinstance(refl, dict):
                    new_plan = refl.get("new_plan")
                    if isinstance(new_plan, list) and new_plan:
                        state["plan"] = new_plan

                    role_update = (refl.get("role_update") or "").strip()
                    if role_update:
                        prev = (state.get("role_prompt") or "").strip()
                        state["role_prompt"] = (prev + "\n" + role_update).strip() if prev else role_update
                        log_print(f"[ROLE] UPDATED:\n{role_update}")

                    mem_items = refl.get("memory_write") or []
                    if isinstance(mem_items, list) and mem_items:
                        append_global_memory(mem_items, session_id=session_id)
                        log_print(f"[MEMORY] wrote {len(mem_items)} items to {_GLOBAL_MEM_PATH}")
                    save_session_state(state)

                # если reflection предлагает дополнительные next_actions
                next_actions = refl.get("next_actions") if isinstance(refl, dict) else None
                if isinstance(next_actions, list) and next_actions:
                    extra_res, _ = multi_tool_handler.execute_multi_tool_call(next_actions, tools_cfg)
                    extra_res_short = _short(extra_res, n=35600)
                    memory.chat_memory.add_ai_message(f"[TOOL_RESULT_REFLECTION]\n{extra_res_short}")

                    # и тоже в trace
                    for c in next_actions:
                        tn = (c.get("tool_name") or "unknown_tool")
                        pr = (c.get("params", {}) or {})
                        append_trace(state, tn, pr, extra_res_short)
                        log_print(f"[TRACE] +tool={tn} params={pr}")
                    save_session_state(state)

                    # обновим tool_result_short, чтобы продолжение учитывало уже и это
                    tool_result_short = tool_result_short + "\n\n[REFLECTION_EXTRA_TOOLS]\n" + extra_res_short

                # 4) followup — просим модель продолжить (либо еще инструменты, либо финальный ответ)
                history = memory.load_memory_variables({}).get("history", "")
                followup_prompt = build_followup_prompt(
                    state=state,
                    original_user_query=original_user_query,
                    history=history,
                    tools_cfg=tools_cfg,
                    last_tool_result=tool_result_short,
                )
                response = llm.invoke(followup_prompt)

                preview = response if len(response) <= 150 else response[:150] + "… (сокращено)"
                console.print(
                    Panel(
                        preview,
                        style="green",
                        border_style="green",
                        title=f"ai_BP_helper (итерация {iteration})",
                        title_align="left",
                    )
                )
                memory.chat_memory.add_ai_message(response)

            # конец одной пользовательской итерации

    except Exception as e:
        print(f"❌ Ошибка в основном цикле: {e}")

    finally:
        vm1_worker.stop()


if __name__ == "__main__":
    main()