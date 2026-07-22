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


# def get_default_rooms() -> list[InteractiveRoom]:


def get_default_schedule(cast_size: int = len(DEFAULT_CAST)) -> list[aibb.core.DefaultWeek]:

    all_weeks = []
    for wk_number in range(cast_size - 3):
        all_weeks.append(aibb.core.StandardWeek(
            name=f"Week {wk_number+1}",
            hoh_comp_ruleset=DEFAULT_COMP_RULESET,
            veto_comp_ruleset=DEFAULT_COMP_RULESET, 
            )
        )
    all_weeks.append(aibb.core.FinaleWeek(hoh_comp_ruleset=DEFAULT_COMP_RULESET))
    return all_weeks



def get_default_house(cast=DEFAULT_CAST):

    living_room = aibb.core.LivingRoom()
    kitchen = aibb.core.Kitchen(
        inventory=[f.deepcopy() for f in DEFAULT_FRIDGE_INVENTORY],
    )
    backyard = aibb.core.Backyard()
    hoh_room = aibb.core.HohRoom()
    laundry_room = aibb.core.LaundryRoom(
        inventory=[f.deepcopy() for f in DEFAULT_PANTRY_INVENTORY],
    )
    shower_room = aibb.core.ShowerRoom()
    stairs = InteractiveRoom(name="stairs")
    hallway = InteractiveRoom(name="hallway")
    diary_room = aibb.core.DiaryRoom()

    bedrooms = [
        aibb.core.Bedroom(name="Lion Bedroom", num_beds=4),
        aibb.core.Bedroom(name="Panda Bedroom", num_beds=4),
        aibb.core.Bedroom(name="Wolf Bedroom", num_beds=4),
        aibb.core.Bedroom(name="Tiger Bedroom", num_beds=4),
    ]

    room_layout = {
        living_room: [kitchen, backyard, hallway],
        kitchen: [stairs, living_room, laundry_room],
        stairs: [hoh_room, kitchen],
        hoh_room: [stairs],
        hallway: [living_room, shower_room] + [bedroom for bedroom in bedrooms],
        shower_room: [hallway],
        backyard: [living_room],
        laundry_room: [kitchen],
        diary_room: [],
    }

    room_layout.update({bedroom: [hallway] for bedroom in bedrooms})

    rooms = [
        living_room,
        kitchen,
        backyard,
        hoh_room,
        stairs,
        hallway,
        laundry_room,
        shower_room,
        diary_room,
    ] + bedrooms

    house = aibb.core.DefaultHouse(
        cast=cast,
        rooms=rooms,
        room_layout=room_layout,
        schedule=get_default_schedule(cast_size=len(cast)),
    )

    return house


def dump_model(obj: Base, path: Path):
    with open(path, "w") as outfile:
        yaml.safe_dump(obj.model_dump(mode="json"), outfile)
    print(f"dumped to {path}")