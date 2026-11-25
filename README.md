# ai_audit_helper
AI-агент для подготовки материалов аудиторских проверок крупных проектов.
Планирует шаги, вызывает инструменты, рефлексирует над результатом,
накапливает знания между сессиями и возвращает структурированный ответ.

**Демо-версия** (этот репозиторий): agent loop, память и локальные инструменты
работают полностью; HDFS и Spark-кластер заменены mock-заглушками.

| Параметр | Значение |
|----------|----------|
| Версия | 0.2 (демо) |
| Python | 3.10 – 3.12 |
| Точка входа | `python cli_w.py` |

## 1. Назначение и аудитория

**Что делает.** Принимает запрос на русском языке, формирует план, вызывает
зарегистрированные инструменты (Python-функции на VM1, PySpark-задачи на VM2),
после каждого вызова запускает reflection-модуль LLM: оценивает, достигнута ли
цель, корректирует план. Завершается финальным `text_response`.

**Для кого.** эксперты отдела аудита информационных технологий.

**Что НЕ делает.** Не заменяет аудитора, не выносит суждений, не работает с
внешними API кроме доступных четез GigaChatAPI. Все данные — из корпоративных реплик (в демо недоступны).

## 2. Ожидаемый результат

При запуске `python cli_w.py` и вводе `list_tools` вы должны увидеть:

```
Доступные инструменты:
 - cur_datetime: Показывает текущую дату и время
 - calculate_numbers: Арифметика над двумя числами.
 - big_projects_data: Выгрузка данных ИТ-проектов из корпоративных реплик
 - goals_replica: Выгрузка целей ответственных из реплики данных.
```

При вводе `run cur_datetime` — JSON с результатом:
```json
{"result": "2026-11-22 14:23:45", "status": "done"}
```

**Наблюдаемые артефакты:**
- `memory/sessions/session_<uuid>.json` — состояние сессии (план, трасса, роль);
- `memory/global_memory.jsonl` — дополняется после reflection;
- панели `ai_audit_helper` / `Ответ` в терминале на каждом шаге агента.

## 3. Quick Start

Минимальные шаги:

```bash
# 1. Клонировать
git clone <repo_url> ai_audit_helper
cd ai_audit_helper

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate          # Linux / macOS / WSL2
# .venv\Scripts\activate            # Windows

# 3. Зависимости
python -m pip install -r requirements.txt

# 4. Переменные окружения
cp .env.example .env
# отредактировать .env — при отсутствии токена используйте DEMO_NO_LLM=1

# 5. Запуск
python cli_w.py
```

**Первая проверка (без токена GigaChatAPI):**

```
>> MASTER: list_tools
>> MASTER: run cur_datetime
>> MASTER: exit
```

**Ожидаемо:** список из 4 инструментов; JSON с текущим временем;
корректный выход без трейсбека.

**Если нужен ответ LLM** — задайте `JPY_API_TOKEN` в `.env` и запустите
`python cli_w.py`, затем введите запрос, например, `посчитай 5 + 3`.

## 4. Окружение и зависимости

### Поддерживаемое окружение

| Компонент | Требование |
|-----------|-----------|
| Python | 3.10 – 3.12 |
| ОС | Linux / macOS / WSL2 (Windows — только через WSL2) |
| Терминал | любой с поддержкой UTF-8 (для rich-панелей) |

### Зависимости
`requirements.txt`:
```txt
langchain>=0.1.0,<0.3           # ConversationBufferMemory
langchain-core>=0.1.0,<0.4      # BaseLLM, CallbackManagerForLLMRun
requests>=2.28.0,<3.0           # HTTP-клиент GigaChat API
prompt_toolkit>=3.0.43,<4.0     # ввод с историей
rich>=13.0.0,<15.0              # панели и подсветка
```

### Переменные окружения (`.env`)

