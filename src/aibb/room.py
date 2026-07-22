from __future__ import annotations
from pydantic import Field
from typing import TypeVar, Generic

from aibb.base import Room, Ref
from aibb.interaction import (
    Interactable,
    Bed,
    Food,
    Fridge,
    Pantry,
    Stove,
    Dishwasher,
    WashingMachine,
    Dryer,
    Couch,
    Pool,
    Sink,
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
    "DiaryRoom",
]


class NullInteractable(Interactable):
    pass

I = TypeVar("I", bound=Interactable)


# Actual Rooms

class InteractiveRoom(Room, Generic[I]):

    interactables: list[I] = Field(default_factory=list)

    class Ref(Ref["InteractiveRoom"]):
        name: str = Field(description="The exact name of the room.")

    def describe(self):
        return self.name


class Bedroom(InteractiveRoom[Bed]):

    num_beds: int

    def model_post_init(self, context):
        self.interactables = [Bed(name=str(index)) for index in range(self.num_beds)]
        return super().model_post_init(context)


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
        return super().model_post_init(context)


class LaundryRoom(InteractiveRoom[WashingMachine | Dryer | Pantry]):
    
    name: str = "Laundry Room"
    inventory: list[Food] = Field(default_factory=list)

    def model_post_init(self, context):
        self.interactables = [
            Pantry(
                name="Pantry",
                inventory=[food for food in self.inventory],
            ),
            WashingMachine(),
            Dryer(),
        ]
        return super().model_post_init(context)


class LivingRoom(InteractiveRoom[Couch]):

    name: str = "Living Room"

    def model_post_init(self, context):
        self.interactables = [Couch()]
        return super().model_post_init(context)


class Backyard(InteractiveRoom[Pool]):

    name: str = "Backyard"

    def model_post_init(self, context):
        self.interactables = [Pool()]
        return super().model_post_init(context)


class ShowerRoom(InteractiveRoom[Sink | Shower]):

    name: str = "Shower Room"

    def model_post_init(self, context):
        self.interactables = [Sink(), Shower()]
        return super().model_post_init(context)


class HohRoom(InteractiveRoom[Monitor]):

    name: str = "Head of Household Room"

    def model_post_init(self, context):
        self.interactables = [Monitor()]
        return super().model_post_init(context)
    

class DiaryRoom(InteractiveRoom[NullInteractable]):

    name: str = "Diary Room"