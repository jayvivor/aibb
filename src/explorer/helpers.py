from dummy import helpers as dummy_helpers

from explorer.house import ExplorerHouse


def get_explorer_house() -> ExplorerHouse:
    house = dummy_helpers.get_default_house()
    return ExplorerHouse(**dict(house))
