from __future__ import annotations
from pydantic import Field
from typing import ClassVar, Optional
from abc import ABC, abstractmethod
from enum import Enum, auto

from aibb.base import Base, Week, Phase, CompRuleset
from aibb.houseguest import DefaultRole, DefaultHouseguest
from aibb.competition import CompScore


__all__ = [
    "OpenPhase",
    "CompPhase",
    "SleepPhase",
    "CeremonyPhase",
    "NominationPhase",
    "VetoDrawPhase",
    "VetoPhase",
    "EvictionVotePhase",
    "FinalThreeEvictionPhase",
    "JuryVotePhase",
    "DefaultWeek",
    "FinaleWeek",
    "StandardWeek",
]

class PhaseStatusTurnType(Enum):
    pass

class DefaultTurnType(PhaseStatusTurnType):
    DEFAULT = auto()

class PhaseStatus[PSTT: PhaseStatusTurnType](Base, ABC):

    turn_types: ClassVar[type[PhaseStatusTurnType] | None]

    @classmethod
    def __pydantic_init_subclass__(cls, **kw):
        super().__pydantic_init_subclass__(**kw)
        # FABLE: The inner enums are declared on the Phase classes as <Phase>TurnType
        # (e.g. CompPhase.CompTurnType), never as "TurnType" on the Status, so this
        # lookup always falls back to DefaultTurnType - and turn_types is never read
        # anywhere. Needs a naming/ownership decision before it can do its job.
        # FIX: I tried to implement a fix for this one by hand; if it's incomplete, complete it.
        # If not, give me a gold star as a comment.
        inner = cls.__dict__.get("TurnType") or DefaultTurnType
        if inner:
            if not (isinstance(inner, type) and issubclass(inner, PhaseStatusTurnType)):
                raise TypeError(f"{cls.__name__}.TurnType must subclass PhaseStatusTurnType")
            cls.turn_types = inner
    
    @abstractmethod
    def get_turn_type(self) -> PSTT | None:
        ...


class DefaultPhase(Phase, ABC):

    info: ClassVar[str]
    status_type: ClassVar[type[PhaseStatus] | None] = None

    @classmethod
    def __pydantic_init_subclass__(cls, **kw):
        super().__pydantic_init_subclass__(**kw)
        if inner := cls.__dict__.get("Status"):
            if not (isinstance(inner, type) and issubclass(inner, PhaseStatus)):
                raise TypeError(f"{cls.__name__}.Status must subclass PhaseStatus")
            cls.status_type = inner

    def describe(self):
        raise NotImplementedError
    
    @abstractmethod
    def get_status(self) -> PhaseStatus:
        ...
    

OPEN_PHASE_INFO = '''
This is the "Open" Phase. You are free to explore and converse with other houseguests.
'''

class OpenPhase(DefaultPhase):
    name: str = "Open"
    num_turns: int
    info: ClassVar[str] = OPEN_PHASE_INFO

    class Status(PhaseStatus):
        turns_run: int = Field(default=0)
        max_turns: int

        def get_turn_type(self):
            TT = DefaultTurnType
            if self.turns_run < self.max_turns:
                return TT.DEFAULT
            return None

    def describe(self):
        return f'''Open phase ({self.num_turns} turns)'''
    
    def get_status(self) -> OpenPhase.Status:
        return OpenPhase.Status(turns_run=0, max_turns=self.num_turns)


COMP_PHASE_INFO = '''
This is the "Competition" phase. You are competing for a prize.
'''
    
class CompPhase(DefaultPhase):
    comp_ruleset: CompRuleset
    prize: DefaultRole
    allowed_roles: list[DefaultRole]
    disallowed_roles: list[DefaultRole] = Field(default_factory=list)
    info: ClassVar[str] = COMP_PHASE_INFO


    class TurnType(PhaseStatusTurnType):
        INIT = auto()  # TODO: This is a "No API" turn, technically; figure out solution
                        # FIX/RESOLVE: I think the current approach might actually be fine. Only change
                        # it if you really, earnestly think it's bad and needs fixing, but the recursive 
                        # calls in the `process_phase_turn` switch seems like an okay solution to me.
        GET_EFFORTS = auto()
        GET_SCORES = auto()
        CROWN_WINNER = auto()


    class Status(PhaseStatus[TurnType]):
        players: list[DefaultHouseguest] = Field(default_factory=list)
        efforts: dict[DefaultHouseguest, int] = Field(default_factory=dict)
        scores: list[CompScore] = Field(default_factory=list)
        winner_crowned: bool = False

        def get_turn_type(self):
            TT = CompPhase.TurnType
            if not self.players:
                return TT.INIT
            if len(self.players) > len(self.efforts.keys()):
                return TT.GET_EFFORTS
            if not len(self.players) == len(self.scores):
                return TT.GET_SCORES
            if not self.winner_crowned:
                return TT.CROWN_WINNER
            return None


    def describe(self):
        return f"Comp phase (Prize: {self.prize.value})"
    
    def get_status(self):
        return CompPhase.Status()
    

