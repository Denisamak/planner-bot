import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from brain import generate_plan, update_plan
from storage import get_user, save_user

load_dotenv()
logging.basicConfig(level=logging.INFO)

WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip()
PORT = int(os.getenv("PORT", "8080"))

app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

QUESTIONS = [
    ("Какие цели и предметы перед собой? "
     "(учёба, работа, спорт, хобби — напиши подробно)", 1),
    ("Во сколько ты обычно встаёшь и ложишься?", 2),
    ("Есть ли сегодня обязательные дела? "
     "(работа, уроки, встречи, поездки)", 3),
]


def format_tasks(tasks: list) -> str:
    if not tasks:
        return "Пока нечего планировать — пришли /plan, когда будешь готов 😊"
    lines = ["🗒 <b>Твой план</b>:"]
    for task in tasks:
        time_ = task.get("time") or "—"
        title = task.get("title") or "Без названия"
        subject = task.get("subject") or "разное"
        lines.append(f"🕐 {time_} — {title} ({subject})")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = get_user(user_id)
    user["awaiting_profile"] = True
    user["profile_text"] = ""
    user["tasks"] = []
    user["question_index"] = 0
    save_user(user_id, user)
    await update.message.reply_text(
        "Привет! 👋 Я — твой AI-планировщик.\n\n"
        "Начнём с опроса. Вопрос 1/3: "
        + QUESTIONS[0][0],
        parse_mode=ParseMode.HTML,
    )


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user["awaiting_profile"]:
        await update.message.reply_text(
            "Сначала пройди опрос профиля — просто отвечай на мои вопросы 😊",
            parse_mode=ParseMode.HTML,
        )
        return
    if not user["profile_text"].strip():
        await update.message.reply_text(
            "Профиль пока пустой — пройди опрос через /start 😉",
            parse_mode=ParseMode.HTML,
        )
        return
    await update.message.reply_text("Составляю план… 🤔")
    tasks = await generate_plan(user["profile_text"], datetime.now().strftime("%Y-%m-%d"))
    user["tasks"] = tasks
    save_user(user_id, user)
    await update.message.reply_text(format_tasks(tasks), parse_mode=ParseMode.HTML)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = get_user(user_id)
    text = (update.message.text or "").strip()
    if user["awaiting_profile"]:
        user["profile_text"] = (user["profile_text"] + " " + text).strip()
        user["question_index"] = user.get("question_index", 0) + 1
        index = user["question_index"]
        if index < len(QUESTIONS):
            await update.message.reply_text(
                f"Хорошо! Вопрос {index + 1}/{len(QUESTIONS)}: " + QUESTIONS[index][0],
                parse_mode=ParseMode.HTML,
            )
        else:
            user["awaiting_profile"] = False
            await update.message.reply_text(
                "Готово! 🎉 Твой профиль собран. Напиши /plan — и я составлю первый план 😊",
                parse_mode=ParseMode.HTML,
            )
        save_user(user_id, user)
        return
    if not user["tasks"]:
        await update.message.reply_text(
            "Пока нет плана — пришли /plan, чтобы я его составил 📋",
            parse_mode=ParseMode.HTML,
        )
        return
    await update.message.reply_text("Пересчитываю план с учётом твоего запроса… 🔄")
    tasks = await update_plan(user["profile_text"], user["tasks"], text)
    user["tasks"] = tasks
    save_user(user_id, user)
    await update.message.reply_text(format_tasks(tasks), parse_mode=ParseMode.HTML)


app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("plan", plan_cmd))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))


if __name__ == "__main__":
    if WEBHOOK_URL:
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=token,
            webhook_url=f"{WEBHOOK_URL.rstrip('/')}/{token}",
            drop_pending_updates=True,
        )
    else:
        app.run_polling()
