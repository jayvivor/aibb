from abc import ABC, abstractmethod
from typing import Generic, TypeVar, ClassVar, Optional
from pydantic import Field

from aibb.base import Base, Move
from aibb.houseguest import DefaultHouseguest, DefaultMemory
from aibb.interaction import Interactable, Action
from aibb.room import InteractiveRoom
from aibb.week import (
    DefaultPhase,
    OpenPhase,
    CompPhase,
    EvictionVotePhase,
    SleepPhase,
    NominationPhase,
    VetoPhase,
    VetoDrawPhase,
    JuryVotePhase,
    FinalThreeEvictionPhase,
)
from aibb.utils import listed
'''
    NOTE: A Move is an encapsulation of the Houseguest's attempted action, 
    not necessarily a completed action.
'''


__all__ = [
    "DefaultMove",
    "SpeakMove",
    "WhisperMove",
    "Conversation",
    "StartConversationMove",
    "JoinConversationMove",
    "ExitConversationMove",
    "ChangeRoomMove",
    "InteractMove",
    "SchemeMove",
    "CompMove",
    "EffortMove",
    "NominationMove",
    "VetoMove",
    "ReplacementNomineeMove",
    "VetoDrawChoiceMove",
    "VoteMove",
    "EvictionVoteMove",
    "JuryVoteMove",
]



class DefaultMove(Move[DefaultHouseguest], ABC):

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]]
    selection_id: ClassVar[str]
    choice_info: ClassVar[str]

DM = TypeVar("DM", bound=DefaultMove)


# FABLE: Competing response design - response.py builds on base.MoveResponse
# (selection_id + actor + get_move), which is the shape house.py and the
# houseguests actually consume. This one embeds the whole Move (full nested
# Houseguest/Room objects) in the LLM's JSON instead. Commented out until one
# of the two designs is chosen.
# REMOVE: Keep this explanation str and move it to the `response.py` design. Otherwise, chuck it.
# class MoveResponse(Base, ABC, Generic[DM]):
#     explanation: str = Field(description="Your private explanation for the move; nobody else in the game will see this.")
#     move: DM



# OPEN

class OpenMove(DefaultMove):
    VALID_PHASES = [OpenPhase]


class SpeakMove(OpenMove):
    content: str

    selection_id: ClassVar[str] = "Speak"
    choice_info: ClassVar[str] = "Speak at a standard volume. Anyone present in the room will hear you."

    def describe(self):
        return f"{self.actor.name}: {self.content}"


## CONVERSATION

class Conversation(Base):
    active_participants: list[DefaultHouseguest]
    room: InteractiveRoom

    # def add_event(self, event: JoinConvoEvent | ExitConvoEvent | SpokenMessage | WhisperedMessage):
    #     match event:
    #         case JoinConvoEvent():
    #             self.history.join_history.append(event)
    #         case ExitConvoEvent():
    #             self.history.exit_history.append(event)
    #         case SpokenMessage():
    #             self.history.speech_history.append(event)
    #         case WhisperedMessage():
    #             self.history.whisper_history.append(event)

    def describe(self):
        return f"A conversation involving {listed([hg.name for hg in self.active_participants])}."

    def is_active(self) -> bool:
        return len(self.active_participants) > 1


class StartConversationMove(DefaultMove):
    participants: list[DefaultHouseguest]

    selection_id: ClassVar[str] = "Start Conversation"
    choice_info: ClassVar[str] = "Start a conversation between yourself and the named houseguests. This will allow you to whisper to them, even if others are present in the room."

    def describe(self):
        return f"{self.actor.name} starts a conversation between {listed([p.name for p in self.participants])}."


class JoinConversationMove(DefaultMove):
    conversation: Conversation

    selection_id: ClassVar[str] = "Join Ongoing Conversation"
    choice_info: ClassVar[str] = "Join an ongoing conversation between the named houseguests. This will allow you to whisper to them, and hear their whispers in future turns."

    def describe(self):
        return f"{self.actor.name} joins the conversation between {listed([p.name for p in self.conversation.active_participants])}"


class ExitConversationMove(DefaultMove):
    conversation: Conversation

    selection_id: ClassVar[str] = "Leave Conversation"
    choice_info: ClassVar[str] = "Leave your current conversation."

    def describe(self):
        return f"{self.actor.name} leaves the conversation between {listed([p.name for p in self.conversation.active_participants])}"


class WhisperMove(DefaultMove):
    content: str
    allow_join: bool = False

    selection_id: ClassVar[str] = "Whisper"
    choice_info: ClassVar[str] = "Speak in a hushed tone, exclusively to your conversation partners. Others present in the room will know you have whispered, but will not know what was said. If someone attempts to join the conversation this same turn, and `allow_join` is set to False, you will instead say nothing this turn."

    def describe(self):
        return f"{self.actor.name} (whispers): {self.content}"


## ROOM

