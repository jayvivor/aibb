from __future__ import annotations
from pydantic import Field
from typing import ClassVar

from aibb.base import Week, Phase, CompRuleset
from aibb.houseguest import DefaultRole


__all__ = [
    "OpenPhase",
    "CompPhase",
    "SleepPhase",
    "CeremonyPhase",
    "DefaultWeek",
    "FinaleWeek",
    "StandardWeek",
]


class DefaultPhase(Phase):

    info: ClassVar[str]

    def describe(self):
        raise NotImplementedError

OPEN_PHASE_INFO = '''
This is the "Open" Phase. You are free to explore and converse with other houseguests.
'''

class OpenPhase(DefaultPhase):
    name: str = "Open"
    num_turns: int
    info: ClassVar[str] = OPEN_PHASE_INFO

    def describe(self):
        return f'''Open phase ({self.num_turns} turns)'''


COMP_PHASE_INFO = '''
This is the "Competition" phase. You are competing for a prize.
'''
    
class CompPhase(DefaultPhase):
    comp_ruleset: CompRuleset
    prize: DefaultRole
    allowed_roles: list[DefaultRole]
    disallowed_roles: list[DefaultRole] = Field(default_factory=list)
    info: ClassVar[str] = COMP_PHASE_INFO

    def describe(self):
        return f"Comp phase (Prize: {self.prize.value})"
    

SLEEP_PHASE_INFO = '''
The house is "asleep". You will all "wake" at the same time.
'''
  

class SleepPhase(DefaultPhase):
    name: str = "End of Day"
    info: ClassVar[str] = SLEEP_PHASE_INFO


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


VETO_PHASE_INFO = '''
This is a "Veto" Phase.
'''

class VetoPhase(CeremonyPhase):
    name: str = "Veto Ceremony"
    info: ClassVar[str] = VETO_PHASE_INFO


EVICTION_PHASE_INFO = '''
This is an "Eviction" Phase.
'''

class EvictionVotePhase(CeremonyPhase):
    name: str = "Live Vote and Eviction"
    info: ClassVar[str] = EVICTION_PHASE_INFO


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
            CeremonyPhase(
                name="Final 3 Eviction",
            ),
            CeremonyPhase(
                name="Jury Vote",
            )            
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
            CeremonyPhase(
                name="Veto Draw",
            ),
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
        return super().model_post_init(context)

    def describe(self):
        return f'''
        {self.name}
        Schedule:
        {'\n    - '.join(phase.describe() for phase in self.schedule)}
        '''