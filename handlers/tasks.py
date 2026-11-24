import logging
from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
import keyboards as kb
from config import OWNER_ID
from handlers.start import guard
from models import DIFFICULTY_EMOJI

router = Router()
log = logging.getLogger(__name__)


class NewTask(StatesGroup):
    title = State()
    category = State()
    difficulty = State()
    ttype = State()
    deadline = State()
    deadline_custom = State()
    period = State()
    period_custom = State()


def esc(s: str | None) -> str:
    if s is None:
        return ""
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def task_card_text(t: dict) -> str:
    diff = DIFFICULTY_EMOJI.get(t["difficulty"], "")
    cat = t["category_name"] or "Без категории"
    head = f"<b>{esc(t['title'])}</b> (ID {t['id']})"
    body = [head, f"Категория: {esc(cat)}", f"Сложность: {diff}"]
    if t["type"] == "oneoff":
        body.append(f"Тип: одноразовая")
        body.append(f"Дедлайн: {t['deadline'] or 'бессрочно'}")
    else:
        body.append(f"Тип: повторяющаяся, каждые {t['period_days']} дн.")
        body.append(f"Начало периода: {t['period_start']}")
        body.append(f"Выполнено раз: {t['completed_count']}")
    if t["status"] == "expired":
        body.append("⚠️ <b><i>ПРОСРОЧЕНО</i></b>")
    return "\n".join(body)


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext):
    if not await guard(message):
        return
    await state.set_state(NewTask.title)
    await message.answer(
        "Шаг 1/5. Введите название задачи (текстом).\nОтмена: /cancel"
    )


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not await guard(message):
        return
    await state.clear()
    await message.answer("Создание отменено.")


# ----- step 1 -----
@router.message(NewTask.title, F.text)
async def step_title(message: Message, state: FSMContext):
    if not await guard(message):
        return
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Введите ещё раз.")
        return
    if len(title) > 200:
        await message.answer("Слишком длинное название (макс. 200).")
        return
    dup = await db.find_active_by_title(title)
    if dup:
        await message.answer(
            f"Задача «{esc(title)}» уже существует и активна. "
            "Введите другое название."
        )
        return
    await state.update_data(title=title)
    await state.set_state(NewTask.category)
    cats = await db.list_categories()
    await message.answer("Шаг 2/5. Выберите категорию:",
                         reply_markup=kb.kb_categories(cats))


@router.callback_query(NewTask.category, F.data.startswith("newcat:"))
async def step_category(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    val = cb.data.split(":", 1)[1]
    if val == "none":
        await state.update_data(category_id=None)
    else:
        await state.update_data(category_id=int(val))
    await state.set_state(NewTask.difficulty)
    await cb.message.edit_text("Шаг 3/5. Выберите сложность:",
                               reply_markup=kb.kb_difficulty())
    await cb.answer()


# ----- step 3 -----
@router.callback_query(NewTask.difficulty, F.data.startswith("newdiff:"))
async def step_difficulty(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    diff = int(cb.data.split(":")[1])
    await state.update_data(difficulty=diff)
    await state.set_state(NewTask.ttype)
    await cb.message.edit_text("Шаг 4/5. Тип задачи:",
                               reply_markup=kb.kb_type())
    await cb.answer()


@router.callback_query(NewTask.ttype, F.data.startswith("newtype:"))
async def step_type(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    ttype = cb.data.split(":")[1]
    await state.update_data(ttype=ttype)
    if ttype == "oneoff":
        await state.set_state(NewTask.deadline)
        await cb.message.edit_text("Шаг 5/5. Дедлайн:",
                                   reply_markup=kb.kb_deadline())
    else:
        await state.set_state(NewTask.period)
        await cb.message.edit_text(
            "Шаг 5/5. Период повторения (дней, 1..14):",
            reply_markup=kb.kb_period(),
        )
    await cb.answer()


# ----- deadline presets -----
@router.callback_query(NewTask.deadline, F.data.startswith("newdl:"))
async def step_deadline(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    val = cb.data.split(":")[1]
    if val == "custom":
        await state.set_state(NewTask.deadline_custom)
        await cb.message.edit_text("Введите дату в формате ДД.ММ.ГГГГ:")
        await cb.answer()
        return
    data = await state.get_data()
    deadline = None
    if val != "none":
        days = int(val)
        deadline = (date.today() + timedelta(days=days)).isoformat()
    await _finish_task(cb.message, state, data, deadline=deadline)
    await cb.answer()


@router.message(NewTask.deadline_custom, F.text)
async def step_deadline_custom(message: Message, state: FSMContext):
    if not await guard(message):
        return
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Введите ДД.ММ.ГГГГ:")
        return
    data = await state.get_data()
    await _finish_task(message, state, data, deadline=d.isoformat())


# ----- period presets -----
@router.callback_query(NewTask.period, F.data.startswith("newpd:"))
async def step_period(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    pd = int(cb.data.split(":")[1])
    if not 1 <= pd <= 14:
        await cb.answer("Нужно 1..14", show_alert=True)
        return
    data = await state.get_data()
    await _finish_task(cb.message, state, data, period_days=pd)
    await cb.answer()


# ----- finalize -----
async def _finish_task(message: Message, state: FSMContext, data: dict,
                      deadline: str | None = None,
                      period_days: int | None = None):
    title = data["title"]
    cat_id = data.get("category_id")
    diff = data["difficulty"]
    ttype = data["ttype"]
    period_start = None
    if ttype == "recurring":
        period_start = date.today().isoformat()
    task_id = await db.create_task(
        title=title, category_id=cat_id, difficulty=diff, ttype=ttype,
        deadline=deadline, period_days=period_days,
        period_start=period_start,
    )
    await state.clear()
    t = await db.get_task_with_category(task_id)
    text = "Задача создана!\n\n" + task_card_text(t)
    await message.answer(text, reply_markup=kb.kb_task_card(task_id))


# ----- task card callback handler (для всех действий) -----
@router.callback_query(F.data.startswith("done:"))
async def cb_done(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    from handlers.done import perform_task_completion
    task_id = int(cb.data.split(":")[1])
    await perform_task_completion(cb.message, task_id, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data.startswith("del:"))
async def cb_del(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    task_id = int(cb.data.split(":")[1])
    await cb.message.answer(
        "Удалить задачу? Монеты за выполненные не откатываются.",
        reply_markup=kb.kb_confirm_delete_task(task_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("deltask_yes:"))
async def cb_deltask_yes(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    task_id = int(cb.data.split(":")[1])
    await db.delete_task(task_id)
    await cb.message.edit_text(f"Задача #{task_id} удалена.")
    await cb.answer()


@router.callback_query(F.data.startswith("deltask_no:"))
async def cb_deltask_no(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Бот личный.", show_alert=True)
        return
    await cb.message.edit_text("Удаление отменено.")
    await cb.answer()