| Переменная | Обязательна | Описание |
|-----------|-------------|----------|
| `JPY_API_TOKEN` | для LLM-ответов | Токен GigaChat API. Без него работают `list_tools` и `run <vm1-тул>` |
| `DEMO_NO_LLM` | опционально | `1` — LLM возвращает заглушку без HTTP (для проверки без токена) |
| `NB_USER` | опционально | Имя пользователя HDFS; в демо не используется (mock), дефолт `demo_user` |
| `GC_MODEL_URL` | опционально | Endpoint GigaChat; по умолчанию `http://liveaccess/v1/gc/chat/completions` |
| `LLM_COOLDOWN` | опционально | Пауза между вызовами LLM, сек (по умолчанию 4) |

Полный список — в `.env.example`.

## 5. Структура репозитория

```
ai_audit_helper/
├── cli_w.py                        точка входа (баннер + запуск)
├── audit_helper/
│   ├── __init__.py
│   ├── cli_skillhub_v02.py           Agent Loop, промпты, память
│   ├── gc_call_oaitsh.py             GigaChat API wrapper (LangChain LLM)
│   ├── hdfs_utils.py                 MOCK: no-op HDFS-операции
│   ├── mcp_registry.py               декоратор @mcp.tool (реестр тулов)
│   ├── multi_tool_handler.py         парсинг JSON из LLM + orchestration
│   ├── tools_utils.py                MOCK: читает tools_config.sample.json
│   ├── utils.py                      log_print и вспомогательные функции
│   ├── vm1_local_worker.py           MOCK: не запускается
│   ├── vm1_mcp_logger_client.py      MOCK: локальный submit_job / placeholder
│   └── tools/                       локальные инструменты VM1
│       ├── __init__.py
│       ├── math_tools.py             calculate_numbers
│       └── time_tool.py              cur_datetime
├── scripts/
│   ├── __init__.py
│   └── check_imports.py              smoke-test импортов
├── memory/                          сессионное состояние и образец долгосрочной памяти
├── tools_config.sample.json         шаблон реестра инструментов
├── requirements.txt                 зависимости
├── README.md                        этот файл
├── .env.example                     шаблон переменных окружения
└── .gitignore                       исключает .env, .venv, memory/sessions/*
```

### Что реально включено, а что — mock

| Файл | В полной версии | В демо |
|------|-----------------|--------|
| `hdfs_utils.py` | HDFS `arnsdpsbx` | no-op (не падает) |
| `tools_utils.py` | конфиг из HDFS | читает `tools_config.sample.json` |
| `vm1_mcp_logger_client.py` | очередь заданий в HDFS | локальный вызов vm1-тула или placeholder |
| `vm1_local_worker.py` | сканирует HDFS-requests | печатает warning, не запускается |
| `skillhub_proxy_folder/` | HDFS: requests/statuses/logs/results | **исключён** |
| `oait_skillhub_oncluster/` | VM2: Spark-сервер + PySpark-тулы | **исключён** |

## 6. Данные

### Источники

| Источник | Расположение | Содержимое |
|----------|--------------|------------|
| Крупные проекты | HDFS `arnsdpsbx/.../big_projects_data` | Реплика данных: ФИО, табельный номер, проект, статус, год |
| Цели сотрудников | HDFS `arnsdpsbx/.../goals_replica` | Реплика целей: ФИО, год, ключевые слова, метрики |
| Память агента | `memory/global_memory.jsonl` | Факты, предпочтения, ссылки на артефакты |

### Данные в демо-версии

- **`memory/global_memory.sample.jsonl`** — обезличенные демонстрационные записи
  (ФИО и проекты вымышлены, даты — 2026 г., соответствуют дате формирования
  документа). Формат: `{ts, session_id, key, value, source}`.
- **`tools_config.sample.json`** — реестр из 4 инструментов (2 локальных,
  2 кластерных). Кластерные возвращают placeholder.
- **Реальные реплики данных** — не включены (корпоративная тайна).

## 7. Порядок воспроизведения

### Маршрут проверяющего (5 шагов, ~3 минуты)
| Шаг | Действие | Ожидаемый результат |
|-----|----------|---------------------|
| **1. Понять задачу** | Прочитать  пп.1–2 этого README | Ясно, что делает агент и что вы увидите |
| **2. Проверить окружение** | `python -m scripts.check_imports` | Все критичные модули — `OK`; mock — `WARN` |
| **3. Запустить CLI** | `python cli_w.py` → `list_tools` | Список из 4 инструментов |
| **4. Выполнить тул** | `run cur_datetime` | JSON с текущим временем |
| **5. Проверить память** | Открыть `memory/sessions/session_*.json` | План, роль |

