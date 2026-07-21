from aibb.base import Turn
from typing import ClassVar

# FABLE: Nothing constructs Turns yet - base.TurnType has no members, and week.py's
# PhaseStatusTurnType is a separate enum tree, so there is no member to fill
# `turn_type` with and no site that records into Phase.turns. Left in place (not
# commented out) because DefaultHouse is parameterized over it.
class DefaultTurn(Turn):
    info: ClassVar[str] = "A 'Turn'."