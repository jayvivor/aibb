from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Self, Generic, TypeVar, Mapping, cast
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

    
    def describe(self) -> str:
        raise NotImplementedError

    def deepcopy(self) -> Self:
        return self.model_copy(update={"hash_id":uuid4()})
    
    @classmethod
    def get_all_subclasses(cls) -> set[type]:
        subclasses = set(cls.__subclasses__())
        for subclass in list(subclasses):
            subclasses.update(subclass.get_all_subclasses())
        return subclasses

B = TypeVar("B", bound=Base)


class Ref(Base, Generic[B]):
    name: str

    def describe(self):
        return self.name

    def resolve(self, registry: Registry) -> B:
        return cast(B, registry[type(self)][self.name])

type Registry = Mapping[type[Ref], Mapping[str, Base]]


class Memory(Base):
    pass

M = TypeVar("M", bound=Memory)


class Status(Base, ABC, Generic[SV]):
    value: SV

S = TypeVar("S", bound=Status)


class Houseguest(Base, Generic[M, S]):
    name: str
    model_id: str
    # roles: list[Role] = Field(default_factory=list)
    memory: M
    statuses: list[S]

    def __hash__(self):
        return super().__hash__()

HG = TypeVar("HG", bound=Houseguest)


class Room(Base):
    name: str

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


class CompResults(Base, Generic[HG]):
    winner: HG

CR = TypeVar("CR", bound=CompResults)


class CompRuleset(Base, ABC, Generic[HG, CR]):

    @abstractmethod
    def run_comp(self, pool: list[HG]) -> CR:
        ...


class Competition(Base, ABC, Generic[HG, CR]):
    ruleset: CompRuleset
    competitors: list[HG]
    results: Optional[CR] = None

    def run_comp(self) -> CR:
        results = self.ruleset.run_comp(self.competitors)
        self.results = results
        return results
    

# Timestamps
class Timestamp(Base):
    index: int

    def __hash__(self):
        return super().__hash__()


class GameEvent(Base, ABC):
    timestamp: Timestamp

    @abstractmethod
    def narrate(self, hg) -> str:
        ...


class MoveResponse(Base, ABC, Generic[HG, MV]):

    selection_id: str
    actor: HG

    @abstractmethod
    def get_move(self, registry: Registry) -> MV:
        ...