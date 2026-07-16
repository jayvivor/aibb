import aibb.helpers
from pathlib import Path



house = aibb.helpers.get_default_house()

# aibb.helpers.dump_model(house, Path("dumps/house.yaml"))

house.run()

aibb.helpers.dump_model(house, Path("dumps/house_post_run.yaml"))