from aibb.base import Audience, House, Room, Houseguest

__all__ = [
    "HouseAudience",
    "RoomAudience",
    "GroupAudience",
    "SoloAudience",
    "CompositeAudience",
]

class HouseAudience(Audience):
    house: House

    def get_members(self):
        return set(self.house.cast)


class RoomAudience(Audience):
    room: Room

    def get_members(self):
        return set(self.room.members)


class GroupAudience(Audience):
    group: list[Houseguest]

    def get_members(self):
        return set(self.group)


class SoloAudience(Audience):
    houseguest: Houseguest

    def get_members(self):
        return {self.houseguest}


class CompositeAudience(Audience):
    audiences: list[Audience]

    def get_members(self):
        members = set()
        for aud in self.audiences:
            for member in aud.get_members():
                members.add(member)
        return members