SLEEP_PHASE_INFO = '''
The house is "asleep". You will all "wake" at the same time.
'''
  

class SleepPhase(DefaultPhase):
    name: str = "End of Day"
    info: ClassVar[str] = SLEEP_PHASE_INFO


    class Status(PhaseStatus):
        schemers: list[DefaultHouseguest] = Field(default_factory=list)
        scheme_dict: dict[DefaultHouseguest, str] = Field(default_factory=dict)

        def get_turn_type(self):
            TT = DefaultTurnType
            if not self.schemers or not self.scheme_dict:
                return TT.DEFAULT
            return None


    def get_status(self):
        return SleepPhase.Status()


CEREMONY_PHASE_INFO = '''
This is a "Ceremony" phase.
'''

class CeremonyPhase(DefaultPhase):
    name: str = "Ceremony"
    info: ClassVar[str] = CEREMONY_PHASE_INFO


NOMINATION_PHASE_INFO = '''
This is a "Nomination" Phase.
'''

class NominationPhase(CeremonyPhase):
    name: str = "Nomination Ceremony"
    info: ClassVar[str] = NOMINATION_PHASE_INFO


    class TurnType(PhaseStatusTurnType):
        INIT = auto()
        GET_NOMINATIONS = auto()


    class Status(PhaseStatus[TurnType]):
        hoh: Optional[DefaultHouseguest] = None
        nominees: list[DefaultHouseguest] = Field(default_factory=list)

        def get_turn_type(self):
            TT = NominationPhase.TurnType
            if not self.hoh:
                return TT.INIT
            if not self.nominees:
                return TT.GET_NOMINATIONS
            return None
        

    def get_status(self):
        return NominationPhase.Status()


VETO_PHASE_INFO = '''
This is a "Veto" Phase.
'''

class VetoPhase(CeremonyPhase):
    name: str = "Veto Ceremony"
    info: ClassVar[str] = VETO_PHASE_INFO

    class TurnType(PhaseStatusTurnType):
        INIT = auto()
        VETO_CHOICE = auto()
        REPLACEMENT_CHOICE = auto()

    class Status(PhaseStatus[TurnType]):
        holder: Optional[DefaultHouseguest] = None
        saved: Optional[DefaultHouseguest | bool] = None
        replacement: Optional[DefaultHouseguest | bool] = None

        def get_turn_type(self):
            TT = VetoPhase.TurnType
            if not self.holder:
                return TT.INIT
            if self.saved is None:
                return TT.VETO_CHOICE
            if self.saved and not self.replacement:
                return TT.REPLACEMENT_CHOICE
            return None
        
    def get_status(self):
        return VetoPhase.Status()


VETO_DRAW_PHASE_INFO = '''
This is a "Veto Draw" Phase.
'''

class VetoDrawPhase(CeremonyPhase):
    name: str = "Veto Draw Ceremony"
    info: ClassVar[str] = VETO_DRAW_PHASE_INFO

    class TurnType(PhaseStatusTurnType):
        INIT = auto()
        DRAW_NEEDED = auto()
        HG_CHOICE = auto()

    class Status(PhaseStatus[TurnType]):
        drawn_dict: dict[DefaultHouseguest, DefaultHouseguest] = Field(default_factory=dict)
        draws_needed: int = 3

        def get_turn_type(self):
            TT = VetoDrawPhase.TurnType
            if not self.drawn_dict:
                return TT.INIT
            for drafter, drawn in self.drawn_dict.items():
                if drafter == drawn:
                    return TT.HG_CHOICE
            if len(self.drawn_dict.values()) < self.draws_needed:
                    return TT.DRAW_NEEDED
            return None
        
    def get_status(self):
        return VetoDrawPhase.Status()


EVICTION_PHASE_INFO = '''
This is an "Eviction Vote" Phase.
'''

class EvictionVotePhase(CeremonyPhase):
    name: str = "Live Vote and Eviction"
    info: ClassVar[str] = EVICTION_PHASE_INFO


    class TurnType(PhaseStatusTurnType):
        INIT = auto()
        VOTE_NEEDED = auto()
        TIEBREAK_NEEDED = auto()


    class Status(PhaseStatus[TurnType]):
        voters: list[DefaultHouseguest] = Field(default_factory=list)
        vote_tally: dict[DefaultHouseguest, DefaultHouseguest] = Field(default_factory=dict)
        evicted: Optional[DefaultHouseguest] = None

        def get_turn_type(self):
            TT = EvictionVotePhase.TurnType
            if not self.voters:
                return TT.INIT
            if not self.vote_tally:
                return TT.VOTE_NEEDED
            if not self.evicted:
                return TT.TIEBREAK_NEEDED
            return None
        
    
    def get_status(self):
        return EvictionVotePhase.Status()


FINAL_THREE_EVICTION_PHASE_INFO = '''
This is the Final Eviction Phase.
'''

