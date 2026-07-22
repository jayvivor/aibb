from pydantic import Field, ValidationError
from openrouter import OpenRouter
from openrouter.errors import OpenRouterError
from typing import Optional

from aibb.base import Role, Memory, Houseguest, Status, GameEvent, MoveResponse, Ref, Registry
from aibb.request import DefaultRequest
from aibb.utils import get_client
from aibb.log import get_logger



__all__ = [
    "DefaultRole",
    "DefaultMemory",
    "DefaultHouseguest",
]


class AIError(Exception):
    pass


class DefaultRole(Role):
    HOH = "Head of Household"
    POV = "Power of Veto"
    NOMINEE = "Nominee"
    BLOCKBUSTER = "Blockbuster"
    HAVE_NOT = "Have-Not"

    DRAWN_FOR_VETO = "Drawn for Veto"
    OUTGOING_HOH = "Outgoing HOH"
    ACTIVE = "Active"
    WINNER = "Winner"


class DefaultMemory(Memory):
    content: str = Field(default_factory=str)

    def describe(self):
        return self.content


# TODO: Full-on RPG Mechanics over here
# IGNORE: This will be implemented eventually; explained elsewhere. For now, let it be.
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
    history: list[GameEvent] = Field(default_factory=list, exclude=True)
    memory_limit: Optional[int] = 100
    statuses: list[Status] = Field(default_factory=list)
    max_attempts: int = 3

    class Ref(Ref):
        name: str = Field(description="The exact name of the houseguest.")

    # def get_roles(self):
    #     return [r.value for r in self.roles]

    def describe(self):
        # return f"{self.name} ({listed(self.get_roles())})"
        return self.name
    
    def __hash__(self):
        return super().__hash__()
    
    def get_chat_request[R: MoveResponse](self, prompt: str, user_message: str, response_type: type[R], registry: Registry) -> DefaultRequest:
        return DefaultRequest(
            kwargs={"prompt": prompt, "user_message": user_message, "response_type": response_type},
            registry=registry,
            max_retries=self.max_attempts,
        )

    def get_chat_response[R: MoveResponse](self, prompt: str, user_message: str, response_type: type[R], registry: Optional[Registry]=None, client: Optional[OpenRouter]=None) -> R:
        
        logger = get_logger()

        if client is None:
            client = get_client()

        messages = [
                {"role": "system", "content": prompt},
                {"role": "user","content": user_message},
            ]
        last_error = None

        with client:
            for _attempt in range(self.max_attempts):
                    try:
                        # FABLE: assumed the SDK kwarg is `model`; verify against the openrouter client
                        # RESOLVE: This is correct. No action needed.
                        response_format = {
                            "type": "json_schema",
                                "json_schema": {
                                    "name": response_type.__name__,
                                    "schema": response_type.get_schema(hg=self, registry=registry),
                                    "additionalProperties": False,
                                },
                        }
                        res = client.chat.send(model=self.model_id, messages=messages, response_format=response_format, timeout_ms=1000*30)  # type: ignore
                        content = res.choices[0].message.content or ""
                    except OpenRouterError as e:  # provider
                        last_error = e
                        logger.warning(f"{self.name}: {e.body}")
                        continue
                    except Exception as e:  # anything else
                        last_error = e
                        logger.warning(f"{self.name}: {e}")
                        continue
    
                    # Slice from first "{" to last "}" — tolerates code fences
                    # and stray preamble without a separate extraction step.
                    start = content.find("{")  # type: ignore
                    end = content.rfind("}")  # type: ignore
                    candidate = content[start : end + 1] if 0 <= start < end else content
    
                    try:
                        parsed = response_type.model_validate_json(candidate)  # type: ignore
                    except ValidationError as e:
                        last_error = e
                        logger.warning(f"{self.name}: {e}")
                        # Feed the failure back so the model can self-repair.
                        messages = messages + [
                            {"role": "assistant", "content": content},
                            {
                                "role": "user",
                                "content": (
                                    "Your previous output was not valid against the "
                                    f"required schema. Error:\n{e}\n\n"
                                    "Respond again with ONLY the corrected JSON "
                                    "object, no code fences, no commentary."
                                ),
                            },
                        ]
                        continue

                    parsed.actor = self
                    return parsed
    
            raise AIError(
                f"Houseguest {self.name}: failed after {self.max_attempts} attempts"
            ) from last_error
        
    def get_move[R: MoveResponse](self, prompt: str, user_message: str, response_type: type[R], registry: Optional[Registry]=None) -> R:
        return self.get_chat_response(prompt, user_message, response_type, registry)