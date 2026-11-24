from aiogram import Router
from . import start, tasks, categories, done, edit, stats


def setup_handlers(dp):
    r = Router()
    r.include_router(start.router)
    r.include_router(tasks.router)
    r.include_router(categories.router)
    r.include_router(done.router)
    r.include_router(edit.router)
    r.include_router(stats.router)
    dp.include_router(r)
