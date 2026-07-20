from pydantic import Field
from typing import Generic, TypeVar, Optional
from enum import Enum, auto

from aibb.base import Base, GameEvent, Timestamp
from aibb.houseguest import DefaultHouseguest, DefaultRole
from aibb.interaction import Interactable, Action
from aibb.room import InteractiveRoom
from aibb.utils import listed
from aibb.move import Conversation


class DefaultTimestamp(Timestamp):
    week_number: int
    turn_number: int
    
    def describe(self):
        return f"Week {self.week_number}, Turn {self.turn_number}"


class NullTimestamp(Timestamp):
    index: int = -1

    def describe(self):
        return "The beginning of time."


class Perspective(Enum):
    ACTOR = auto()  # Person actually speaking, interacting, moving, etc.
    TARGET = auto()  # Intended recipient (ex: person spoken to in a conversation)
    WITNESS = auto()  # Known recipient (ex: person who saw a hg leave a room)
    SNOOP = auto()  # Unknown recipient (ex: person who overhears laughter in another room)


class DefaultGameEvent(GameEvent):
    perspective_map: dict[DefaultHouseguest, Perspective]
    location: InteractiveRoom

    def _exclusive_perspective(self, perspective: Perspective, attr: Optional[str]=None):
        attr = attr or perspective.name.lower()
        if len(self.reverse_perspective_map[perspective]) != 1:
            raise ValueError(f"Not OR more than one {attr}")
        val = self.reverse_perspective_map[perspective][0]
        return val
    

    @property
    def reverse_perspective_map(self):

        reverse_map: dict[Perspective, list[DefaultHouseguest]] = {p: [] for p in Perspective}

        for ob, per in self.perspective_map.items():
            reverse_map[per].append(ob)
        
        return reverse_map
    
    @property
    def actors(self) -> list[DefaultHouseguest]:
        return self.reverse_perspective_map[Perspective.ACTOR]

    @property
    def targets(self) -> list[DefaultHouseguest]:
        return self.reverse_perspective_map[Perspective.TARGET]
    
    @property
    def witnesses(self) -> list[DefaultHouseguest]:
        return self.reverse_perspective_map[Perspective.WITNESS]

    @property
    def snoopers(self) -> list[DefaultHouseguest]:
        return self.reverse_perspective_map[Perspective.SNOOP]
    
    @property
    def actor(self):
        return self._exclusive_perspective(Perspective.ACTOR)
    
    @property
    def target(self):
        return self._exclusive_perspective(Perspective.TARGET)
    
    @property
    def witness(self):
        return self._exclusive_perspective(Perspective.WITNESS)
    
    @property
    def snoop(self):
        return self._exclusive_perspective(Perspective.SNOOP)


    def narrate(self, hg: DefaultHouseguest):
        return self.describe().replace(hg.name, 'You')
    
# DGE = TypeVar("DGE", bound=DefaultGameEvent)


type Observer = Base
O = TypeVar("O", bound=Observer)

# class History(Base, Generic[O]):
#     event_dict: dict[Timestamp, list[DefaultGameEvent]]



# SOCIAL

class SpokenMessage(DefaultGameEvent):
    content: str

    @property
    def speaker(self) -> DefaultHouseguest:
        return self._exclusive_perspective(Perspective.ACTOR, attr="speaker")

    def describe(self):
        return f"({self.speaker.name} @ {self.timestamp.describe()}): {self.content}"


class WhisperedMessage(DefaultGameEvent):
    content: str

    @property
    def speaker(self) -> DefaultHouseguest:
        return self._exclusive_perspective(Perspective.ACTOR, attr="speaker")
    
    def describe(self):
        return f"({self.speaker.name}, to {listed([t.name for t in self.targets])} @ {self.timestamp.describe()}): {self.content}"

    def narrate(self, hg):
        involved = [self.speaker] + self.targets
        if hg in involved:
            return super().narrate(hg)
        else:
            return f"{listed([t.name for t in involved])} @ {self.timestamp.describe()}: seemed to be whispering to each other."


class StartConvoEvent(DefaultGameEvent):

    @property
    def hg(self):
        return self.actor
    
    @property
    def participants(self):
        return self.targets

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} pulls {listed([p.name for p in self.participants])} aside for a chat."


class JoinConvoEvent(DefaultGameEvent):

    convo: Conversation

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} joins the conversation."
    

