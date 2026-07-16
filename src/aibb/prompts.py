BASE_PROMPT_TEMPLATE = '''
You are a houseguest competing against other houseguests in a game of Big Brother.
Decide on your next move.

Rules:
{rules}

Week Schedule:
{schedule}

Phase:
{phase_info}

Turn:
{turn_info}
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

RULES = '''
[TBD]
'''