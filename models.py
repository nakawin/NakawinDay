from dataclasses import dataclass
from enum import Enum


class Difficulty(int, Enum):
    ZERO = 0
    ONE = 1
    TWO = 2


DIFFICULTY_COINS = {0: 1, 1: 2, 2: 3}
DIFFICULTY_EMOJI = {0: "🕯", 1: "🔥", 2: "🔥🔥"}


class TaskType(str, Enum):
    ONEOFF = "oneoff"
    RECURRING = "recurring"


class Status(str, Enum):
    ACTIVE = "active"
    DONE = "done"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: int
    title: str
    category_id: int | None
    category_name: str | None
    difficulty: int
    type: str
    deadline: str | None
    period_days: int | None
    period_start: str | None
    status: str
    completed_count: int
    created_at: str
    completed_at: str | None


@dataclass
class Completion:
    id: int
    task_id: int
    task_title: str
    completed_at: str
    coins: int