class ExitConvoEvent(DefaultGameEvent):

    convo: Conversation

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} leaves the conversation."
    

class EndConvoEvent(DefaultGameEvent):

    convo: Conversation

    def describe(self):
        return f"({self.timestamp.describe()}): The conversation ends."


# class ConversationHistory(DefaultGameEvent):
#     join_history: list[JoinConvoEvent] = Field(default_factory=list)
#     exit_history: list[ExitConvoEvent] = Field(default_factory=list)
#     speech_history: list[SpokenMessage] = Field(default_factory=list)
#     whisper_history: list[WhisperedMessage] = Field(default_factory=list)
#     turn_duration: int = 0

#     def get_all_members(self) -> set[DefaultHouseguest]:
#         all_members: set[DefaultHouseguest] = set()
#         for event in self.join_history + self.exit_history:
#             all_members.add(event.hg)
#         return all_members

#     def describe(self):
#         return f"({self.timestamp.describe()}): A conversation involving {listed([hg.name for hg in self.get_all_members()])} for {self.turn_duration} turns."
    



# ROOM

class Interaction(DefaultGameEvent):
    action: Action
    object: Interactable
    # turn_duration: int

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} interacts with the {self.object.name}."


class JoinRoomEvent(DefaultGameEvent):

    room: InteractiveRoom

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} enters the room."


class ExitRoomEvent(DefaultGameEvent):

    room: InteractiveRoom

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} leaves the room."


# COLLECTIONS
# TODO: Registry pattern; ClassVar specifically for the perspectives which should "see" a historical moment
ROOM_EVENT_TYPES = Interaction | JoinRoomEvent | ExitRoomEvent
# HOUSEGUEST_EVENT_TYPES = as_union(DefaultGameEvent.get_all_subclasses())
HOUSEGUEST_EVENT_TYPES = DefaultGameEvent






# class RoomHistory(DefaultGameEvent):
#     timestamp: Timestamp = Field(default_factory=NullTimestamp)
#     join_history: list[JoinRoomEvent] = Field(default_factory=list)
#     exit_history: list[ExitRoomEvent] = Field(default_factory=list)
#     speech_history: list[SpokenMessage] = Field(default_factory=list)
#     interaction_history: list[Interaction] = Field(default_factory=list)
#     conversation_history: list[ConversationHistory] = Field(default_factory=list)



# COMP

NUMBER = TypeVar("NUMBER", bound=int | float)

class ExclusiveCrowning(DefaultGameEvent):
    prize: DefaultRole

    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} now holds the '{self.prize.name.lower()}' title."
    

class AdditiveCrowning(DefaultGameEvent):
    prize: DefaultRole

    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} now holds the '{self.prize.name.lower()}' title."
    

class DeCrowning(DefaultGameEvent):
    prize: DefaultRole

    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} has lost the '{self.prize.name.lower()}' title."



class CompScore(DefaultGameEvent, Generic[NUMBER]):
    score: NUMBER

class CompScoreboard(Base):
    scores: list[CompScore]


# CEREMONIAL

class EvictionResultEvent(DefaultGameEvent):
    vote_dict: dict[DefaultHouseguest, int]

    @property
    def evicted(self):
        return self.actor
    
    @property
    def saved(self):
        return self.targets

    def describe(self):
        return f"({self.timestamp.describe()}): By a vote of {'-'.join([str(i) for i in self.vote_dict.values()])}, {self.evicted.name} is evicted."


class EvictionVoteEvent(DefaultGameEvent):

    choice: DefaultHouseguest

    @property
    def voter(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.voter.name} votes to evict {self.choice.name}."
    

class NominationEvent(DefaultGameEvent):

    @property
    def nominees(self):
        return self.targets
    
    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} nominates {listed([nom.name for nom in self.nominees])} for eviction."


class VetoUseEvent(DefaultGameEvent):

    used_on: Optional[DefaultHouseguest]
    replacement: Optional[DefaultHouseguest]

    @property
    def holder(self):
        return self.actor
    
    def describe(self):
        description = f"({self.timestamp.describe()}): {self.holder.name}"
        if self.used_on:
            description += f" uses the veto on {self.used_on.name}"
            if self.replacement:
                description += f"; {self.replacement.name} is named as the replacement."
            else:
                description += "."
        return description


# SPECIAL/META

class EndWeek(DefaultGameEvent):
    pass