class FinalThreeEvictionPhase(CeremonyPhase):
    name: str = "Final Three Eviction Ceremony"
    info: ClassVar[str] = FINAL_THREE_EVICTION_PHASE_INFO

    class TurnType(PhaseStatusTurnType):
        INIT = auto()
        VOTE_NEEDED = auto()
        EVICTION = auto()


    class Status(PhaseStatus[TurnType]):
        voters: list[DefaultHouseguest] = Field(default_factory=list)
        choice: Optional[DefaultHouseguest] = None
        evicted: bool = False

        def get_turn_type(self):
            TT = FinalThreeEvictionPhase.TurnType
            if not self.voters:
                return TT.INIT
            if not self.choice:
                return TT.VOTE_NEEDED
            if not self.evicted:
                return TT.EVICTION
            return None
        

    def get_status(self):
        return FinalThreeEvictionPhase.Status()


JURY_VOTE_PHASE_INFO = '''
This is a "Jury Vote" Phase.
'''

class JuryVotePhase(CeremonyPhase):
    name: str = "Jury Vote Ceremony"
    info: ClassVar[str] = JURY_VOTE_PHASE_INFO

    class TurnType(PhaseStatusTurnType):
        INIT = auto()
        VOTE_NEEDED = auto()
        EVICTION = auto()


    class Status(PhaseStatus[TurnType]):
        voters: list[DefaultHouseguest] = Field(default_factory=list)
        vote_tally: dict[DefaultHouseguest, DefaultHouseguest] = Field(default_factory=dict)
        evicted: Optional[DefaultHouseguest] = None

        def get_turn_type(self):
            TT = JuryVotePhase.TurnType
            if not self.voters:
                return TT.INIT
            if not self.vote_tally:
                return TT.VOTE_NEEDED
            if not self.evicted:
                return TT.EVICTION
            return None
        
    def get_status(self):
        return JuryVotePhase.Status()



DEFAULT_WEEK_INFO = '''
A Standard Week of Big Brother.
'''

class DefaultWeek(Week[DefaultPhase]): 

    schedule: list[DefaultPhase] = Field(default_factory=list)
    info: ClassVar[str] = DEFAULT_WEEK_INFO

    @property
    def schedule_info(self):
        return "\n".join(f" - {phase.name}" for phase in self.schedule)


class FinaleWeek(DefaultWeek):
    name: str = "Finale"
    hoh_comp_ruleset: CompRuleset

    def model_post_init(self, context):
        self.schedule: list[DefaultPhase] = [
            CompPhase(
                name="Final HoH",
                prize=DefaultRole.HOH,
                comp_ruleset=self.hoh_comp_ruleset,
                allowed_roles=[
                    DefaultRole.ACTIVE,
                ]
            ),
            FinalThreeEvictionPhase(),
            JuryVotePhase(),        
        ]
        return super().model_post_init(context)

    def describe(self):
        return f'''
        Schedule:
        {'\n    - '.join(phase.describe() for phase in self.schedule)}
        '''


class StandardWeek(DefaultWeek):
    hoh_comp_ruleset: CompRuleset
    veto_comp_ruleset: CompRuleset
    turns_per_hour: int = 5

    def model_post_init(self, context):
        self.schedule = [
            # Thursday Night
            OpenPhase(
                num_turns=self.turns_per_hour*1,
            ),
            CompPhase(
                name="Head of Household Competition",
                prize=DefaultRole.HOH,
                comp_ruleset=self.hoh_comp_ruleset,
                allowed_roles=[
                    DefaultRole.ACTIVE,
                ],
                disallowed_roles=[
                    DefaultRole.OUTGOING_HOH,
                ]
            ),
            OpenPhase(
                num_turns=self.turns_per_hour*4,
            ),
            SleepPhase(),
            # Friday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*2,
            ),
            NominationPhase(),
            OpenPhase(
                num_turns=self.turns_per_hour*3,
            ),
            VetoDrawPhase(),
            CompPhase(
                name="Power of Veto Competition",
                prize=DefaultRole.POV,
                comp_ruleset=self.veto_comp_ruleset,
                allowed_roles=[
                    DefaultRole.HOH,
                    DefaultRole.NOMINEE,
                    DefaultRole.DRAWN_FOR_VETO,
                ]
            ),
            OpenPhase(
                num_turns=self.turns_per_hour*9,
            ),
            SleepPhase(),
            # Saturday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*16,
            ),
            SleepPhase(),
            # Sunday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*16,
            ),
            SleepPhase(),
            # Monday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*2,
            ),
            VetoPhase(),
            OpenPhase(
                num_turns=self.turns_per_hour*13,
            ),
            SleepPhase(),
            # Tuesday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*16,
            ),
            SleepPhase(),
            # Wednesday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*16,
            ),
            SleepPhase(),
            # Thursday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*7,
            ),
            EvictionVotePhase(),
        ]
        return super().model_post_init(context)

    def describe(self):
        return f'''
        {self.name}
        Schedule:
        {'\n    - '.join(phase.describe() for phase in self.schedule)}
        '''