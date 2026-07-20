from aibb.base import Turn
from typing import ClassVar

class DefaultTurn(Turn):
    info: ClassVar[str] = "A 'Turn'."