from pydantic import Field, ValidationError
from openrouter import OpenRouter

from aibb.base import Base, Role, Memory, Houseguest, Status, GameEvent
from aibb.utils import listed



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
    history: list[GameEvent] = Field(default_factory=list)
    statuses: list[Status] = Field(default_factory=list)
    max_attempts: int = 3

    def get_roles(self):
        return [r.value for r in self.roles]

    def describe(self):
        return f"{self.name} ({listed(self.get_roles())})"
    
    def get_chat_response(self, client: OpenRouter, prompt: str, user_message: str, response_type: type[Base]) -> Base:
        
        messages = [
                {"role": "system", "content": prompt},
                {"role": "user","content": user_message},
            ]
        last_error = None

        with client:
            for _attempt in range(self.max_attempts):
                    try:
                        res = client.chat.send(messages=messages)  # type: ignore
                        content = res.choices[0].message.content or ""
                    except Exception as e:  # network / provider / rate-limit
                        last_error = e
                        continue
    
                    # Slice from first "{" to last "}" — tolerates code fences
                    # and stray preamble without a separate extraction step.
                    start = content.find("{")
                    end = content.rfind("}")
                    candidate = content[start : end + 1] if 0 <= start < end else content
    
                    try:
                        parsed = response_type.model_validate_json(candidate)
                    except ValidationError as e:
                        last_error = e
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
    
                    # Never depend on the model echoing identifiers correctly —
                    # the cache check in eval_manuscript keys off this.
                    return parsed
    
            raise AIError(
                f"Houseguest {self.name}: failed after {self.max_attempts} attempts"
            ) from last_error
