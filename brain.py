import json
import os
from typing import Optional

from openai import AsyncOpenAI

_client: Optional[AsyncOpenAI] = None

PLAN_SYSTEM_PROMPT = (
    "Ты — персональный AI-планировщик жизни и учёбы. "
    "Твоя задача — помогать пользователю строить реалистичные планы "
    "на день и неделю. Отвечай по делу, кратко, без лишней воды. "
    "План должен быть выполнимым: время, задачи и длительности должны "
    "умещаться в реальный день."
)

RESPONSE_FORMAT = {"type": "json_object"}


def _client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY", ""),
        )
    return _client


def _model() -> str:
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def _tasks_hint() -> str:
    return (
        'Каждый элемент массива tasks: {"title": "краткое название", '
        '"subject": "раздел или предмет", "time": "ЧЧ:ММ", "duration": "ЧЧ:ММ"}.'
    )


def _parse_tasks(completion) -> list:
    content = completion.choices[0].message.content or '{"tasks": []}'
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    tasks = data.get("tasks") or []
    return [t for t in tasks if isinstance(t, dict) and t.get("title")]


async def generate_plan(user_context: str, date_str: str) -> list:
    """Составляет новый план на день. Возвращает список задач."""
    completion = await _client().chat.completions.create(
        model=_model(),
        response_format=RESPONSE_FORMAT,
        temperature=0.4,
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Сегодняшняя дата: {date_str}. "
                    f"Контекст пользователя: {user_context}. "
                    "Составь план на сегодняшний день. "
                    'Ответь одним JSON-объектом формата {"tasks": [...]}. '
                    + _tasks_hint()
                ),
            },
        ],
    )
    return _parse_tasks(completion)


async def update_plan(user_context: str, current_tasks: list, change_request: str) -> list:
    """Пересчитывает план с учётом правки от пользователя. Возвращает задачи."""
    completion = await _client().chat.completions.create(
        model=_model(),
        response_format=RESPONSE_FORMAT,
        temperature=0.4,
        messages=[
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Контекст пользователя: {user_context}. "
                    f"Текущий план: {json.dumps({'tasks': current_tasks}, ensure_ascii=False)}. "
                    f"Пользователь хочет внести изменение в план: «{change_request}». "
                    "Пересчитай план с учётом этого изменения. "
                    'Ответь одним JSON-объектом формата {"tasks": [...]}. '
                    + _tasks_hint()
                ),
            },
        ],
    )
    return _parse_tasks(completion)
