from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Self, Generic, TypeVar
from enum import Enum
from uuid import UUID, uuid4
from abc import ABC, abstractmethod


class Role(Enum):
    pass

class TurnType(Enum):
    pass

class StatusValue(Enum):
    
    @property
    def default_value(self) -> Self:
        raise NotImplementedError

SV = TypeVar("SV", bound=StatusValue)


class Base(BaseModel, ABC):
    hash_id: UUID = Field(default_factory=uuid4, exclude=True)

    def __hash__(self):
        return self.hash_id.int
    
    @abstractmethod
    def describe(self) -> str:
        ...

    def deepcopy(self) -> Self:
        return self.model_copy(update={"hash_id":uuid4()})


class Memory(Base):
    pass

M = TypeVar("M", bound=Memory)


class Status(Base, ABC, Generic[SV]):
    value: SV

S = TypeVar("S", bound=Status)


class Houseguest(Base, Generic[M, S]):
    name: str
    model_id: str
    roles: list[Role] = Field(default_factory=list)
    memory: M
    statuses: list[S]

    def __hash__(self):
        return super().__hash__()


HG = TypeVar("HG", bound=Houseguest)






class Room(Base, Generic[HG]):
    name: str
    members: list[HG] = Field(default_factory=list)

R = TypeVar("R", bound=Room)


class Move(Base, ABC, Generic[HG]):  # What an HG does in a given turn
    actor: HG

MV = TypeVar("MV", bound=Move)


class Turn(Base, ABC, Generic[MV]):  # A unit of time in the house
    moves: list[MV] = Field(default_factory=list)
    turn_type: TurnType

    def describe(self):
        raise NotImplementedError

T = TypeVar("T", bound=Turn)


class Phase(Base, Generic[T]):
    name: str
    turns: list[T] = Field(default_factory=list)

P = TypeVar("P", bound=Phase)


class Week(Base, Generic[P]):
    name: str
    schedule: list[P]

W = TypeVar("W", bound=Week)


class House(Base, ABC, Generic[HG, R, W, T]):
    name: str
    cast: list[HG]
    rooms: list[R]
    schedule: list[W]


    def get_active_hgs(self) -> set[HG]:
        all_hgs = set()
        for room in self.rooms:
            all_hgs.update(member for member in room.members)
        return all_hgs
    
    @abstractmethod
    def evict(self, hg: HG):
        ...

    @abstractmethod
    def get_hg_move(self, turn: T, hg: HG) -> Move:
        ...

    def run_turn(self, turn: T) -> T:
        moves = [self.get_hg_move(turn, hg) for hg in self.get_active_hgs()]
        turn.moves = moves
        return turn
    
    def run_phase(self, phase: Phase, pool: list[Houseguest]) -> Phase:
        turns = [self.run_turn(turn=turn) for turn in phase.turns]
        phase.turns = turns
        return phase
    
    def run_week(self, week: Week, pool: list[Houseguest]) -> Week:
        phases = [self.run_phase(phase=phase, pool=pool) for phase in week.schedule]
        week.schedule = phases
        return week
    
    def run(self):
        print("Running weeks...")
        for week in self.schedule:
            print(f"*Week {week.name}*")
            self.run_week(week, list(self.get_active_hgs()))
        print("Complete.")


class Audience(Base, ABC):

    @abstractmethod
    def get_members(self) -> set[Houseguest]:
        ...

    def describe(self):
        raise NotImplementedError


class Message(Base):
    content: str
    audience: Audience

    def __str__(self):
        return self.content


class CompResults(Base):
    winner: Houseguest


class CompRuleset(Base, ABC, Generic[HG]):

    @abstractmethod
    def run_comp(self, pool: list[HG]) -> CompResults:
        ...


class Competition(Base, ABC, Generic[HG]):
    ruleset: CompRuleset
    competitors: list[HG]
    results: Optional[CompResults] = None

    
    def run_comp(self) -> CompResults:
        results = self.ruleset.run_comp(self.competitors)
        self.results = results
        return results
    

# Timestamps
class Timestamp(Base):
    index: int

    def __sub__(self, other: Self):
        return self.index - other.index


class GameEvent(Base, ABC):
    timestamp: Timestamp

    @abstractmethod
    def narrate(self, hg) -> str:
        ...