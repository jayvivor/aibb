from aibb.base import Turn
from typing import ClassVar

# FABLE: Nothing constructs Turns yet - base.TurnType has no members, and week.py's
# PhaseStatusTurnType is a separate enum tree, so there is no member to fill
# `turn_type` with and no site that records into Phase.turns. Left in place (not
# commented out) because DefaultHouse is parameterized over it.
# IGNORE: Eventually - in a much future version of this - we will use a protocol-based
# system to delegate event generation/resolution down to the Turns. For now, we keep
# turns as objects that are never (or rarely) instantiated.
class DefaultTurn(Turn):
    info: ClassVar[str] = "A 'Turn'."