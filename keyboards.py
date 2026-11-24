from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_categories(categories: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cid, name in categories:
        kb.button(text=name, callback_data=f"newcat:{cid}")
    kb.button(text="Без категории", callback_data="newcat:none")
    kb.adjust(2)
    return kb.as_markup()


def kb_difficulty() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="0 огней", callback_data="newdiff:0")
    kb.button(text="1 огонь", callback_data="newdiff:1")
    kb.button(text="2 огня", callback_data="newdiff:2")
    kb.adjust(3)
    return kb.as_markup()


def kb_type() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Одноразовая", callback_data="newtype:oneoff")
    kb.button(text="Повторяющаяся", callback_data="newtype:recurring")
    kb.adjust(2)
    return kb.as_markup()


def kb_deadline() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    presets = [
        ("Бессрочно", "none"),
        ("1 день", "1"), ("3 дня", "3"), ("Неделя", "7"),
        ("2 недели", "14"), ("Месяц", "30"),
        ("Ввести дату", "custom"),
    ]
    for label, value in presets:
        kb.button(text=label, callback_data=f"newdl:{value}")
    kb.adjust(3)
    return kb.as_markup()


def kb_period() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in (1, 2, 3, 5, 7, 10, 14):
        kb.button(text=f"{d} дн.", callback_data=f"newpd:{d}")
    kb.adjust(4)
    return kb.as_markup()


def kb_task_card(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполнено", callback_data=f"done:{task_id}")
    kb.button(text="✏️ Редактировать", callback_data=f"edit:{task_id}")
    kb.button(text="🗑 Удалить", callback_data=f"del:{task_id}")
    kb.adjust(1)
    return kb.as_markup()


def kb_undo_completion(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="↩️ Отменить", callback_data=f"undo:{task_id}")
    return kb.as_markup()


def kb_confirm_delete_cat(cat_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data=f"delcat_yes:{cat_id}")
    kb.button(text="Нет", callback_data=f"delcat_no:{cat_id}")
    return kb.as_markup()


def kb_confirm_delete_task(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data=f"deltask_yes:{task_id}")
    kb.button(text="Нет", callback_data=f"deltask_no:{task_id}")
    return kb.as_markup()


def kb_choose_task(tasks: list[dict], action: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in tasks:
        kb.button(
            text=f"#{t['id']} {t['title'][:40]}",
            callback_data=f"{action}:{t['id']}",
        )
    kb.adjust(1)
    return kb.as_markup()


def kb_edit_menu(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Название", callback_data=f"editf:title:{task_id}")
    kb.button(text="Категория", callback_data=f"editf:category:{task_id}")
    kb.button(text="Сложность", callback_data=f"editf:difficulty:{task_id}")
    kb.button(text="Дедлайн/Период", callback_data=f"editf:period:{task_id}")
    kb.button(text="Отмена", callback_data=f"editf:cancel:{task_id}")
    kb.adjust(2)
    return kb.as_markup()


def kb_edit_categories(categories: list[tuple[int, str]],
                       task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cid, name in categories:
        kb.button(text=name, callback_data=f"edcat:{task_id}:{cid}")
    kb.button(text="Без категории", callback_data=f"edcat:{task_id}:0")
    kb.adjust(2)
    return kb.as_markup()


def kb_edit_difficulty(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="0 огней", callback_data=f"eddiff:{task_id}:0")
    kb.button(text="1 огонь", callback_data=f"eddiff:{task_id}:1")
    kb.button(text="2 огня", callback_data=f"eddiff:{task_id}:2")
    kb.adjust(3)
    return kb.as_markup()
