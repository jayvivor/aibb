from aibb.base import Move
from aibb.houseguest import DefaultHouseguest

__all__ = [
    "SpeakMove",
    "WhisperMove",
]

class SpeakMove(Move):
    actor: DefaultHouseguest
    content: str

    def describe(self):
        return f"{self.actor.name}: {self.content}"


class WhisperMove(Move):
    actor: DefaultHouseguest
    content: str
    target: DefaultHouseguest

    def describe(self):
        return f"{self.actor.name} (whispered to {self.target.name}): {self.content}"