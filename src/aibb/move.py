from abc import ABC, abstractmethod
from typing import Generic, TypeVar, ClassVar, Optional
from pydantic import Field

from aibb.base import Base, Move, Ref, Registry
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
    "EndInteractionMove",
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
    "ALL_MOVE_TYPES",
    "SELECTION_REGISTRY",
]



class DefaultMove(Move[DefaultHouseguest], ABC):

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]]
    selection_id: ClassVar[str]
    choice_info: ClassVar[str]

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        """The option line offered to the hg, or None if the move is unavailable to them."""
        return f"{cls.selection_id}: {cls.choice_info}"

DM = TypeVar("DM", bound=DefaultMove)


# OPEN

class OpenMove(DefaultMove):
    VALID_PHASES = [OpenPhase]


class SpeakMove(OpenMove):
    content: str

    selection_id: ClassVar[str] = "Speak"
    choice_info: ClassVar[str] = "Speak at a standard volume. Anyone present in the room will hear you."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        return f"{cls.selection_id}: {cls.choice_info} (set: content)"

    def describe(self):
        return f"{self.actor.name}: {self.content}"


## CONVERSATION

class Conversation(Base):
    active_participants: list[DefaultHouseguest]
    room: InteractiveRoom

    class Ref(Ref):
        name: str = Field(description="The exact name of any current participant in the conversation.")

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


def get_convo_groups(registry: Registry) -> list[list[str]]:
    groups: dict[int, list[str]] = {}
    for name, convo in registry.get(Conversation.Ref, {}).items():
        groups.setdefault(id(convo), []).append(name)
    return [group for group in groups.values()]


class StartConversationMove(DefaultMove):
    participants: list[DefaultHouseguest]

    selection_id: ClassVar[str] = "Start Conversation"
    choice_info: ClassVar[str] = "Start a conversation between yourself and the named houseguests. This will allow you to whisper to them, even if others are present in the room."

    def describe(self):
        return f"{self.actor.name} starts a conversation between {listed([p.name for p in self.participants])}."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        convo_table = registry.get(Conversation.Ref, {})
        free_hgs = [name for name in registry.get(DefaultHouseguest.Ref, {}) if name not in convo_table]
        if not free_hgs:
            return None
        return f"{cls.selection_id}: {cls.choice_info} (set: participants — any of {listed(free_hgs)})"


class JoinConversationMove(DefaultMove):
    conversation: Conversation

    selection_id: ClassVar[str] = "Join Ongoing Conversation"
    choice_info: ClassVar[str] = "Join an ongoing conversation between the named houseguests. This will allow you to whisper to them, and hear their whispers in future turns."

    def describe(self):
        return f"{self.actor.name} joins the conversation between {listed([p.name for p in self.conversation.active_participants])}"

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        joinable = [group for group in get_convo_groups(registry) if hg.name not in group]
        if not joinable:
            return None
        convo_list = "; ".join(f"the conversation between {listed(group)}" for group in joinable)
        return f"{cls.selection_id}: {cls.choice_info} (set: conversation, named by any participant — options: {convo_list})"


class ExitConversationMove(DefaultMove):
    conversation: Conversation

    selection_id: ClassVar[str] = "Leave Conversation"
    choice_info: ClassVar[str] = "Leave your current conversation."

    def describe(self):
        return f"{self.actor.name} leaves the conversation between {listed([p.name for p in self.conversation.active_participants])}"

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        if hg.name not in registry.get(Conversation.Ref, {}):
            return None
        return f"{cls.selection_id}: {cls.choice_info} (set: conversation, named by any participant)"


class WhisperMove(DefaultMove):
    content: str
    allow_join: bool = False

    selection_id: ClassVar[str] = "Whisper"
    choice_info: ClassVar[str] = "Speak in a hushed tone, exclusively to your conversation partners. Others present in the room will know you have whispered, but will not know what was said. If someone attempts to join the conversation this same turn, and `allow_join` is set to False, you will instead say nothing this turn."

    def describe(self):
        return f"{self.actor.name} (whispers): {self.content}"

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        if hg.name not in registry.get(Conversation.Ref, {}):
            return None
        return f"{cls.selection_id}: {cls.choice_info} (set: content, allow_join)"


## ROOM

class ChangeRoomMove(DefaultMove):
    room: InteractiveRoom

    selection_id: ClassVar[str] = "Change Rooms"
    choice_info: ClassVar[str] = "Enter the specified room."

    def describe(self):
        return f"{self.actor.name} moves to the {self.room.name}"

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        rooms = [name for name in registry.get(InteractiveRoom.Ref, {})]
        if not rooms:
            return None
        return f"{cls.selection_id}: {cls.choice_info} (set: room — one of {listed(rooms)})"


## INTERACTIVES


class InteractMove(DefaultMove):
    interactable: Interactable
    action: Action

    selection_id: ClassVar[str] = "Interact"
    choice_info: ClassVar[str] = "Interact with something in this room."

    def describe(self):
        return self.action.action_description.format(actor=self.actor, object=self.interactable.name)

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        interactable_table = registry.get(Interactable.Ref, {})
        if not interactable_table:
            return None
        interactable_infos = []
        for interactable in interactable_table.values():
            # TODO: The asserts need to go. This is just for the linter, for now.
            # IGNORE: [1]
            assert(isinstance(interactable, Interactable))
            actions = listed([action.value for action in interactable.interactors])
            interactable_infos.append(f"{interactable.name} (action: {actions})")
        return f"{cls.selection_id}: {cls.choice_info} (set: interactable and its action — options: {'; '.join(interactable_infos)})"


