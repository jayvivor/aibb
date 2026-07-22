from aibb.houseguest import DefaultRole
from dummy import helpers



house = helpers.get_default_house()

house.simulate_season()

winner = house.role_dict[DefaultRole.WINNER][0]
print(f"\nWinner: {winner.name}")
print(f"Finalists: {', '.join(hg.name for hg in house.role_dict[DefaultRole.ACTIVE])}")
print(f"Jury: {', '.join(hg.name for hg in house.jury)}")
print(f"Pre-jury: {', '.join(hg.name for hg in house.pre_jury)}")
print(f"Events recorded: {sum(len(events) for events in house.history.values())} across {len(house.history)} turns")