from pydantic import Field

from aibb.base import Week, Phase, TurnType, CompRuleset
from aibb.base import Role
from aibb.houseguest import DefaultRole


__all__ = [
    "DefaultTurnType",
    "OpenPhase",
    "CompPhase",
    "SleepPhase",
    "CeremonyPhase",
    "DefaultWeek",
    "FinaleWeek",
    "StandardWeek",
]



class DefaultTurnType(TurnType):
    SCHEME = "Scheme"
    OPEN = "Open"
    COMP = "Comp"
    VOTE = "Vote"
    EVICTION = "Eviction"
    NOMINATION = "Nomination"
    VETO = "Veto"
    JURY_VOTE = "Jury Vote"

    @property
    def description(self):
        mapping = {
            DefaultTurnType.SCHEME: "Houseguests make and review plans for future rounds.",
            DefaultTurnType.OPEN: "Houseguests are permitted to openly mingle.",
            DefaultTurnType.COMP: "Houseguests are competing for a prize.",
            DefaultTurnType.VOTE: "Houseguests are voting to evict.",
            DefaultTurnType.VOTE: "Houseguests are voting to select a winner.",
            DefaultTurnType.EVICTION: "Houseguests are saying their goodbyes to the evicted houseguest.",
            DefaultTurnType.NOMINATION: "Houseguests are nominating for eviction.",
            DefaultTurnType.VETO: "Houseguests are attending the veto meeting.",
        }
        return mapping[self]


class DefaultPhase(Phase):
    turn_type: DefaultTurnType

    def describe(self):
        return self.turn_type.description


class OpenPhase(DefaultPhase):
    name: str = "Open"
    turn_type: DefaultTurnType = DefaultTurnType.OPEN
    num_turns: int

    def describe(self):
        return f'''{self.turn_type.description} ({self.num_turns} turns)'''
    
    
class CompPhase(DefaultPhase):
    turn_type: DefaultTurnType = DefaultTurnType.COMP
    comp_ruleset: CompRuleset
    prize: Role

    def describe(self):
        return f"{self.turn_type.description} (Prize: {self.prize.value})"
    

class SleepPhase(DefaultPhase):
    name: str = "End of Day"
    turn_type: DefaultTurnType = DefaultTurnType.SCHEME


class CeremonyPhase(DefaultPhase):
    name: str = "Ceremony"



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


class DefaultWeek(Week[DefaultPhase]):
    schedule: list[DefaultPhase] = Field(default_factory=list)


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
                turn_type=DefaultTurnType.EVICTION,
            ),
            CeremonyPhase(
                name="Jury Vote",
                turn_type=DefaultTurnType.JURY_VOTE,
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
                turn_type=DefaultTurnType.NOMINATION,
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
            DefaultPhase(
                name="Veto Meeting",
                turn_type=DefaultTurnType.VETO,
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
            CeremonyPhase(
                name="Eviction Vote",
                turn_type=DefaultTurnType.VOTE,
            ),
            CeremonyPhase(
                name="Live Eviction",
                turn_type=DefaultTurnType.EVICTION,
            ),
        ]

    def describe(self):
        return f'''
        {self.name}
        Schedule:
        {'\n    - '.join(phase.describe() for phase in self.schedule)}
        '''