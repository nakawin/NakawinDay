import logging
import random
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

import db
import keyboards as kb
from config import OWNER_ID, TZ
from handlers.tasks import task_card_text
from handlers.categories import _sort_key
from models import DIFFICULTY_EMOJI

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone=TZ)


async def _send(bot: Bot, text: str, **kwargs):
    try:
        await bot.send_message(OWNER_ID, text, **kwargs)
    except Exception as e:
        log.exception("Ошибка отправки: %s", e)


# ----- Daily digest 11:00 -----
async def daily_digest(bot: Bot):
    try:
        await db.mark_expired(date.today().isoformat())
        tasks = await db.list_active_tasks()
        today = date.today()
        expired = [t for t in tasks if t["status"] == "expired"]
        soon_oneoff = []
        for t in tasks:
            if t["status"] != "active" or t["type"] != "oneoff":
                continue
            if not t["deadline"]:
                continue
            d = date.fromisoformat(t["deadline"])
            if today <= d <= today + timedelta(days=7):
                soon_oneoff.append(t)
        soon_recur = []
        for t in tasks:
            if t["status"] != "active" or t["type"] != "recurring":
                continue
            if not t["period_start"] or not t["period_days"]:
                continue
            end = date.fromisoformat(t["period_start"]) + timedelta(days=t["period_days"] - 1)
            if today <= end <= today + timedelta(days=7):
                soon_recur.append(t)

        if not (expired or soon_oneoff or soon_recur):
            await _send(bot, "На сегодня срочных дел нет 🌿")
            return

        lines = ["☀️ <b>Доброе утро!</b>", ""]
        if expired:
            lines.append("⚠️ <b>Просрочено:</b>")
            for t in expired:
                lines.append(f"• {DIFFICULTY_EMOJI[t['difficulty']]} {t['title']} "
                             f"(ID {t['id']}) — дедлайн {t['deadline']}")
            lines.append("")
        if soon_oneoff:
            lines.append("<b>Дедлайн в ближайшие 7 дней:</b>")
            for t in soon_oneoff:
                lines.append(f"• {DIFFICULTY_EMOJI[t['difficulty']]} {t['title']} "
                             f"(ID {t['id']}) — до {t['deadline']}")
            lines.append("")
        if soon_recur:
            lines.append("<b>Скоро конец периода:</b>")
            for t in soon_recur:
                end = date.fromisoformat(t["period_start"]) + timedelta(days=t["period_days"] - 1)
                lines.append(f"• {DIFFICULTY_EMOJI[t['difficulty']]} {t['title']} "
                             f"(ID {t['id']}) — до {end.isoformat()}")
        await _send(bot, "\n".join(lines))
    except Exception:
        log.exception("daily_digest error")


# ----- Every 3 hours reminder 09..23 -----
async def random_reminder(bot: Bot):
    try:
        await db.mark_expired(date.today().isoformat())
        tasks = await db.list_active_tasks()
        # только active/expired с реально доступным статусом
        candidates = [t for t in tasks if t["status"] in ("active", "expired")]
        if not candidates:
            return
        t = random.choice(candidates)
        text = "⏰ <b>Напоминание</b>\n\n" + task_card_text(t)
        await _send(bot, text, reply_markup=kb.kb_task_card(t["id"]))
    except Exception:
        log.exception("random_reminder error")


def start_scheduler(bot: Bot):
    scheduler.add_job(
        daily_digest, CronTrigger(hour=11, minute=0, timezone=TZ),
        args=[bot], id="daily_digest",
    )
    # Каждые 3 часа, в 09, 12, 15, 18, 21 (09:00...21:00 → последний 21:00; 
    # 00:00 не нужен; добавим отдельно 23:00? ТЗ: «с 09:00 до 23:00» — часы 09,12,15,18,21,23? 
    # Простейшая трактовка: cron на 9-23 с шагом 3, т.е. 9,12,15,18,21.
    scheduler.add_job(
        random_reminder,
        CronTrigger(hour="9,12,15,18,21", minute=0, timezone=TZ),
        args=[bot], id="random_reminder",
    )
    scheduler.start()