class EndInteractionMove(DefaultMove):
    interactable: Interactable

    selection_id: ClassVar[str] = "Stop Interacting"
    choice_info: ClassVar[str] = "Stop interacting with the specified object."

    def describe(self):
        return f"{self.actor.name} stops interacting with the {self.interactable.name}."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        for interactable in registry.get(Interactable.Ref, {}).values():
            # TODO: The asserts need to go. This is just for the linter, for now.
            # IGNORE: [1]
            assert(isinstance(interactable, Interactable))
            for interacting_hgs in interactable.interactors.values():
                if hg in interacting_hgs:
                    return f"{cls.selection_id}: {cls.choice_info} (set: interactable)"
        return None


# FABLE: The live OPEN_MOVES collection is the list in response.py.
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

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        return f"{cls.selection_id}: {cls.choice_info} (set: updated_scratchpad)"

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

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        return f"{cls.selection_id}: {cls.choice_info} (set: effort)"

    def describe(self):
        return f"{self.actor.name} sizes up the competition."


# CEREMONIAL

class NominationMove(DefaultMove):
    nominees: list[DefaultHouseguest]
    
    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [NominationPhase]
    selection_id: ClassVar[str] = "Nominate for Eviction"
    choice_info: ClassVar[str] = "Choose the houseguests you will nominate for eviction."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        candidates = [name for name in registry.get(DefaultHouseguest.Ref, {})]
        return f"{cls.selection_id}: {cls.choice_info} (set: nominees — from {listed(candidates)})"

    def describe(self):
        return f"{self.actor.name} has nominated folks for eviction."


class VetoMove(DefaultMove):
    choice: Optional[DefaultHouseguest] = None

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [VetoPhase]
    selection_id: ClassVar[str] = "Use Veto"
    choice_info: ClassVar[str] = "Use the Power of Veto to save one of the nominees, or decline to use it."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        nominees = [name for name in registry.get(DefaultHouseguest.Ref, {})]
        return f"{cls.selection_id}: {cls.choice_info} (set: choice — one of {listed(nominees)}, or null to decline)"

    def describe(self):
        if self.choice:
            return f"{self.actor.name} uses the Power of Veto on {self.choice.name}."
        return f"{self.actor.name} does not use the Power of Veto."


class ReplacementNomineeMove(DefaultMove):
    choice: DefaultHouseguest

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [VetoPhase]
    selection_id: ClassVar[str] = "Name Replacement Nominee"
    choice_info: ClassVar[str] = "Name a replacement nominee for eviction."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        candidates = [name for name in registry.get(DefaultHouseguest.Ref, {})]
        return f"{cls.selection_id}: {cls.choice_info} (set: choice — one of {listed(candidates)})"

    def describe(self):
        return f"{self.actor.name} names {self.choice.name} as the replacement nominee."


class VetoDrawChoiceMove(DefaultMove):
    choice: DefaultHouseguest

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [VetoDrawPhase]
    selection_id: ClassVar[str] = "Houseguest's Choice"
    choice_info: ClassVar[str] = "Choose any eligible houseguest to play in the Veto competition."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        candidates = [name for name in registry.get(DefaultHouseguest.Ref, {})]
        return f"{cls.selection_id}: {cls.choice_info} (set: choice — one of {listed(candidates)})"

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

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        nominees = [name for name in registry.get(DefaultHouseguest.Ref, {})]
        return f"{cls.selection_id}: {cls.choice_info} (set: choice — one of {listed(nominees)})"

    def describe(self):
        return f"{self.actor.name} votes to evict {self.choice.name}"
    

class JuryVoteMove(VoteMove):

    VALID_PHASES: ClassVar[list[type[DefaultPhase]]] = [JuryVotePhase]
    selection_id: ClassVar[str] = "Vote for Winner"
    choice_info: ClassVar[str] = "Vote for the houseguest you want to win the game."

    @classmethod
    def get_option(cls, hg: DefaultHouseguest, registry: Registry) -> Optional[str]:
        finalists = [name for name in registry.get(DefaultHouseguest.Ref, {})]
        return f"{cls.selection_id}: {cls.choice_info} (set: choice — one of {listed(finalists)})"

    def describe(self):
        return f"{self.actor.name} votes for {self.choice.name}"
    

# COLLECT SUBCLASS SELECTION IDs
# FIX: Figure out how to wire this. Please prioritize readable code over "clean", "pythonic" code.

ALL_MOVE_TYPES: list[type[DefaultMove]] = []
unchecked_move_types: list[type[DefaultMove]] = [DefaultMove]

while unchecked_move_types:
    move_type = unchecked_move_types.pop()
    unchecked_move_types.extend(move_type.__subclasses__())
    if hasattr(move_type, "selection_id"):
        ALL_MOVE_TYPES.append(move_type)


SELECTION_REGISTRY: dict[str, type[DefaultMove]] = {}
for move_type in ALL_MOVE_TYPES:
    SELECTION_REGISTRY[move_type.selection_id] = move_type