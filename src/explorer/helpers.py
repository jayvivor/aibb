from typing import Optional

import yaml

from aibb import helpers as aibb_helpers
from aibb.houseguest import DefaultHouseguest
from dummy import helpers as dummy_helpers

from explorer.house import ExplorerHouse


def get_cast(path: str) -> list[DefaultHouseguest]:
    with open(path) as file:
        config = yaml.safe_load(file)
    defaults = config.get("defaults", {})
    return [DefaultHouseguest(**(defaults | entry)) for entry in config["cast"]]


def get_explorer_house(cast_path: Optional[str]=None) -> ExplorerHouse:
    if cast_path:
        house = aibb_helpers.get_default_house(cast=get_cast(cast_path))
    else:
        house = dummy_helpers.get_default_house()
    return ExplorerHouse(**dict(house))