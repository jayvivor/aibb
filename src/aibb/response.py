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
    JuryVoteMove,
    SchemeMove,
    NominationMove,
    EffortMove,
    VetoMove,
    ReplacementNomineeMove,
    VetoDrawChoiceMove,
)


# FABLE: The response layer is schema-only for now; every get_move below is
# commented out because the dispatch mechanism is undecided:
#   - selection_id is meant to pick the move type out of valid_move_types, but the
#     responses carry no payload fields for the chosen move (nominee_names below is
#     the one example of the intended shape - LLM output as plain strings).
#   - Resolving those strings into Houseguest/Room objects needs the House
#     registries, which get_move() has no path to.
#   - actor is a full Houseguest model: the LLM cannot emit it, and only
#     DummyHouseguest injects it today; get_chat_response validates the raw JSON
#     with no injection step.
#   - move.py holds a competing (commented-out) design that embeds the whole Move
#     in the response instead.


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
    
    # FABLE: see the module note; the placeholder returned a hardcoded SpeakMove
    # def get_move(self):
    #     return SpeakMove(
    #         actor=self.actor,
    #         content="Howdy, World!",
    #     )


class EffortMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [EffortMove]

    # FABLE: see the module note
    # def get_move(self) -> EffortMove:
    #     ...


class EvictionVoteMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [EvictionVoteMove]

    # FABLE: see the module note
    # def get_move(self) -> EvictionVoteMove:
    #     ...
    

class JuryVoteMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [JuryVoteMove]

    # FABLE: see the module note
    # def get_move(self) -> JuryVoteMove:
    #     ...


class SchemeMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [SchemeMove]

    # FABLE: see the module note
    # def get_move(self) -> SchemeMove:
    #     ...
    

class NominationMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [NominationMove]

    nominee_names: list[str]

    # FABLE: see the module note
    # def get_move(self) -> NominationMove:
    #     ...
    #     # return NominationMove(
    #     #     actor=self.actor,
    #     #     nominees=
    #     # )


class VetoMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [VetoMove]

    # FABLE: see the module note
    # def get_move(self) -> VetoMove:
    #     ...


class ReplacementNomineeMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [ReplacementNomineeMove]

    # FABLE: see the module note
    # def get_move(self) -> ReplacementNomineeMove:
    #     ...


class VetoDrawChoiceMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [VetoDrawChoiceMove]

    # FABLE: see the module note
    # def get_move(self) -> VetoDrawChoiceMove:
    #     ...