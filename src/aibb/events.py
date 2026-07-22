from typing import TypeVar, Optional, Self
from enum import Enum, auto

from aibb.base import Base, GameEvent, Timestamp
from aibb.houseguest import DefaultHouseguest, DefaultMemory, DefaultRole
from aibb.interaction import Interactable, Action
from aibb.room import InteractiveRoom
from aibb.utils import listed
from aibb.move import Conversation


class DefaultTimestamp(Timestamp):
    week_number: int
    phase_number: int
    turn_number: int

    def __hash__(self):
        return super().__hash__()
    
    def describe(self):
        return f"Week {self.week_number}, Turn {self.turn_number}"
    
    def __gt__(self, other: Self):
        if self.week_number == other.week_number:
            if self.phase_number == other.phase_number:
                return self.turn_number > other.turn_number
            return self.phase_number > other.phase_number
        return self.week_number > other.week_number
    
    def __eq__(self, other):
        if not isinstance(other, DefaultTimestamp):
            return NotImplemented
        return self.week_number == other.week_number and \
            self.phase_number == other.phase_number and \
            self.turn_number == other.turn_number


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
            raise ValueError(f"None or more than one {attr}")
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


type Observer = Base
O = TypeVar("O", bound=Observer)


# SOCIAL

class SpokenMessage(DefaultGameEvent):
    content: str

    @property
    def speaker(self) -> DefaultHouseguest:
        return self._exclusive_perspective(Perspective.ACTOR, attr="speaker")

    def describe(self):
        return f"({self.speaker.name} @ {self.timestamp.describe()}): {self.content}"

    def narrate(self, hg):
        if self.perspective_map.get(hg) == Perspective.SNOOP:
            return f"({self.timestamp.describe()}): You hear voices coming from the {self.location.name}."
        return super().narrate(hg)


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


class EndInteractionEvent(DefaultGameEvent):
    object: Interactable

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} stops interacting with the {self.object.name}."


class SchemeEvent(DefaultGameEvent):
    updated_memory: DefaultMemory

    @property
    def hg(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} takes a moment to think."


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
# IGNORE: For now, leave this alone. I'll get to it, maybe.
ROOM_EVENT_TYPES = Interaction | JoinRoomEvent | ExitRoomEvent
# HOUSEGUEST_EVENT_TYPES = as_union(DefaultGameEvent.get_all_subclasses())
HOUSEGUEST_EVENT_TYPES = DefaultGameEvent


# COMP

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



# FABLE: Competing design - competition.CompScore (actor + value) is the one
# CompPhase.Status actually consumes; this event-flavored one is used nowhere.
# Commented out until the two are reconciled.
# IGNORE: Don't remove this comment; I'll implement actual non-random competitions later
# NUMBER = TypeVar("NUMBER", bound=int | float)
#
# class CompScore(DefaultGameEvent, Generic[NUMBER]):
#     score: NUMBER
#
# class CompScoreboard(Base):
#     scores: list[CompScore]


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
    

class JuryVoteEvent(DefaultGameEvent):

    choice: DefaultHouseguest

    @property
    def voter(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): {self.voter.name} votes for {self.choice.name} to win."


class JuryResultEvent(DefaultGameEvent):
    vote_dict: dict[DefaultHouseguest, int]

    @property
    def winner(self):
        return self.actor

    def describe(self):
        return f"({self.timestamp.describe()}): By a vote of {'-'.join([str(i) for i in self.vote_dict.values()])}, {self.winner.name} is the winner of Big Brother."


class EvictionEvent(DefaultGameEvent):

    @property
    def evicted(self):
        return self._exclusive_perspective(Perspective.ACTOR, attr="evicted")

    def describe(self):
        return f"({self.timestamp.describe()}): {self.evicted.name} has left the Big Brother house."


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
        else:
            description += " does not use the veto."
        return description


# SPECIAL/META

# FIX: This is intentionally bare, and it's only meant to happen if a week needs to end
# unexpectedly (ex: 'MedEvac' (an endpoint goes down mid-season)); don't worry about the
# use cases for now, but handle this in DefaultHouse by resetting the week.
class EndWeek(DefaultGameEvent):
    pass