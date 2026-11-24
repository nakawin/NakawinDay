from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import db
import keyboards as kb
from config import OWNER_ID
from handlers.start import guard
from handlers.tasks import task_card_text

router = Router()


@router.message(Command("categories"))
async def cmd_categories(message: Message):
    if not await guard(message):
        return
    cats = await db.list_categories()
    if not cats:
        await message.answer(
            "Категорий пока нет. Добавьте: /addcategory <имя>"
        )
        return
    tasks = await db.list_active_tasks()
    counts = {}
    for t in tasks:
        if t["category_id"]:
            counts[t["category_id"]] = counts.get(t["category_id"], 0) + 1
    lines = ["<b>Категории:</b>"]
    for cid, name in cats:
        lines.append(f"• #{cid} {name} — активных: {counts.get(cid, 0)}")
    await message.answer("\n".join(lines))


@router.message(Command("addcategory"))
async def cmd_addcategory(message: Message):
    if not await guard(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /addcategory <имя>")
        return
    name = parts[1].strip()
    cid = await db.add_category(name)
    if cid is None:
        await message.answer(f"Категория «{name}» уже существует.")
        return
    await message.answer(f"Категория «{name}» создана (ID {cid}).")


@router.message(Command("delcategory"))
async def cmd_delcategory(message: Message):
    if not await guard(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /delcategory <имя>")
        return
    name = parts[1].strip()
    cat = await db.find_category(name)
    if not cat:
        await message.answer(f"Категория «{name}» не найдена.")
        return
    cid, cname = cat
    await message.answer(
        f"Удалить категорию «{cname}»? Задачи будут перенесены в «Без категории».",
        reply_markup=kb.kb_confirm_delete_cat(cid),
    )


@router.callback_query(F.data.startswith("delcat_yes:"))
async def cb_delcat_yes(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    cid = int(cb.data.split(":")[1])
    await db.delete_category(cid)
    await cb.message.edit_text("Категория удалена, задачи перенесены в «Без категории».")
    await cb.answer()


@router.callback_query(F.data.startswith("delcat_no:"))
async def cb_delcat_no(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    await cb.message.edit_text("Удаление отменено.")
    await cb.answer()


@router.message(Command("category"))
async def cmd_category(message: Message):
    if not await guard(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /category <текст>")
        return
    needle = parts[1].strip().lower()
    cats = await db.list_categories()
    matched_ids = {cid for cid, name in cats if needle in name.lower()}
    if not matched_ids:
        await message.answer("Категории по запросу не найдено.")
        return
    tasks = await db.list_active_tasks()
    filtered = [t for t in tasks if t["category_id"] in matched_ids]
    if not filtered:
        await message.answer("В этих категориях нет активных задач.")
        return
    filtered.sort(key=_sort_key)
    for t in filtered:
        await message.answer(task_card_text(t),
                             reply_markup=kb.kb_task_card(t["id"]))


def _sort_key(t):
    from datetime import date
    expired_flag = 0 if t["status"] == "expired" else 1
    if t["type"] == "oneoff":
        d = t["deadline"] or "9999-12-31"
    else:
        d = t["period_start"] or "9999-12-31"
    return (expired_flag, d, -t["difficulty"])
