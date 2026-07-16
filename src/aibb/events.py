from pydantic import Field

from aibb.base import GameEvent, Timestamp
from aibb.houseguest import DefaultHouseguest
from aibb.interaction import Interactable, Action
from aibb.utils import listed



class NullTimestamp(Timestamp):
    index: int = -1

    def describe(self):
        return "The beginning of time."


class DefaultGameEvent(GameEvent):

    def narrate(self, hg: DefaultHouseguest):
        return self.describe().replace(hg.name, 'You')


# SOCIAL

class SpokenMessage(DefaultGameEvent):  # Spoken loud
    speaker: DefaultHouseguest
    content: str

    def describe(self):
        return f"({self.speaker.name} @ {self.timestamp.describe()}): {self.content}"


class WhisperedMessage(DefaultGameEvent):
    speaker: DefaultHouseguest
    content: str
    targets: list[DefaultHouseguest]  # Heard words
    witnesses: list[DefaultHouseguest]  # Heard whispering, didn't hear words

    def describe(self):
        return f"({self.speaker.name}, to {listed([t.name for t in self.targets])} @ {self.timestamp.describe()}): {self.content}"

    def narrate(self, hg):
        involved = [self.speaker] + self.targets
        if hg in involved:
            return super().narrate(hg)
        else:
            return f"{listed([t.name for t in involved])} @ {self.timestamp.describe()}: seemed to be whispering to each other."


class StartConvoEvent(DefaultGameEvent):
    hg: DefaultHouseguest
    participants: list[DefaultHouseguest]

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} pulls {listed([p.name for p in self.participants])} aside for a chat."


class JoinConvoEvent(DefaultGameEvent):
    hg: DefaultHouseguest

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} joins the conversation."
    

class ExitConvoEvent(DefaultGameEvent):
    hg: DefaultHouseguest

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} leaves the conversation."


class ConversationHistory(DefaultGameEvent):
    join_history: list[JoinConvoEvent] = Field(default_factory=list)
    exit_history: list[ExitConvoEvent] = Field(default_factory=list)
    speech_history: list[SpokenMessage] = Field(default_factory=list)
    whisper_history: list[WhisperedMessage] = Field(default_factory=list)
    turn_duration: int = 0

    def get_all_members(self) -> set[DefaultHouseguest]:
        all_members: set[DefaultHouseguest] = set()
        for event in self.join_history + self.exit_history:
            all_members.add(event.hg)
        return all_members

    def describe(self):
        return f"({self.timestamp.describe()}): A conversation involving {listed([hg.name for hg in self.get_all_members()])} for {self.turn_duration} turns."
    



# ROOM

class Interaction(DefaultGameEvent):
    actor: DefaultHouseguest
    action: Action
    object: Interactable
    turn_duration: int

    def describe(self):
        return f"({self.timestamp.describe()}): {self.actor.name} interacts with the {self.object.name}."


class JoinRoomEvent(DefaultGameEvent):
    hg: DefaultHouseguest

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} enters the room."


class ExitRoomEvent(DefaultGameEvent):
    hg: DefaultHouseguest

    def describe(self):
        return f"({self.timestamp.describe()}): {self.hg.name} leaves the room."


class RoomHistory(DefaultGameEvent):
    timestamp: Timestamp = Field(default_factory=NullTimestamp)
    join_history: list[JoinRoomEvent] = Field(default_factory=list)
    exit_history: list[ExitRoomEvent] = Field(default_factory=list)
    speech_history: list[SpokenMessage] = Field(default_factory=list)
    interaction_history: list[Interaction] = Field(default_factory=list)
    conversation_history: list[ConversationHistory] = Field(default_factory=list)


# COMP

class CompScoreboard(DefaultGameEvent):
    scores: dict[DefaultHouseguest, int]


class EvictionResultEvent(DefaultGameEvent):
    evicted: DefaultHouseguest
    saved: DefaultHouseguest | list[DefaultHouseguest]
    vote_dict: dict[DefaultHouseguest, int]

    def describe(self):
        return f"({self.timestamp.describe()}): By a vote of {'-'.join([str(i) for i in self.vote_dict.values()])}, {self.evicted.name} is evicted."


class EvictionVoteEvent(DefaultGameEvent):
    voter: DefaultHouseguest
    choice: DefaultHouseguest

    def describe(self):
        return f"({self.timestamp.describe()}): {self.voter.name} votes to evict {self.choice.name}."