### Маршрут с LLM (нужен `JPY_API_TOKEN`)
```
>> MASTER: посчитай 5 * 3
```
Агент выполнит: `main_prompt` → `tool_call(calculate_numbers)` →
`reflection` → `followup` → `text_response`. **3 вызова LLM** (см. §8).

### Маршрут без LLM
```bash
DEMO_NO_LLM=1 python cli_w.py
```
`_call` вернёт валидный JSON-заглушку `{"action":"text_response",...}` —
agent loop не сломается, панель покажет «Демо-режим: LLM отключён».

## 8. Архитектура агента (кратко)

```
User Query
    │
    ▼
┌──────────────────────────────────┐
│ Agent Loop (до 12 итераций)      │
│  1. Planning    → LLM: план      │
│  2. Tool Call   → submit_job     │
│  3. Reflection  → LLM: самоанализ│
│  4. Memory      → JSONL          │
│  5. Role Update → role_prompt    │
│  6. Followup    → следующий шаг  │
└──────────────────────────────────┘
    │
    ▼
text_response
```

**Ключевое отличие от ReAct:** между tool-вызовом и следующим шагом стоит
**отдельный reflection-вызов LLM** (см. `build_reflection_prompt` в
`cli_skillhub_v02.py`). Он сравнивает цель, план и результат,
предлагает `new_plan` / `next_actions` / `memory_write` / `role_update`.

**Цена:** один запрос = 2–3 LLM-вызова. Для сложной задачи до 12 итераций × 3
= до 36 вызовов. Пауза `LLM_COOLDOWN` (4 сек) настраивается через env.

### Три уровня памяти

| Уровень | Где | Живёт | Что хранит |
|---------|-----|-------|-----------|
| Conversation Buffer | RAM (LangChain) | до выхода | история диалога |
| Session State | `memory/sessions/session_*.json` | между запросами сессии | план, роль |
| Global Memory | `memory/global_memory.jsonl` | между сессиями | устойчивые знания |

## 9. Известные ограничения демо
- **Кластерные тулы** (`big_projects_data`, `goals_replica`) возвращают
  placeholder: `{"status":"demo_placeholder","message":"...требует HDFS и Spark..."}`.
- **`submit_job`** для vm1-тулов выполняет функцию локально; для cluster —
  placeholder. HDFS-очередь не эмулируется.
- **`vm1_local_worker.start()`** печатает warning и не запускает поток.
- **`mcp_registry`** при импорте пытается писать в HDFS — в демо это no-op.
  Если `NB_USER` не задан, используется `demo_user`.
- **`role_prompt`** накапливается (`prev + "\n" + role_update`) без ограничения
  длины — за длинную сессию может съесть контекст.
- **Дедупликация глобальной памяти** не реализована.
- **`time.sleep(4)` / `sleep(5)`** после LLM-вызовов захардкожены; настраиваются
  через `LLM_COOLDOWN` (частично).

## 10. Безопасность и правовой статус

Использование кода — только для целей аудита ОАИТ Сбера. 
Передача третьим лицам не допускается без разрешения владельца проекта.

### Конфиденциальность
- **`.env` не коммитится** (см. `.gitignore`). Токены и пароли отсутствуют
  в истории Git.
- **`memory/sessions/*.json`** — gitignored: содержат трассы вызовов
  конкретных пользователей.
- **`memory/global_memory.sample.jsonl`** — обезличен (ФИО вымышлены).
- **Реальные реплики данных и HDFS-адреса** — не включены в выгрузку;
  `arnsdpsbx` встречается только в docstring/комментариях как ссылка на
  полную версию.
- **`.venv/`, `__pycache__/`, `*.pyc`** — gitignored.

### Проверка основного сценария

```bash
python -m scripts.check_imports
```

Скрипт различает критичные модули (agent loop, реестр, локальные тулы) и
опциональные (API-обёртка, mock-HDFS). При отсутствии `JPY_API_TOKEN`
критичные модули всё равно импортируются.
