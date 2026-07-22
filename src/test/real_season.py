from pathlib import Path
from os import makedirs
from yaml import safe_dump

from aibb.houseguest import DefaultRole
from dummy import helpers
import aibb.helpers


house = helpers.get_default_house()

house.simulate_season()

dummy_path = Path("dumps/dummy")
makedirs(dummy_path, exist_ok=True)

makedirs(dummy_path / "hg", exist_ok=True)
for hg in house.cast:
    print(f"Dumping {hg.name}...")
    aibb.helpers.dump_model(hg, dummy_path / "hg" / f"{hg.name}.yaml")

makedirs(dummy_path / "week", exist_ok=True)
for w_ind, week in enumerate(house.schedule):
    week_dir = dummy_path / "week" / week.name.replace(" ","_")
    makedirs(week_dir, exist_ok=True)
    for p_ind, phase in enumerate(week.schedule):
        phase_filename = week_dir / f"{phase.name.replace(" ","_")}.yaml"
        phase_dict = {f"Turn {stamp.turn_number}": [e.model_dump(mode="json") for e in eventlist] for stamp, eventlist in house.history.items() if stamp.week_number == w_ind and stamp.phase_number == p_ind}
        with open(phase_filename, "w", encoding="utf-8") as phase_file:
            safe_dump(phase_dict, phase_file, indent=2)
            

winner = house.role_dict[DefaultRole.WINNER][0]
print(f"\nWinner: {winner.name}")
print(f"Finalists: {', '.join(hg.name for hg in house.role_dict[DefaultRole.ACTIVE])}")
print(f"Jury: {', '.join(hg.name for hg in house.jury)}")
print(f"Pre-jury: {', '.join(hg.name for hg in house.pre_jury)}")
print(f"Events recorded: {sum(len(events) for events in house.history.values())} across {len(house.history)} turns")