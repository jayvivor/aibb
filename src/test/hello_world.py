import aibb.helpers
from pathlib import Path



house = aibb.helpers.get_default_house(cast=aibb.helpers.DUMMY_CAST)

# aibb.helpers.dump_model(house, Path("dumps/house.yaml"))

house.simulate_season()

aibb.helpers.dump_model(house, Path("dumps/house_post_run.yaml"))