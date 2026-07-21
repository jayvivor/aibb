from typing import ClassVar

from aibb.base import MoveResponse
from aibb.houseguest import DefaultHouseguest
from aibb.move import (
    DefaultMove,
    SpeakMove,
    WhisperMove,
    StartConversationMove,
    JoinConversationMove,
    ExitConversationMove,
    ChangeRoomMove,
    InteractMove,
    EvictionVoteMove,
    SchemeMove,
    NominationMove,
)



class DefaultMoveResponse(MoveResponse[DefaultHouseguest, DefaultMove]):
    
    valid_move_types: ClassVar[list[type[DefaultMove]]]

    def describe(self):
            raise NotImplementedError


OPEN_MOVES: list[type[DefaultMove]] = [
    SpeakMove, 
    WhisperMove, 
    StartConversationMove,
    JoinConversationMove,
    ExitConversationMove,
    ChangeRoomMove,
    InteractMove,
]

class OpenMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = OPEN_MOVES
    
    # TODO: This is a placeholder; should actually discern move type etc.
    def get_move(self):
        return SpeakMove(
            actor=self.actor,
            content="Howdy, World!",
        )


class EvictionVoteMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [EvictionVoteMove]

    # TODO: This is a placeholder; should actually discern move type etc.
    def get_move(self) -> EvictionVoteMove:
        ...
    

class SchemeMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [SchemeMove]

    # TODO: This is a placeholder; should actually discern move type etc.
    def get_move(self) -> SchemeMove:
        ...
    

class NominationMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [NominationMove]

    nominee_names: list[str]

    # TODO: This is a placeholder; should actually discern move type etc.
    def get_move(self) -> NominationMove:
        ...
        # return NominationMove(
        #     actor=self.actor,
        #     nominees=
        # )