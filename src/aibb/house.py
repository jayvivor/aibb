from pydantic import Field
from typing import Optional

from aibb.base import House
from aibb.houseguest import DefaultHouseguest
from aibb.room import InteractiveRoom
from aibb.week import DefaultWeek, DefaultPhase
from aibb.move import DefaultMove, SpeakMove
from aibb.turn import (
    DefaultTurn,
    OpenTurn,
    SchemeTurn,
    EvictionVoteTurn,
    TurnResult,
)
from aibb.events import GameEvent, EvictionResultEvent
from aibb.prompts import BASE_PROMPT_TEMPLATE, MESSAGE_TEMPLATE, RULES
from aibb.utils import get_client


__all__ = [
    "DefaultHouse",
]






class DefaultHouse(House[DefaultHouseguest, InteractiveRoom, DefaultWeek, DefaultTurn]):

    name: str = "Big Brother House"
    room_layout: dict[InteractiveRoom, list[InteractiveRoom]] = Field(default_factory=dict, exclude=True)
    pre_jury: list[DefaultHouseguest] = Field(default_factory=list)
    jury: list[DefaultHouseguest] = Field(default_factory=list)
    jury_size: int = 7
    num_finalists: int = 2

    _current_week: Optional[DefaultWeek] = Field(default=None, exclude=True)
    _current_phase: Optional[DefaultPhase] = Field(default=None, exclude=True)
    
    def describe(self):
        description = f'''
        The Big Brother House.

        Cast: 
            {'\n'.join([hg.describe() for hg in self.cast])}
        '''

        return description
    
    def evict(self, hg: DefaultHouseguest):
        room = self.get_hg_room(hg=hg)
        room.members.remove(hg)
        hgs = self.get_active_hgs()
        if len(hgs) >= self.num_finalists + self.jury_size:
            self.pre_jury.append(hg)
        else:
            self.jury.append(hg)

    def get_hg_room(self, hg: DefaultHouseguest):
        for room in self.rooms:
            if hg in room.members:
                return room
        raise ValueError(f"Houseguest {hg.name} not found in any rooms")
    

    def process_event(self, event: GameEvent):

        match event:
            case EvictionResultEvent():
                self.evict(event.evicted)
            case _:
                return
            
    def get_status(self, turn: DefaultTurn, hg: DefaultHouseguest) -> str:
        status_items: list[str] = []
        hgs = self.get_active_hgs()
        status_items.append(f"Houseguests remaining: ")
        for houseguest in hgs:
            if houseguest != hg:
                status_items.append(f" - {houseguest.name}")
            else:
                status_items.append(f" - {houseguest.name} (you)")
        match turn:
            case SchemeTurn():
                status_items.append("Context (anything not saved to memory will be wiped): ")
            case OpenTurn():
                status_items.append("Context: ")
                
        for event in hg.history:
                    status_items.append(f" - {event.narrate(hg)}")
        
        return "\n".join(status_items)


    def get_week(self, turn: DefaultTurn) -> DefaultWeek:

        # Try caching
        if self._current_week and self.get_phase(turn) in self._current_week.schedule:
            return self._current_week
        
        for week in self.schedule:
            for phase in week.schedule:
                if turn in phase.turns:
                    self._current_phase = phase
                    self._current_week = week
                    return week
        
        raise ValueError("Turn not found in any week")
    

    def get_phase(self, turn: DefaultTurn) -> DefaultPhase:

        # Try caching
        if self._current_phase and turn in self._current_phase.turns:
            return self._current_phase
        
        for week in self.schedule:
            for phase in week.schedule:
                if turn in phase.turns:
                    self._current_phase = phase
                    self._current_week = week
                    return phase
        
        raise ValueError("Turn not found in any phase")

    
    def get_hg_move(self, turn, hg):

        # Get prompt
        system_prompt = BASE_PROMPT_TEMPLATE.format(
            rules=RULES,
            schedule=self.get_week(turn).info,
            phase_info=self.get_phase(turn).info,
            turn_info=turn.info,
        )

        user_message = MESSAGE_TEMPLATE.format(
            scratchpad=hg.memory.content,
            house_status=self.get_status(turn, hg),
            options=turn.get_options(),
        )

        choice = hg.get_chat_response(
            client=get_client(), 
            prompt=system_prompt, 
            user_message=user_message,
            response_type=DefaultMove,
            )

        # match turn.turn_type:
        #     case DefaultTurnType.SCHEME:
        #         pass
        #     case DefaultTurnType.OPEN:
        #         pass
        #     case DefaultTurnType.COMP:
        #         pass
        #     case DefaultTurnType.VOTE:
        #         pass
        #     case DefaultTurnType.EVICTION:
        #         pass
        #     case DefaultTurnType.NOMINATION:
        #         pass
        #     case DefaultTurnType.VETO:
        #         pass
        #     case DefaultTurnType.JURY_VOTE:
        #         pass

        return SpeakMove(actor=hg, content="Howdy, World!")
    
    
    def run_turn(self, turn: DefaultTurn) -> DefaultTurn:
        turn_result: TurnResult[GameEvent] = turn.execute()

        events: list[GameEvent] = []
        for event_list in turn_result.events.values():
            events.extend(event_list)

        for event in events:
            self.process_event(event)
        
        return turn