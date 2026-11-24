import logging
import re
from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import db
import keyboards as kb
from config import OWNER_ID
from handlers.start import guard
from handlers.tasks import task_card_text
from models import DIFFICULTY_COINS

router = Router()
log = logging.getLogger(__name__)


# ----- /done <id> -----
@router.message(Command("done"))
async def cmd_done(message: Message):
    if not await guard(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /done <id>")
        return
    task_id = int(parts[1].strip())
    await perform_task_completion(message, task_id, message.from_user.id)


# ----- "выполнено" / "неактуально" текстом -----
@router.message(F.text.regexp(r"(?i)^(.+?)\s+(выполнено|неактуально)$"))
async def text_done_or_cancel(message: Message):
    if not await guard(message):
        return
    text = message.text.strip()
    m = re.match(r"(?i)^(.+?)\s+(выполнено|неактуально)$", text)
    if not m:
        return
    needle = m.group(1).strip()
    action = m.group(2).lower()
    found = await db.search_active_by_partial(needle)
    if not found:
        await message.answer(
            f"Активных задач по запросу «{needle}» не найдено."
        )
        return
    if len(found) > 1:
        action_cb = "pickdone" if action == "выполнено" else "pickcancel"
        await message.answer(
            f"Найдено {len(found)} задач. Выберите нужную:",
            reply_markup=kb.kb_choose_task(found, action_cb),
        )
        return
    task = found[0]
    if action == "выполнено":
        await perform_task_completion(message, task["id"], message.from_user.id)
    else:
        await perform_cancel(message, task["id"])


@router.callback_query(F.data.startswith("pickdone:"))
async def cb_pick_done(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    task_id = int(cb.data.split(":")[1])
    await perform_task_completion(cb.message, task_id, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data.startswith("pickcancel:"))
async def cb_pick_cancel(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    task_id = int(cb.data.split(":")[1])
    await perform_cancel(cb.message, task_id)
    await cb.answer()


async def perform_cancel(message: Message, task_id: int):
    task = await db.get_task(task_id)
    if not task or task["status"] not in ("active", "expired"):
        await message.answer("Задача не найдена или уже неактивна.")
        return
    await db.update_task(task_id, status="cancelled")
    await message.answer(
        f"Задача «{task['title']}» отмечена как неактуальная. "
        "Монеты не начислены."
    )


async def perform_task_completion(message: Message, task_id: int, user_id: int):
    await db.ensure_user(user_id)
    task = await db.get_task(task_id)
    if not task:
        await message.answer(f"Задача #{task_id} не найдена.")
        return
    if task["status"] not in ("active", "expired"):
        await message.answer(
            f"Задача «{task['title']}» уже {task['status']}."
        )
        return
    coins = DIFFICULTY_COINS[task["difficulty"]]

    if task["type"] == "oneoff":
        await db.update_task(
            task_id, status="done",
            completed_at=datetime.utcnow().isoformat(),
        )
    else:
        # recurring
        pd = task["period_days"]
        current_start = date.fromisoformat(task["period_start"])
        if pd == 7:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_start = today + timedelta(days=days_until_monday)
        else:
            next_start = current_start + timedelta(days=pd)
        await db.update_task(
            task_id,
            completed_count=task["completed_count"] + 1,
            period_start=next_start.isoformat(),
        )

    await db.add_completion(task_id, coins)
    await db.add_coins(user_id, coins)
    new_balance = await db.get_balance(user_id)

    await message.answer(
        f"🎉 Задача «{task['title']}» выполнена!\n"
        f"Начислено: <b>+{coins}</b> 🪙\n"
        f"Новый баланс: <b>{new_balance}</b> 🪙",
        reply_markup=kb.kb_undo_completion(task_id),
    )


# ----- undo -----
@router.callback_query(F.data.startswith("undo:"))
async def cb_undo(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    task_id = int(cb.data.split(":")[1])
    user_id = cb.from_user.id
    task = await db.get_task(task_id)
    if not task:
        await cb.message.answer("Задача не найдена.")
        await cb.answer()
        return
    last = await db.get_last_completion(task_id)
    if not last:
        await cb.message.answer("Нет записей о выполнении для отмены.")
        await cb.answer()
        return
    coins = last["coins"]
    await db.delete_completion(last["id"])
    await db.add_coins(user_id, -coins)

    if task["type"] == "oneoff":
        await db.update_task(task_id, status="active", completed_at=None)
    else:
        pd = task["period_days"] or 1
        prev_start = date.fromisoformat(task["period_start"]) - timedelta(days=pd)
        new_count = max(task["completed_count"] - 1, 0)
        await db.update_task(
            task_id,
            completed_count=new_count,
            period_start=prev_start.isoformat(),
        )

    new_balance = await db.get_balance(user_id)
    await cb.message.edit_text(
        f"↩️ Выполнение задачи «{task['title']}» отменено.\n"
        f"Списано: <b>-{coins}</b> 🪙\n"
        f"Баланс: <b>{new_balance}</b> 🪙"
    )
    await cb.answer()