class ChangeRoomMove(DefaultMove):
    room: InteractiveRoom

    selection_id: ClassVar[str] = "Change Rooms"
    choice_info: ClassVar[str] = "Enter the specified room."

    def describe(self):
        return f"{self.actor.name} moves to the {self.room.name}"


## INTERACTIVES


class InteractMove(DefaultMove):
    interactable: Interactable
    action: Action

    selection_id: ClassVar[str] = "Interact"
    choice_info: ClassVar[str] = "Interact with something in this room."

    def describe(self):
        return self.action.action_description.format(actor=self.actor, object=self.interactable.name)


# FABLE: Part of the commented-out embedded-move MoveResponse design above; the
# live OPEN_MOVES collection is the list in response.py.
# IGNORE: Keep this, I'll implement it later.
# OPEN_MOVES = SpeakMove | WhisperMove | StartConversationMove | JoinConversationMove | ExitConversationMove | ChangeRoomMove |  InteractMove
#
# class OpenTurnResponse(MoveResponse[OPEN_MOVES]):
#     pass


# SCHEME

class SchemeMove(DefaultMove):
    updated_memory: DefaultMemory

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [SleepPhase]
    selection_id: ClassVar[str] = "Scheme"
    choice_info: ClassVar[str] = "Update your scratchpad to include anything worth carrying over to future phases."

    def describe(self):
        return f"{self.actor.name} takes a moment to think."


# COMP

class CompMove(DefaultMove):
    
    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [CompPhase]
    selection_id: ClassVar[str] = "Compete"
    choice_info: ClassVar[str] = "Decide how to approach the competition."


class EffortMove(CompMove):
    effort: int = Field(description="The percentage of effort - from 1 to 100 - that you will put into trying to win.")

    selection_id: ClassVar[str] = "Choose Effort"
    choice_info: ClassVar[str] = "Decide, from 1 to 100, what percentage of effort you want to put into the competition."

    def describe(self):
        return f"{self.actor.name} sizes up the competition."


# CEREMONIAL

class NominationMove(DefaultMove):
    nominees: list[DefaultHouseguest]
    
    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [NominationPhase]
    selection_id: ClassVar[str] = "Nominate for Eviction"
    choice_info: ClassVar[str] = "Choose the houseguests you will nominate for eviction."

    def describe(self):
        return f"{self.actor.name} has nominated folks for eviction."


class VetoMove(DefaultMove):
    choice: Optional[DefaultHouseguest] = None

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [VetoPhase]
    selection_id: ClassVar[str] = "Use Veto"
    choice_info: ClassVar[str] = "Use the Power of Veto to save one of the nominees, or decline to use it."

    def describe(self):
        if self.choice:
            return f"{self.actor.name} uses the Power of Veto on {self.choice.name}."
        return f"{self.actor.name} does not use the Power of Veto."


class ReplacementNomineeMove(DefaultMove):
    choice: DefaultHouseguest

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [VetoPhase]
    selection_id: ClassVar[str] = "Name Replacement Nominee"
    choice_info: ClassVar[str] = "Name a replacement nominee for eviction."

    def describe(self):
        return f"{self.actor.name} names {self.choice.name} as the replacement nominee."


class VetoDrawChoiceMove(DefaultMove):
    choice: DefaultHouseguest

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [VetoDrawPhase]
    selection_id: ClassVar[str] = "Houseguest's Choice"
    choice_info: ClassVar[str] = "Choose any eligible houseguest to play in the Veto competition."

    def describe(self):
        return f"{self.actor.name} chooses {self.choice.name} to play in the Veto competition."




# EVICTION/FINALE

class VoteMove(DefaultMove):
    choice: DefaultHouseguest


class EvictionVoteMove(VoteMove):
    is_tiebreaker: bool = False

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [EvictionVotePhase, FinalThreeEvictionPhase]
    selection_id: ClassVar[str] = "Vote to Evict"
    choice_info: ClassVar[str] = "Vote to evict one of the nominees."

    def describe(self):
        return f"{self.actor.name} votes to evict {self.choice.name}"
    

class JuryVoteMove(VoteMove):

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [JuryVotePhase]
    selection_id: ClassVar[str] = "Vote for Winner"
    choice_info: ClassVar[str] = "Vote for the houseguest you want to win the game."

    def describe(self):
        return f"{self.actor.name} votes for {self.choice.name}"
    

# # TODO: COLLECT SUBCLASS SELECTION IDs
# FIX: Figure out how to wire this. Please prioritize readable code over "clean", "pythonic" code.


# all_subclasses = []
# left_class = DefaultMove
# index = 0

# while index == 0 or left_class.__subclasses__():
#     all_subclasses.append(left_class)
#     all_subclasses.extend(left_class.__subclasses__())
#     if index < len(all_subclasses) - 1:
#         left_class = all_subclasses[index+1]
#     else:
#         break



# class SelectionResponse(Base, Generic[DM]):
#     selection_classes: list[type[DM]] = Field(exclude=True)

#     @property
#     def info(self) -> str:
#         "\n".join(f"{sc.selection_id}" for sc in self.selection_classes)