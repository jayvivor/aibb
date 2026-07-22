# THE REF/REGISTRY SYSTEM, ISOLATED
#
# The problem it solves: the LLM can only emit JSON, but the Moves are built from
# full pydantic objects (Houseguests, Rooms, Conversations, Interactables). The
# model can't emit a whole DefaultHouseguest - and we wouldn't trust one it did
# emit - so it emits a *Ref* instead: a tiny model holding nothing but a name.
# The house owns the real objects, so the house is what turns Refs back into them.
#
# There are exactly three pieces:
#   1. `Ref` (base.py) - a Base subclass with a single `name` field and a
#      `resolve` method.
#   2. Per-subclass Refs - any Base subclass that the LLM needs to point at
#      declares its own nested `class Ref(Ref)`. The subclass adds nothing but
#      identity: `DefaultHouseguest.Ref` and `InteractiveRoom.Ref` are different
#      *types*, and that type is what the registry keys off of.
#   3. `Registry` (base.py) - just a type alias:
#          dict[type[Ref], dict[str, Base]]
#      i.e. "for this kind of Ref, here is the name -> object lookup."
#
# Resolution is one line (see Ref.resolve):
#          registry[type(self)][self.name]
# "Look up my own Ref type to find the right lookup table, then look up my name."
from __future__ import annotations
from aibb.base import Base, Ref, Registry


# A minimal Base subclass, with the same nested-Ref shape the real classes use.
# Inside the class body, `Ref` still refers to the imported base Ref, so
# `class Ref(Ref)` reads as "my own Ref, inheriting the base one".

class Pet(Base):
    name: str

    class Ref(Ref["Pet"]):
        pass

    def describe(self):
        return self.name


dog = Pet(name="Biscuit")
cat = Pet(name="Mochi")

# The registry maps the Ref TYPE to the lookup table for that type. In the real
# architecture the house builds this - see DefaultHouse.registry, which maps
# DefaultHouseguest.Ref / InteractiveRoom.Ref / Conversation.Ref /
# Interactable.Ref onto the house's name registries.
registry: Registry = {
    Pet.Ref: {dog.name: dog, cat.name: cat},
}

# This dict is what the LLM would actually emit, validated as a Ref field on a
# MoveResponse (e.g. `choice: DefaultHouseguest.Ref` in response.py).
ref = Pet.Ref(name="Biscuit")

resolved = ref.resolve(registry)
print(f"{ref.name!r} resolved to the {type(resolved).__name__} object: {resolved is dog}")


# THE SCOPING TRICK
#
# Nothing forces a registry to be complete. The house builds a *different*
# registry for every get_move call, containing only the legal choices for that
# decision. An eviction vote gets a registry holding just the nominees; a
# nomination gets the actives minus the HOH; the Open phase gets the actor's
# room-mates, the adjacent rooms, and the objects in the current room. This is
# what "the house knows which Refs to pass along" means in practice - and it's
# validation for free, because an illegal name simply isn't in the table:

eviction_registry: Registry = {
    Pet.Ref: {cat.name: cat},  # only the "nominee" is on the table
}

vote = Pet.Ref(name="Mochi")
print(f"legal vote resolves: {vote.resolve(eviction_registry) is cat}")

illegal_vote = Pet.Ref(name="Biscuit")
try:
    illegal_vote.resolve(eviction_registry)
except KeyError as error:
    print(f"illegal vote raises: KeyError({error})")


# WHERE THE SEAMS ARE IN THE REAL ARCHITECTURE
#
#   base.py       - Ref, Registry, and MoveResponse.get_move(self, registry)
#   houseguest.py - DefaultHouseguest.Ref     (and room.py, move.py, interaction.py
#                   for InteractiveRoom.Ref, Conversation.Ref, Interactable.Ref;
#                   Conversation.Ref resolves via ANY participant's name, since
#                   conversations have no name of their own)
#   response.py   - the Ref-typed payload fields, and get_move implementations
#                   that call ref.resolve(registry) while constructing the Move
#   house.py      - DefaultHouse.registry (the full table for the Open phase)
#                   and the scoped one-off registries built at each ceremony
#                   call site in process_phase_turn