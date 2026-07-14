from pydantic import Field

from aibb.base import Role, Memory, Houseguest, Status
from aibb.utils import *



__all__ = [
    "DefaultRole",
    "DefaultMemory",
    "DefaultHouseguest",
]



class DefaultRole(Role):
    HOH = "Head of Household"
    POV = "Power of Veto"
    NOMINEE = "Nominee"
    BLOCKBUSTER = "Blockbuster"
    HAVE_NOT = "Have-Not"


class DefaultMemory(Memory):
    content: str = Field(default_factory=str)

    def describe(self):
        return self.content


# TODO: Full-on RPG Mechanics over here

# class LaundryStatusValue(StatusValue):
#     CLEAN = "clean"
#     DIRTY = "dirty"

#     @property
#     def default_value(self):
#         return LaundryStatusValue.CLEAN


# class LaundryStatus(Status[LaundryStatusValue]):
    
#     def describe(self):
#         return f"Most of their clothing is {self.value.value}."



class DefaultHouseguest(Houseguest[DefaultMemory, Status]):
    memory: DefaultMemory = Field(default_factory=DefaultMemory)
    statuses: list[Status] = Field(default_factory=list)

    def get_roles(self):
        return [r.value for r in self.roles]

    def describe(self):
        return f"{self.name} ({listed(self.get_roles())})"