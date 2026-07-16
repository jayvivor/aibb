from pydantic import Field
from typing import TypeVar, Generic

from aibb.base import Week, Phase, TurnType, CompRuleset
from aibb.base import Role
from aibb.houseguest import DefaultRole, DefaultHouseguest
from aibb.turn import DefaultTurn, OpenTurn, CompTurn, EvictionVoteTurn, SchemeTurn


__all__ = [
    # "DefaultTurnType",
    "OpenPhase",
    "CompPhase",
    "SleepPhase",
    "CeremonyPhase",
    "DefaultWeek",
    "FinaleWeek",
    "StandardWeek",
]



# class DefaultTurnType(TurnType):
#     SCHEME = "Scheme"
#     OPEN = "Open"
#     COMP = "Comp"
#     VOTE = "Vote"
#     EVICTION = "Eviction"
#     NOMINATION = "Nomination"
#     VETO = "Veto"
#     JURY_VOTE = "Jury Vote"

#     @property
#     def description(self):
#         mapping = {
#             DefaultTurnType.SCHEME: "Houseguests make and review plans for future rounds.",
#             DefaultTurnType.OPEN: "Houseguests are permitted to openly mingle.",
#             DefaultTurnType.COMP: "Houseguests are competing for a prize.",
#             DefaultTurnType.VOTE: "Houseguests are voting to evict.",
#             DefaultTurnType.JURY_VOTE: "Houseguests are voting to select a winner.",
#             DefaultTurnType.EVICTION: "Houseguests are saying their goodbyes to the evicted houseguest.",
#             DefaultTurnType.NOMINATION: "Houseguests are nominating for eviction.",
#             DefaultTurnType.VETO: "Houseguests are attending the veto meeting.",
#         }
#         return mapping[self]


# class DefaultPhase(Phase):
#     turn_type: DefaultTurnType

#     def describe(self):
#         return self.turn_type.description


# class OpenPhase(DefaultPhase):
#     name: str = "Open"
#     turn_type: DefaultTurnType = DefaultTurnType.OPEN
#     num_turns: int

#     def describe(self):
#         return f'''{self.turn_type.description} ({self.num_turns} turns)'''
    
# class CompPhase(DefaultPhase):
#     turn_type: DefaultTurnType = DefaultTurnType.COMP
#     comp_ruleset: CompRuleset
#     prize: Role

#     def describe(self):
#         return f"{self.turn_type.description} (Prize: {self.prize.value})"
    

# class SleepPhase(DefaultPhase):
#     name: str = "End of Day"
#     turn_type: DefaultTurnType = DefaultTurnType.SCHEME


# class CeremonyPhase(DefaultPhase):
#     name: str = "Ceremony"



# TODO: Era-specific expansions
# class EraWeek(Week):
#     pass

# EW = TypeVar("EW", bound=EraWeek)


# class MidEraWeek(EraWeek):
#     hoh_comp: CompRuleset
#     veto_comp: 


# class DoubleEvictionWeek(Week):
#     hoh_comp: CompRuleset
#     veto_comp: 

DT = TypeVar("DT", bound=DefaultTurn)


class DefaultPhase(Generic[DT], Phase[DT]):

    def describe(self):
        raise NotImplementedError
    
    @property
    def info(self):
        raise NotImplementedError


OPEN_PHASE_INFO = '''
This is the "Open" Phase. You are free to explore and converse with other houseguests.
'''

class OpenPhase(DefaultPhase[OpenTurn]):
    name: str = "Open"
    num_turns: int

    def describe(self):
        return f'''Open phase ({self.num_turns} turns)'''
    
    @property
    def info(self):
        return OPEN_PHASE_INFO


COMP_PHASE_INFO = '''
This is the "Competition" phase. You are competing for a prize.
'''
    
class CompPhase(DefaultPhase[CompTurn]):
    comp_ruleset: CompRuleset
    prize: Role

    def describe(self):
        return f"Comp phase (Prize: {self.prize.value})"
    
    @property
    def info(self):
        return COMP_PHASE_INFO
    

SLEEP_PHASE_INFO = '''
The house is "asleep". You will all "wake" at the same time.
'''
  

class SleepPhase(DefaultPhase[SchemeTurn]):
    name: str = "End of Day"

    @property
    def info(self):
        return SLEEP_PHASE_INFO


CEREMONY_PHASE_INFO = '''
This is a "Ceremony" phase.
'''

class CeremonyPhase(Generic[DT], DefaultPhase[DT]):
    name: str = "Ceremony"

    @property
    def info(self):
        return CEREMONY_PHASE_INFO   


EVICTION_PHASE_INFO = '''
This is an "Eviction" Phase.
'''

class EvictionVotePhase(CeremonyPhase[EvictionVoteTurn]):
    name: str = "Live Vote and Eviction"
    nominees: list[DefaultHouseguest] = Field(default_factory=list)
    voters: list[DefaultHouseguest] = Field(default_factory=list)
    tiebreakers: list[DefaultHouseguest] = Field(default_factory=list)

    @property
    def info(self):  # type: ignore
        return EVICTION_PHASE_INFO



class DefaultWeek(Week[DefaultPhase]):
    schedule: list[DefaultPhase] = Field(default_factory=list)

    @property
    def info(self):
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
            ),
            CeremonyPhase(
                name="Final 3 Eviction",
            ),
            CeremonyPhase(
                name="Jury Vote",
            )            
        ]

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
            ),
            OpenPhase(
                num_turns=self.turns_per_hour*4,
            ),
            SleepPhase(),
            # Friday Morning
            OpenPhase(
                num_turns=self.turns_per_hour*2,
            ),
            CeremonyPhase(
                name="Nomination Ceremony",
            ),
            OpenPhase(
                num_turns=self.turns_per_hour*3,
            ),
            CompPhase(
                name="Power of Veto Competition",
                prize=DefaultRole.POV,
                comp_ruleset=self.veto_comp_ruleset,
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
            CeremonyPhase(
                name="Veto Meeting",
            ),
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
            EvictionVotePhase(
                name="Eviction Vote",
            ),
            CeremonyPhase(
                name="Live Eviction",
            ),
        ]

    def describe(self):
        return f'''
        {self.name}
        Schedule:
        {'\n    - '.join(phase.describe() for phase in self.schedule)}
        '''