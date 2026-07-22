from pydantic import Field

from aibb.core import DefaultHouse
from aibb.week import DefaultWeek, DefaultPhase, PhaseStatus
from aibb.events import DefaultTimestamp, DefaultGameEvent


class SimStopped(Exception):
    pass


class ExplorerHouse(DefaultHouse):

    stop_requested: bool = Field(default=False, exclude=True)

    def process_phase_turn(self, week: DefaultWeek, phase: DefaultPhase, timestamp: DefaultTimestamp, status: PhaseStatus) -> list[DefaultGameEvent]:
        if self.stop_requested:
            raise SimStopped(f"Season stopped at {timestamp.describe()}")
        return super().process_phase_turn(week, phase, timestamp, status)
