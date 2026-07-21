BASE_PROMPT_TEMPLATE = '''
You are a houseguest competing against other houseguests in a game of Big Brother.
Decide on your next move.

Rules:
{rules}

Week Schedule:
{schedule}

Phase:
{phase_info}
'''


MESSAGE_TEMPLATE = '''
Scratchpad:
{scratchpad}

House Status:
{house_status}

Options:
{options}
'''


# TODO: Rule prompts
# FIX: Write concise prompts, here. AFAIK this is the only hard-coded, universal prompt,
# But I'm open to there being more. Explain only the objective and the mechanics, NOT the strategy
# Nor the typical approach. Don't mention anything about alliances, deception, backdoors, etc.
# Just the literal mechanics of the game, and that they are trying to be the last Houseguest standing.

RULES = '''
[TBD]
'''