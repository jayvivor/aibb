import random

from pydantic import Field
from typing import Optional, Mapping, cast

from aibb import core
from aibb.base import Ref, Registry, B
from aibb.houseguest import DefaultMemory
from aibb.interaction import Interactable
from aibb.room import InteractiveRoom
from dummy import pools

__all__ = [
    "DummyHouseguest",
]

# FIX: Feel free to rewrite this to match implemented patterns; it's just a guideline.


# Dummy responses skip the LLM entirely: DummyHouseguest constructs them directly, and
# each one overrides get_move to build a random-but-valid move out of whatever the house
# passed in its registry. The house scopes each registry to the legal choices, so a
# random pull from it is always a legal play.

def table(registry: Registry, ref_type: type[Ref[B]]) -> Mapping[str, B]:
    return cast(Mapping[str, B], registry[ref_type])


class DummyResponse(core.DefaultMoveResponse):
    pass


class DummyOpenMoveResponse(core.OpenMoveResponse, DummyResponse):

    def get_move(self, registry: Registry) -> core.DefaultMove:
        actor = self.actor
        neighbor_hgs = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        rooms = [room for room in table(registry, InteractiveRoom.Ref).values()]
        interactables = [interactable for interactable in table(registry, Interactable.Ref).values()]
        convo_map = table(registry, core.Conversation.Ref)

        actor_convo = convo_map.get(actor.name)
        roll = random.random()

        if actor_convo:
            if roll < 0.4:
                return core.WhisperMove(
                    actor=actor,
                    content=random.choice(pools.PLATITUDES),
                    allow_join=random.random() < 0.5,
                )
            if roll < 0.5:
                return core.ExitConversationMove(actor=actor, conversation=actor_convo)
        else:
            free_hgs = [hg for hg in neighbor_hgs if hg.name not in convo_map]
            if roll < 0.1 and free_hgs:
                return core.StartConversationMove(actor=actor, participants=random.sample(free_hgs, k=1))
            if roll < 0.15 and convo_map:
                return core.JoinConversationMove(
                    actor=actor,
                    conversation=random.choice([convo for convo in convo_map.values()]),
                )
        if roll < 0.65:
            return core.SpeakMove(actor=actor, content=random.choice(pools.PLATITUDES))
        if roll < 0.8 and rooms:
            return core.ChangeRoomMove(actor=actor, room=random.choice(rooms))
        if roll < 0.9 and interactables:
            interactable = random.choice(interactables)
            action = random.choice([action for action in interactable.interactors])
            return core.InteractMove(actor=actor, interactable=interactable, action=action)
        return core.SpeakMove(actor=actor, content=random.choice(pools.PLATITUDES))


class DummyEffortMoveResponse(core.EffortMoveResponse, DummyResponse):

    effort: int = 0

    def get_move(self, registry: Registry) -> core.EffortMove:
        return core.EffortMove(actor=self.actor, effort=random.randint(1, 100))


class DummySchemeMoveResponse(core.SchemeMoveResponse, DummyResponse):

    updated_scratchpad: str = ""

    def get_move(self, registry: Registry) -> core.SchemeMove:
        return core.SchemeMove(
            actor=self.actor,
            updated_memory=DefaultMemory(content=random.choice(pools.PLATITUDES)),
        )


class DummyNominationMoveResponse(core.NominationMoveResponse, DummyResponse):

    nominees: list[core.DefaultHouseguest.Ref] = Field(default_factory=list)

    def get_move(self, registry: Registry) -> core.NominationMove:
        nominatables = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        return core.NominationMove(actor=self.actor, nominees=random.sample(nominatables, k=2))


class DummyVetoMoveResponse(core.VetoMoveResponse, DummyResponse):

    def get_move(self, registry: Registry) -> core.VetoMove:
        noms = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        if random.random() < 0.5:
            return core.VetoMove(actor=self.actor, choice=random.choice(noms))
        return core.VetoMove(actor=self.actor, choice=None)


class DummyReplacementNomineeMoveResponse(core.ReplacementNomineeMoveResponse, DummyResponse):

    choice: Optional[core.DefaultHouseguest.Ref] = None

    def get_move(self, registry: Registry) -> core.ReplacementNomineeMove:
        replaceables = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        return core.ReplacementNomineeMove(actor=self.actor, choice=random.choice(replaceables))


class DummyVetoDrawChoiceMoveResponse(core.VetoDrawChoiceMoveResponse, DummyResponse):

    choice: Optional[core.DefaultHouseguest.Ref] = None

    def get_move(self, registry: Registry) -> core.VetoDrawChoiceMove:
        choosables = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        return core.VetoDrawChoiceMove(actor=self.actor, choice=random.choice(choosables))


class DummyEvictionVoteMoveResponse(core.EvictionVoteMoveResponse, DummyResponse):

    choice: Optional[core.DefaultHouseguest.Ref] = None

    def get_move(self, registry: Registry) -> core.EvictionVoteMove:
        noms = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        return core.EvictionVoteMove(actor=self.actor, choice=random.choice(noms))


class DummyJuryVoteMoveResponse(core.JuryVoteMoveResponse, DummyResponse):

    choice: Optional[core.DefaultHouseguest.Ref] = None

    def get_move(self, registry: Registry) -> core.JuryVoteMove:
        finalists = [hg for hg in table(registry, core.DefaultHouseguest.Ref).values()]
        return core.JuryVoteMove(actor=self.actor, choice=random.choice(finalists))


DUMMY_RESPONSES: dict[type[core.DefaultMoveResponse], type[DummyResponse]] = {
    core.OpenMoveResponse: DummyOpenMoveResponse,
    core.EffortMoveResponse: DummyEffortMoveResponse,
    core.SchemeMoveResponse: DummySchemeMoveResponse,
    core.NominationMoveResponse: DummyNominationMoveResponse,
    core.VetoMoveResponse: DummyVetoMoveResponse,
    core.ReplacementNomineeMoveResponse: DummyReplacementNomineeMoveResponse,
    core.VetoDrawChoiceMoveResponse: DummyVetoDrawChoiceMoveResponse,
    core.EvictionVoteMoveResponse: DummyEvictionVoteMoveResponse,
    core.JuryVoteMoveResponse: DummyJuryVoteMoveResponse,
}


class DummyHouseguest(core.DefaultHouseguest):

    model_id: str = "N/A"

    def get_move[R: core.DefaultMoveResponse](self, prompt: str, user_message: str, response_type: type[R]) -> R: # type: ignore
        dummy_type = DUMMY_RESPONSES[response_type]
        return dummy_type(
            selection_id="Dummy",
            explanation=random.choice(pools.PLATITUDES),
            actor=self,
        ) # type: ignore
            # TODO: fix this