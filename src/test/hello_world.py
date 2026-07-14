import aibb.helpers
from pathlib import Path



house = aibb.helpers.get_default_house()

aibb.helpers.dump_model(house, Path("dumps/house.yaml"))