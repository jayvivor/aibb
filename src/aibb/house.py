from pydantic import Field

from aibb.base import House
from aibb.houseguest import DefaultHouseguest
from aibb.room import InteractiveRoom
from aibb.week import DefaultWeek
from aibb.move import SpeakMove



__all__ = [
    "DefaultHouse",
]



class DefaultHouse(House[DefaultHouseguest, InteractiveRoom, DefaultWeek]):

    room_layout: dict[InteractiveRoom, list[InteractiveRoom]] = Field(default_factory=dict)
    
    def describe(self):
        description = f'''
        The Big Brother House.

        Cast: 
            {'\n'.join([hg.describe() for hg in self.cast])}
        '''

        return description
    
    def get_hg_turn(self, turn, hg):
        return SpeakMove(actor=hg, content="Howdy, World!")