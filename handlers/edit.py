import logging
from datetime import datetime, date, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import db
import keyboards as kb
from config import OWNER_ID
from handlers.start import guard
from handlers.tasks import task_card_text

router = Router()
log = logging.getLogger(__name__)


class EditTask(StatesGroup):
    waiting_title = State()
    waiting_deadline = State()
    waiting_period = State()


@router.message(Command("edit"))
async def cmd_edit(message: Message):
    if not await guard(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /edit <id>")
        return
    task_id = int(parts[1].strip())
    task = await db.get_task_with_category(task_id)
    if not task:
        await message.answer("Задача не найдена.")
        return
    await message.answer(
        "Что изменить?\n\n" + task_card_text(task),
        reply_markup=kb.kb_edit_menu(task_id),
    )


@router.callback_query(F.data.startswith("editf:"))
async def cb_editf(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    _, field, tid = cb.data.split(":")
    task_id = int(tid)
    task = await db.get_task_with_category(task_id)
    if not task:
        await cb.message.answer("Задача не найдена.")
        await cb.answer()
        return
    if field == "cancel":
        await cb.message.edit_text("Редактирование отменено.")
        await cb.answer()
        return
    if field == "title":
        await state.set_state(EditTask.waiting_title)
        await state.update_data(task_id=task_id)
        await cb.message.edit_text("Введите новое название:")
    elif field == "category":
        cats = await db.list_categories()
        await cb.message.edit_text("Выберите новую категорию:",
                                   reply_markup=kb.kb_edit_categories(cats, task_id))
    elif field == "difficulty":
        await cb.message.edit_text("Выберите сложность:",
                                   reply_markup=kb.kb_edit_difficulty(task_id))
    elif field == "period":
        if task["type"] == "oneoff":
            await state.set_state(EditTask.waiting_deadline)
            await state.update_data(task_id=task_id)
            await cb.message.edit_text("Введите новый дедлайн (ДД.ММ.ГГГГ) или «-» для бессрочно:")
        else:
            await state.set_state(EditTask.waiting_period)
            await state.update_data(task_id=task_id)
            await cb.message.edit_text("Введите новый период в днях (1..14):")
    await cb.answer()


@router.callback_query(F.data.startswith("edcat:"))
async def cb_edcat(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    _, tid, cid = cb.data.split(":")
    task_id = int(tid)
    cat_id = None if cid == "0" else int(cid)
    await db.update_task(task_id, category_id=cat_id)
    await cb.message.edit_text("Категория обновлена.")
    await cb.answer()


@router.callback_query(F.data.startswith("eddiff:"))
async def cb_eddiff(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    _, tid, diff = cb.data.split(":")
    await db.update_task(int(tid), difficulty=int(diff))
    await cb.message.edit_text("Сложность обновлена.")
    await cb.answer()


@router.message(EditTask.waiting_title, F.text)
async def edit_title(message: Message, state: FSMContext):
    if not await guard(message):
        return
    data = await state.get_data()
    task_id = data["task_id"]
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Пустое название недопустимо.")
        return
    dup = await db.find_active_by_title(new_title, exclude_id=task_id)
    if dup:
        await message.answer("Такое название уже используется. Введите другое:")
        return
    await db.update_task(task_id, title=new_title)
    await state.clear()
    await message.answer(f"Название обновлено: «{new_title}»")


@router.message(EditTask.waiting_deadline, F.text)
async def edit_deadline(message: Message, state: FSMContext):
    if not await guard(message):
        return
    data = await state.get_data()
    task_id = data["task_id"]
    raw = message.text.strip()
    if raw == "-":
        await db.update_task(task_id, deadline=None, status="active")
    else:
        try:
            d = datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("Формат: ДД.ММ.ГГГГ или «-»")
            return
        status = "expired" if d < date.today() else "active"
        await db.update_task(task_id, deadline=d.isoformat(), status=status)
    await state.clear()
    await message.answer("Дедлайн обновлён.")


@router.message(EditTask.waiting_period, F.text)
async def edit_period(message: Message, state: FSMContext):
    if not await guard(message):
        return
    try:
        pd = int(message.text.strip())
        if not 1 <= pd <= 14:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 14.")
        return
    data = await state.get_data()
    task_id = data["task_id"]
    await db.update_task(task_id, period_days=pd)
    await state.clear()
    await message.answer(f"Период обновлён: {pd} дн.")


@router.message(Command("delete"))
async def cmd_delete(message: Message):
    if not await guard(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /delete <id>")
        return
    task_id = int(parts[1].strip())
    task = await db.get_task(task_id)
    if not task:
        await message.answer("Задача не найдена.")
        return
    await message.answer(
        f"Удалить задачу «{task['title']}» (ID {task_id})?\n"
        "Монеты за выполненные не откатываются.",
        reply_markup=kb.kb_confirm_delete_task(task_id),
                                 )
