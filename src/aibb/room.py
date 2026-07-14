from abc import ABC, abstractmethod
from pydantic import Field
from enum import Enum
from typing import TypeVar, Generic, get_args

from aibb.base import Base, Houseguest, Room
from aibb.message import EventMessage

__all__ = [
    "Bedroom",
    "Kitchen",
    "LaundryRoom",
    "LivingRoom",
    "Backyard",
    "ShowerRoom",
    "HohRoom",
]

# Interactions

class InteractionEventMessage(EventMessage):
    pass


class Action(Enum):

    @property
    def description(self) -> str:
        raise NotImplementedError

A = TypeVar("A", bound=Action)


class Interactable(Base, ABC, Generic[A]):
    name: str
    interactors: dict[A, list[Houseguest]] = Field(default_factory=dict)

    def model_post_init(self, context):
        annotation = type(self).model_fields["interactors"].annotation
        key_type, _ = get_args(annotation)  # e.g. (BedAction, list[Houseguest])
        if isinstance(key_type, type) and issubclass(key_type, Action):
            for action in key_type:
                self.interactors.setdefault(action, [])  # type: ignore
        else:
            raise TypeError(
                f"{type(self).__name__} must inherit from Interactable[SomeAction], "
                "not bare Interactable"
            )

    def interact(self, actor: Houseguest, action: A):
        pass

    def describe(self):
        description = self.name
        for a, hgs in self.interactors.items():
            for hg in hgs:
                description += a.description.format(actor=hg.name, object=self.name)
        return self.name
    
I = TypeVar("I", bound=Interactable)


# Bedroom

class BedAction(Action):
    SLEEP = "sleep"
    LOUNGE = "lounge"

    @property
    def description(self):
        mapping = {
            BedAction.SLEEP: "{actor} is sleeping on {object}",
            BedAction.LOUNGE: "{actor} is lounging on {object}",
        }
        return mapping[self]
    
class Bed(Interactable[BedAction]):
    name: str = "Bed"


# Kitchen

class FoodAction(Action):
    EAT = "eat"

    @property
    def description(self):
        mapping = {
            FoodAction.EAT: "{actor} is eating a {object}",
        }
        return mapping[self]

class Food(Interactable[FoodAction]):
    name: str
    quantity: int


class FridgeAction(Action):
    SEARCH = "search"

    @property
    def description(self):
        mapping = {
            FridgeAction.SEARCH: "{actor} is searching the {object}",
        }
        return mapping[self]

class Fridge(Interactable[FridgeAction]):
    name: str = "Fridge"
    inventory: list[Food]


class StoveAction(Action):
    COOK = "cook"
    BAKE = "bake"

    @property
    def description(self):
        mapping = {
            StoveAction.COOK: "{actor} is cooking on the {object}",
            StoveAction.BAKE: "{actor} is baking"
        }
        return mapping[self]

class Stove(Interactable[StoveAction]):
    name: str = "Stove"


class DishwasherAction(Action):
    WASH_DISHES = "wash dishes"

    @property
    def description(self):
        mapping = {
            DishwasherAction.WASH_DISHES: "{actor} is washing the dishes",
        }
        return mapping[self]

class Dishwasher(Interactable[DishwasherAction]):
    name: str = "Dishwasher"


# Storage/Laundry Room

class PantryAction(Action):
    SEARCH = "search"

    @property
    def description(self):
        mapping = {
            PantryAction.SEARCH: "{actor} is searching the {object}",
        }
        return mapping[self]

class Pantry(Interactable[PantryAction]):
    name: str = "Pantry"
    inventory: list[Food]


class WashingMachineAction(Action):
    WASH_CLOTHES = "wash clothes"

    @property
    def description(self):
        mapping = {
            WashingMachineAction.WASH_CLOTHES: "{actor} is washing clothes in the {object}",
        }
        return mapping[self]

class WashingMachine(Interactable[WashingMachineAction]):
    name: str = "Washing Machine"


class DryerAction(Action):
    DRY_CLOTHES = "dry clothes"

    @property
    def description(self):
        mapping = {
            DryerAction.DRY_CLOTHES: "{actor} is drying clothes in the {object}",
        }
        return mapping[self]

class Dryer(Interactable[DryerAction]):
    name: str = "Dryer"


# Living Room

class CouchAction(Action):
    SIT = "sit"
    LAY = "lay"

    @property
    def description(self):
        mapping = {
            CouchAction.SIT: "{actor} is sitting on the {object}",
            CouchAction.LAY: "{actor} is laying on the {object}",
        }
        return mapping[self]

class Couch(Interactable[CouchAction]):
    name: str = "Couch"


# Backyard

class PoolAction(Action):
    WADE = "wade"
    SIT = "sit"

    @property
    def description(self):
        mapping = {
            PoolAction.WADE: "{actor} is wading in the {object}",
            PoolAction.SIT: "{actor} is sitting by the {object}",
        }
        return mapping[self]

class Pool(Interactable[PoolAction]):
    name: str = "Pool"


# Shower Room

class SinkAction(Action):
    GROOM = "groom"
    BRUSHING_TEETH = "brushing teeth"

    @property
    def description(self):
        mapping = {
            SinkAction.GROOM: "{actor} is grooming (shaving/brushing hair, etc.)",
            SinkAction.BRUSHING_TEETH: "{actor} is brushing their teeth.",
        }
        return mapping[self]

class Sink(Interactable[SinkAction]):
    name: str = "Sink"


class ShowerAction(Action):
    SHOWER = "shower"

    @property
    def description(self):
        mapping = {
            ShowerAction.SHOWER: "{actor} is showering.",
        }
        return mapping[self]

class Shower(Interactable[ShowerAction]):
    name: str = "Shower"




# HoH Room

class MonitorAction(Action):
    MONITOR = "monitor"

    @property
    def description(self):
        mapping = {
            MonitorAction.MONITOR: "{actor} is monitoring the house.",
        }
        return mapping[self]

class Monitor(Interactable[MonitorAction]):
    name: str = "Monitor"




# Actual Rooms

class InteractiveRoom(Room, Generic[I]):

    interactables: list[I] = Field(default_factory=list)

    def describe(self):
        description = f'''
        {self.name.upper()}
        {'\n'.join(i.describe() for i in self.interactables)}
        '''
        return self.name


class Bedroom(InteractiveRoom[Bed]):

    num_beds: int

    def model_post_init(self, context):
        self.interactables = [Bed(name=str(index)) for index in range(self.num_beds)]


class Kitchen(InteractiveRoom[Food | Fridge | Stove | Dishwasher]):

    name: str = "Kitchen"
    inventory: list[Food]

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