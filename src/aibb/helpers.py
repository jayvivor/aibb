from pathlib import Path
import yaml

import aibb.core
from aibb.base import Base
from aibb.room import InteractiveRoom, Food


DEFAULT_COMP_RULESET = aibb.core.RandomCompRuleset()

DEFAULT_CAST = [
    aibb.core.DefaultHouseguest(
        name=name,
        model_id="N/A",
    )
    for name in [
        "Alice",
        "Bob",
        "Charlie",
        "Diane",
        "Edward",
        "Freya",
        "Georgia",
        "Harley",
        "Irene",
        "Josh",
        "Kayla",
        "Lando",
    ]
]

DEFAULT_FRIDGE_INVENTORY = [
    Food(name="Gallon of Milk", quantity=2),
    Food(name="Block of Cheese", quantity=2),
    Food(name="Eggs", quantity=12),
    Food(name="Butter", quantity=1),
    Food(name="Greek Yogurt", quantity=4),
    Food(name="Fresh Vegetables", quantity=5),
    Food(name="Deli Meat", quantity=1),
    Food(name="Orange Juice", quantity=1),
]

DEFAULT_PANTRY_INVENTORY = [
    Food(name="Pasta", quantity=3),
    Food(name="Rice", quantity=2),
    Food(name="Canned Beans", quantity=4),
    Food(name="Canned Tomatoes", quantity=3),
    Food(name="Cereal", quantity=2),
    Food(name="Bread", quantity=2),
    Food(name="Peanut Butter", quantity=1),
    Food(name="Flour", quantity=1),
    Food(name="Sugar", quantity=1),
    Food(name="Olive Oil", quantity=1),
]


def get_house(path: Path):
    with open(path, "r") as housefile:
        full_config = yaml.safe_load(housefile)
    house = aibb.core.DefaultHouse.model_validate(full_config)
    return house


def get_default_rooms() -> list[InteractiveRoom]:

    living_room = aibb.core.LivingRoom()
    kitchen = aibb.core.Kitchen(
        inventory=[f.deepcopy() for f in DEFAULT_FRIDGE_INVENTORY],
    )
    backyard = aibb.core.Backyard()
    hoh_room = aibb.core.HohRoom()
    laundry_room = aibb.core.LaundryRoom()
    shower_room = aibb.core.ShowerRoom()
    stairs = InteractiveRoom(name="stairs")
    hallway = InteractiveRoom(name="hallway")

    bedrooms = [
        aibb.core.Bedroom(name="Lion Bedroom", num_beds=4),
        aibb.core.Bedroom(name="Panda Bedroom", num_beds=4),
        aibb.core.Bedroom(name="Wolf Bedroom", num_beds=4),
        aibb.core.Bedroom(name="Tiger Bedroom", num_beds=4),
    ]

    living_room.doors = [kitchen, backyard, hallway]
    kitchen.doors = [stairs, living_room, laundry_room]
    stairs.doors = [hoh_room, kitchen]
    hoh_room.doors = [stairs]
    hallway.doors = [living_room, shower_room] + [bedroom for bedroom in bedrooms]  # type: ignore
    shower_room.doors = [hallway]
    for bedroom in bedrooms:
        bedroom.doors = [hallway]

    rooms = [
        living_room,
        kitchen,
        backyard,
        hoh_room,
        stairs,
        hallway,
    ] + bedrooms

    return rooms


def get_default_schedule(cast_size: int = len(DEFAULT_CAST)) -> list[aibb.core.DefaultWeek]:

    all_weeks = []

    all_weeks.append(aibb.core.FinaleWeek(hoh_comp_ruleset=DEFAULT_COMP_RULESET))
    for wk_number in range(cast_size - 3):
        all_weeks.append(aibb.core.StandardWeek(
            name=f"Week {wk_number+1}",
            hoh_comp_ruleset=DEFAULT_COMP_RULESET,
            veto_comp_ruleset=DEFAULT_COMP_RULESET, 
            )
        )
        # Start with finale night
    return all_weeks



def get_default_house():

    house = aibb.core.DefaultHouse(
        cast = DEFAULT_CAST,
        rooms = get_default_rooms(),
        schedule = get_default_schedule(),
    )

    return house


def dump_model(obj: Base, path: Path):
    with open(path, "w") as outfile:
        yaml.safe_dump(obj.model_dump(mode="json"), outfile)
    print(f"dumped to {path}")