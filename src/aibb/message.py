from typing import Optional

from aibb.base import Houseguest, Message, CompResults

__all__ = [
    "EventMessage",
    "CompResultsMessage",
    "SpokenMessage",
]

class EventMessage(Message):
    subject: Optional[Houseguest]  # "None" means it's for the whole house


class CompResultsMessage(EventMessage):
    subject: Optional[Houseguest] = None
    results: CompResults


class SpokenMessage(Message):
    speaker: Houseguest