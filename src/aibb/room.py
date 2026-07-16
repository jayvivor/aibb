from pydantic import Field
from typing import TypeVar, Generic

from aibb.base import Room
from aibb.houseguest import DefaultHouseguest
from aibb.events import (
    RoomHistory, 
    JoinRoomEvent, 
    ExitRoomEvent,
    SpokenMessage,
    Interaction,
    ConversationHistory,
)
from aibb.interaction import (
    Interactable,
    Bed,
    Food,
    Fridge,
    Stove,
    Dishwasher,
    WashingMachine,
    Dryer,
    Couch,
    Pool,
    Sink,
    Dryer,
    Shower,
    Monitor,
)

__all__ = [
    "Bedroom",
    "Kitchen",
    "LaundryRoom",
    "LivingRoom",
    "Backyard",
    "ShowerRoom",
    "HohRoom",
]

I = TypeVar("I", bound=Interactable)

# Actual Rooms

class InteractiveRoom(Room[DefaultHouseguest], Generic[I]):

    interactables: list[I] = Field(default_factory=list)
    history: RoomHistory = Field(default_factory=RoomHistory)

    def add_event(self, event: JoinRoomEvent | ExitRoomEvent | SpokenMessage | Interaction | ConversationHistory):
        match event:
            case JoinRoomEvent():
                self.history.join_history.append(event)
            case ExitRoomEvent():
                self.history.exit_history.append(event)
            case SpokenMessage():
                self.history.speech_history.append(event)
            case Interaction():
                self.history.interaction_history.append(event)
            case ConversationHistory():
                self.history.conversation_history.append(event)


    def describe(self):
        description = f'''
        {self.name.upper()}
        {'\n'.join(i.describe() for i in self.interactables)}
        '''
        return description


class Bedroom(InteractiveRoom[Bed]):

    num_beds: int

    def model_post_init(self, context):
        self.interactables = [Bed(name=str(index)) for index in range(self.num_beds)]


class Kitchen(InteractiveRoom[Food | Fridge | Stove | Dishwasher]):

    name: str = "Kitchen"
    inventory: list[Food] = Field(default_factory=list)

    def model_post_init(self, context):
        self.interactables = [
            Fridge(
                name="Fridge",
                inventory=[food for food in self.inventory],
            ),
            Stove(),
            Dishwasher(),
        ]


class LaundryRoom(InteractiveRoom[WashingMachine | Dryer]):
    
    name: str = "Laundry Room"
    inventory: list[Food] = Field(default_factory=list)

    def model_post_init(self, context):
        self.interactables = [WashingMachine(), Dryer()]


class LivingRoom(InteractiveRoom[Couch]):

    name: str = "Living Room"

    def model_post_init(self, context):
        self.interactables = [Couch()]


class Backyard(InteractiveRoom[Pool]):

    name: str = "Backyard"

    def model_post_init(self, context):
        self.interactables = [Pool()]


class ShowerRoom(InteractiveRoom[Sink | Shower]):

    name: str = "Shower Room"

    def model_post_init(self, context):
        self.interactables = [Sink(), Shower()]


class HohRoom(InteractiveRoom[Monitor]):

    name: str = "Head of Household Room"

    def model_post_init(self, context):
        self.interactables = [Monitor()]