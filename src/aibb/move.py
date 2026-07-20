from abc import ABC, abstractmethod
from typing import Generic, TypeVar, ClassVar
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
)
from aibb.utils import listed
'''
    NOTE: A Move is an encapsulation of the Houseguest's attempted action, 
    not necessarily a completed action.
'''


__all__ = [
    "SpeakMove",
    "WhisperMove",
]



class DefaultMove(Move[DefaultHouseguest], ABC):

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]]
    selection_id: ClassVar[str]
    choice_info: ClassVar[str]

DM = TypeVar("DM", bound=DefaultMove)


class MoveResponse(Base, ABC, Generic[DM]):
    diary_room: str = Field(description="Your private explanation of the move; nobody else in the game will see this.")
    move: DM



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

    def describe(self): # TODO
        # return f"A conversation involving {listed([hg.name for hg in self.history.get_all_members()])}"
        return f"A conversation."

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


OPEN_MOVES = SpeakMove | WhisperMove | StartConversationMove | JoinConversationMove | ExitConversationMove | ChangeRoomMove |  InteractMove


class OpenTurnResponse(MoveResponse[OPEN_MOVES]):
    pass


# SCHEME

class SchemeMove(DefaultMove):
    updated_memory: DefaultMemory

    selection_id: ClassVar[str] = "Scheme"
    choice_info: ClassVar[str] = "Update your scratchpad to include anything worth carrying over to future phases."


# COMP

class CompMove(DefaultMove):
    
    selection_id: ClassVar[str] = "Compete"
    choice_info: ClassVar[str] = "Decide how to approach the competition."


class EffortMove(CompMove):
    effort: int = Field(description="The percentage of effort - from 1 to 100 - that you will put into trying to win.")

    selection_id: ClassVar[str] = "Choose Effort"
    choice_info: ClassVar[str] = "Decide, from 1 to 100, what percentage of effort you want to put into the competition."


# CEREMONIAL

class NominationMove(DefaultMove):
    nominees: list[DefaultHouseguest]
    
    selection_id: ClassVar[str] = "Nominate for Eviction"

    def describe(self):
        return f"{self.actor.name} has nominated folks for eviction."




# EVICTION/FINALE

class VoteMove(DefaultMove):
    choice: DefaultHouseguest


class EvictionVoteMove(VoteMove):
    is_tiebreaker: bool = False

    selection_id: ClassVar[str] = "Vote to Evict"

    def describe(self):
        return f"{self.actor.name} votes to evict {self.choice.name}"
    

class JuryVoteMove(VoteMove):

    selection_id: ClassVar[str] = "Vote for Winner"

    def describe(self):
        return f"{self.actor.name} votes for {self.choice.name}"
    

# # TODO: COLLECT SUBCLASS SELECTION IDs


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





