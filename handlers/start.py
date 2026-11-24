from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

import db
from config import OWNER_ID

router = Router()


async def guard(message: Message) -> bool:
    if message.from_user.id != OWNER_ID:
        await message.answer("Извините, бот личный.")
        return False
    return True


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not await guard(message):
        return
    await db.ensure_user(message.from_user.id)
    text = (
        "👋 Привет! Я твой личный трекер задач.\n\n"
        "<b>Команды:</b>\n"
        "/new — новая задача\n"
        "/list — список активных\n"
        "/coins — монеты\n"
        "/categories — категории\n"
        "/addcategory &lt;имя&gt; — добавить категорию\n"
        "/delcategory &lt;имя&gt; — удалить категорию\n"
        "/category &lt;текст&gt; — задачи категории\n"
        "/done &lt;id&gt; — выполнить задачу\n"
        "/edit &lt;id&gt; — редактировать\n"
        "/delete &lt;id&gt; — удалить\n"
        "/help — полная справка"
    )
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not await guard(message):
        return
    text = (
        "<b>Полная справка</b>\n\n"
        "Создание: /new — пошаговый диалог. Название должно быть уникальным "
        "среди активных задач.\n\n"
        "Выполнение:\n"
        "• кнопка «✅ Выполнено» под карточкой,\n"
        "• /done &lt;id&gt;,\n"
        "• текст «&lt;название&gt; выполнено».\n"
        "Монеты: 0 огней = 1, 1 = 2, 2 = 3.\n\n"
        "Отмена выполнения: кнопка «↩️ Отменить» в сообщении о выполнении.\n\n"
        "Неактуальность: текст «&lt;название&gt; неактуально» — задача "
        "отменяется без начисления монет.\n\n"
        "Повторяющиеся задачи: выполнять можно в любой день периода; "
        "для периода 7 дней следующий начинается с ближайшего понедельника, "
        "для остальных — сдвиг на period_days. Пропуск без штрафа.\n\n"
        "Просроченные одноразовые задачи помечаются ⚠️ и показываются первыми.\n\n"
        "Категории: /categories, /addcategory, /delcategory, /category.\n\n"
        "Напоминания: 11:00 — дайджест; каждые 3 часа (09–23) — случайная задача."
    )
    await message.answer(text)
