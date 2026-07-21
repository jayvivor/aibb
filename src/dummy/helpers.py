import random

from aibb import helpers as aibb_helpers
from dummy import pools, core

def get_random_cast(size: int=16):
    return [core.DummyHouseguest(name=random.choice(pools.NAMES)) for _ in range(size)]


def get_default_house():
    house = aibb_helpers.get_default_house(cast=get_random_cast())
    return house