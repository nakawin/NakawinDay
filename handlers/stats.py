from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import db
import keyboards as kb
from handlers.start import guard
from handlers.tasks import task_card_text
from handlers.categories import _sort_key

router = Router()


@router.message(Command("list"))
async def cmd_list(message: Message):
    if not await guard(message):
        return
    tasks = await db.list_active_tasks()
    if not tasks:
        await message.answer("Активных задач нет 🌿")
        return
    tasks.sort(key=_sort_key)
    for t in tasks:
        await message.answer(task_card_text(t),
                             reply_markup=kb.kb_task_card(t["id"]))


@router.message(Command("coins"))
async def cmd_coins(message: Message):
    if not await guard(message):
        return
    await db.ensure_user(message.from_user.id)
    balance = await db.get_balance(message.from_user.id)
    recents = await db.recent_completions(20)
    lines = [f"<b>Баланс:</b> {balance} 🪙", ""]
    if not recents:
        lines.append("Пока нет начислений.")
    else:
        lines.append("<b>Последние начисления:</b>")
        for r in recents:
            dt = r["completed_at"][:10]
            lines.append(f"• {dt} — {r['title']} — +{r['coins']} 🪙")
    await message.answer("\n".join(lines))
