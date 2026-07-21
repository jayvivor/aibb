from abc import ABC, abstractmethod
from typing import get_args

from aibb import core

__all__ = [
    "DummyHouseguest",
]

# FIX: Feel free to rewrite this to match implemented patterns; it's just a guideline.


class DummyResponse(core.DefaultMoveResponse, ABC):
    
    @classmethod
    @abstractmethod
    def get_dummy_move(cls, *args, **kwargs) -> core.DefaultMove:
        ...


# EXAMPLE
type DummyOpenMove = core.SpeakMove | core.ChangeRoomMove # | etc. | etc.
class DummyOpenMoveResponse(core.OpenMoveResponse, DummyResponse):

    @classmethod
    def get_dummy_move(cls, *args, **kwargs) -> DummyOpenMove:
        ...
        # etc.



class DummyHouseguest(core.DefaultHouseguest):

    model_id: str = "N/A"

    # Etc.
    def get_move[DR: DummyResponse](self, prompt, user_message, response_type: type[DR]) -> DR:
        ...
    

