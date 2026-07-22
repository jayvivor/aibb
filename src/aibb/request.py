from pydantic import Field

from aibb.base import Base, Registry


class DefaultRequest(Base):
    kwargs: dict = Field(default_factory=dict)
    registry: Registry = Field(default_factory=dict)
    max_retries: int = 3

    def describe(self):
        response_type = self.kwargs.get("response_type")
        if response_type:
            return f"A chat request for a {response_type.__name__}"
        return "A chat request"