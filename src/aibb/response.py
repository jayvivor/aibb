from __future__ import annotations
from typing import ClassVar, Optional, Union, get_args, get_origin
from types import UnionType
from pydantic import Field
from pydantic.json_schema import GenerateJsonSchema

from aibb.base import MoveResponse, Registry, Ref
from aibb.houseguest import DefaultHouseguest, DefaultMemory
from aibb.room import InteractiveRoom
from aibb.interaction import Interactable
from aibb.move import (
    DefaultMove,
    Conversation,
    SpeakMove,
    WhisperMove,
    StartConversationMove,
    JoinConversationMove,
    ExitConversationMove,
    ChangeRoomMove,
    InteractMove,
    EndInteractionMove,
    EvictionVoteMove,
    JuryVoteMove,
    SchemeMove,
    NominationMove,
    EffortMove,
    VetoMove,
    ReplacementNomineeMove,
    VetoDrawChoiceMove,
)


__all__ = [
    "DefaultMoveResponse",
    "OpenMoveResponse",
    "EffortMoveResponse",
    "EvictionVoteMoveResponse",
    "JuryVoteMoveResponse",
    "SchemeMoveResponse",
    "NominationMoveResponse",
    "VetoMoveResponse",
    "ReplacementNomineeMoveResponse",
    "VetoDrawChoiceMoveResponse",
]


# FIX: Use a ref/registry pattern. Create a per-Base-subclass `Ref` class 
# (ex: DefaultHouseguest gets its own `class Ref(Ref):` definition), and the house
# has a registry for resolving refs to their objects. This way, the house "knows" which
# Refs/literals to pass along to the `get_move` for the hg.
# Special request for this one - create a `ref_demo.py` SPECIFICALLY for isolating and
# explaining the ref/registry system that you choose to implement. This has the greatest potential
# for violating the established style, so I want to fully understand it when reading it.
# Despite the name, this doesn't actually have to be a _demo_ in the traditional sense; I just
# need to see the mechanics of it isolated from the rest of the architecture.


class DefaultMoveResponse(MoveResponse[DefaultHouseguest, DefaultMove]):

    explanation: str = Field(description="Your private explanation for the move; nobody else in the game will see this.")
    
    valid_move_types: ClassVar[list[type[DefaultMove]]]

    #TODO: Instead of inferring options from get_options, both this and get_options should use some sort of resolver
    @classmethod
    def get_ref_property(cls, annotation, registry: Registry) -> Optional[dict]:
        # Unwraps Optional[Ref], list[Ref], and Optional[list[Ref]] down to an
        # inline schema whose `name` is constrained to what would actually resolve
        if get_origin(annotation) in (Union, UnionType):
            for arg in get_args(annotation):
                ref_property = cls.get_ref_property(arg, registry)
                if ref_property:
                    return ref_property
            return None
        if get_origin(annotation) is list:
            item_property = cls.get_ref_property(get_args(annotation)[0], registry)
            if item_property:
                return {"type": "array", "items": item_property}
            return None
        if isinstance(annotation, type) and issubclass(annotation, Ref):
            names = [name for name in registry.get(annotation, {})]
            if not names:
                return None
            return {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": names,
                        "description": annotation.model_fields["name"].description,
                    },
                },
                "required": ["name"],
            }
        return None

    @classmethod
    def get_schema_generator(cls, response_type: type[DefaultMoveResponse], hg: DefaultHouseguest, registry: Optional[Registry]) -> type[GenerateJsonSchema]:

        if not registry:
            return GenerateJsonSchema

        class FilteredJsonSchema(GenerateJsonSchema):

            def generate(self, schema, mode="validation"):
                json_schema = super().generate(schema, mode=mode)

                # get_option is the availability oracle, same as options()
                available = [
                    move_type for move_type in response_type.valid_move_types
                    if move_type.get_option(hg, registry)
                ]
                keep = {"selection_id", "explanation"}
                for move_type in available:
                    keep.update(move_type.model_fields)
                keep.discard("actor")

                properties = {}
                for name, field_schema in json_schema.get("properties", {}).items():
                    if name not in keep:
                        continue
                    annotation = response_type.model_fields[name].annotation
                    properties[name] = cls.get_ref_property(annotation, registry) or field_schema

                properties["selection_id"]["enum"] = [move_type.selection_id for move_type in available]
                json_schema["properties"] = properties
                json_schema["required"] = [name for name in json_schema.get("required", []) if name in properties]
                json_schema.pop("$defs", None)
                return json_schema

        return FilteredJsonSchema

    @classmethod
    def get_schema(cls, hg: DefaultHouseguest, registry: Optional[Registry]) -> dict:
        return cls.model_json_schema(schema_generator=cls.get_schema_generator(cls, hg, registry))

    @classmethod
    def options(cls, hg: DefaultHouseguest, registry: Registry) -> str:
        option_lines = []
        for move_type in cls.valid_move_types:
            option = move_type.get_option(hg, registry)
            if option:
                option_lines.append(option)
        return "\n".join(option_lines)

    def get_move_type(self) -> type[DefaultMove]:
        for move_type in self.valid_move_types:
            if move_type.selection_id == self.selection_id:
                return move_type
        raise ValueError(f"'{self.selection_id}' is not a valid selection for {type(self).__name__}.")

    def describe(self):
            raise NotImplementedError


OPEN_MOVES: list[type[DefaultMove]] = [
    SpeakMove, 
    WhisperMove, 
    StartConversationMove,
    JoinConversationMove,
    ExitConversationMove,
    ChangeRoomMove,
    InteractMove,
    EndInteractionMove,
]

class OpenMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = OPEN_MOVES

    content: Optional[str] = Field(default=None, description="What you say (for 'Speak' and 'Whisper').")
    allow_join: Optional[bool] = Field(default=None, description="Whether to go through with a 'Whisper' if someone joins the conversation this turn.")
    participants: Optional[list[DefaultHouseguest.Ref]] = Field(default=None, description="Who you pull aside (for 'Start Conversation').")
    conversation: Optional[Conversation.Ref] = Field(default=None, description="The conversation in question (for 'Join Ongoing Conversation' and 'Leave Conversation').")
    room: Optional[InteractiveRoom.Ref] = Field(default=None, description="The room to enter (for 'Change Rooms').")
    interactable: Optional[Interactable.Ref] = Field(default=None, description="The object in question (for 'Interact' and 'Stop Interacting').")
    action: Optional[str] = Field(default=None, description="What you do with the object (for 'Interact').")

    def get_move(self, registry: Registry) -> DefaultMove:
        assert(self.actor)
        match self.selection_id:
            case SpeakMove.selection_id:
                assert(self.content)
                return SpeakMove(actor=self.actor, content=self.content)
            case WhisperMove.selection_id:
                assert(self.content)
                return WhisperMove(actor=self.actor, content=self.content, allow_join=self.allow_join or False)
            case StartConversationMove.selection_id:
                assert(self.participants)
                return StartConversationMove(actor=self.actor, participants=[ref.resolve(registry) for ref in self.participants])
            case JoinConversationMove.selection_id:
                assert(self.conversation)
                return JoinConversationMove(actor=self.actor, conversation=self.conversation.resolve(registry))
            case ExitConversationMove.selection_id:
                assert(self.conversation)
                return ExitConversationMove(actor=self.actor, conversation=self.conversation.resolve(registry))
            case ChangeRoomMove.selection_id:
                assert(self.room)
                return ChangeRoomMove(actor=self.actor, room=self.room.resolve(registry))
            case InteractMove.selection_id:
                assert(self.interactable)
                interactable = self.interactable.resolve(registry)
                for action in interactable.interactors:
                    if action.value == self.action:
                        return InteractMove(actor=self.actor, interactable=interactable, action=action)
                raise ValueError(f"'{self.action}' is not a valid action for the {interactable.name}.")
            case EndInteractionMove.selection_id:
                assert(self.interactable)
                return EndInteractionMove(actor=self.actor, interactable=self.interactable.resolve(registry))
            case _:
                raise ValueError(f"'{self.selection_id}' is not a valid selection for {type(self).__name__}.")


class EffortMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [EffortMove]

    effort: int = Field(description="The percentage of effort - from 1 to 100 - that you will put into trying to win.")

    def get_move(self, registry: Registry) -> EffortMove:
        assert(self.actor)
        return EffortMove(actor=self.actor, effort=self.effort)


class EvictionVoteMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [EvictionVoteMove]

    choice: DefaultHouseguest.Ref = Field(description="The nominee you vote to evict.")

    def get_move(self, registry: Registry) -> EvictionVoteMove:
        assert(self.actor)
        return EvictionVoteMove(actor=self.actor, choice=self.choice.resolve(registry))
    

class JuryVoteMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [JuryVoteMove]

    choice: DefaultHouseguest.Ref = Field(description="The finalist you vote to win the game.")

    def get_move(self, registry: Registry) -> JuryVoteMove:
        assert(self.actor)
        return JuryVoteMove(actor=self.actor, choice=self.choice.resolve(registry))


class SchemeMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [SchemeMove]

    updated_scratchpad: str = Field(description="The full new contents of your scratchpad.")

    def get_move(self, registry: Registry) -> SchemeMove:
        assert(self.actor)
        return SchemeMove(actor=self.actor, updated_memory=DefaultMemory(content=self.updated_scratchpad))
    

class NominationMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [NominationMove]

    nominees: list[DefaultHouseguest.Ref] = Field(description="The houseguests you nominate for eviction.")

    def get_move(self, registry: Registry) -> NominationMove:
        assert(self.actor)
        return NominationMove(actor=self.actor, nominees=[ref.resolve(registry) for ref in self.nominees])


class VetoMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [VetoMove]

    choice: Optional[DefaultHouseguest.Ref] = Field(default=None, description="The nominee you remove from the block, or null to leave the nominations the same.")

    def get_move(self, registry: Registry) -> VetoMove:
        assert(self.actor)
        if self.choice:
            return VetoMove(actor=self.actor, choice=self.choice.resolve(registry))
        return VetoMove(actor=self.actor, choice=None)


class ReplacementNomineeMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [ReplacementNomineeMove]

    choice: DefaultHouseguest.Ref = Field(description="The houseguest you name as the replacement nominee.")

    def get_move(self, registry: Registry) -> ReplacementNomineeMove:
        assert(self.actor)
        return ReplacementNomineeMove(actor=self.actor, choice=self.choice.resolve(registry))


class VetoDrawChoiceMoveResponse(DefaultMoveResponse):

    valid_move_types: ClassVar[list[type[DefaultMove]]] = [VetoDrawChoiceMove]

    choice: DefaultHouseguest.Ref = Field(description="The houseguest you choose to play in the veto competition.")

    def get_move(self, registry: Registry) -> VetoDrawChoiceMove:
        assert(self.actor)
        return VetoDrawChoiceMove(actor=self.actor, choice=self.choice.resolve(registry))