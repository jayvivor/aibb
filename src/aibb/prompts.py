BASE_PROMPT_TEMPLATE = '''
You are a houseguest competing against other houseguests in a game of Big Brother.
Decide on your next move.

Rules:
{rules}

Format:
{response_format}

Week Schedule:
{schedule}

Phase:
{phase_info}
{time_info}
'''


MESSAGE_TEMPLATE = '''
Scratchpad:
{scratchpad}

Status:
{status}

Memory:
{memory}

Options:
{options}
'''


# TODO: Rule prompts
# FIX: Write concise prompts, here. AFAIK this is the only hard-coded, universal prompt,
# But I'm open to there being more. Explain only the objective and the mechanics, NOT the strategy
# Nor the typical approach. Don't mention anything about alliances, deception, backdoors, etc.
# Just the literal mechanics of the game, and that they are trying to be the last Houseguest standing.

RULES = '''
- The houseguests live together in the Big Brother house. Houseguests are evicted one at a time, and the last houseguest standing wins.
- Each week begins with a Head of Household (HOH) competition. The winner is safe for the week and must nominate two houseguests for eviction.
- Six houseguests play in the Power of Veto competition: the HOH, both nominees, and three others selected by random draw. The veto winner may remove one nominee from the block; if they do, the HOH must name a replacement nominee.
- At the end of the week, every houseguest besides the HOH and the nominees votes to evict one nominee. The nominee with the most votes is evicted; the HOH votes only to break a tie.
- Houseguests evicted late in the season become members of the jury.
- When three houseguests remain, the final HOH alone evicts one of the other two. The jury then votes for one of the two finalists, and the finalist with the most jury votes wins the game.
'''

RESPONSE_FORMAT = '''
Respond with **exactly one JSON object** and nothing else — no code fences, no preamble, no commentary. It must match this schema exactly (field names, nesting, and types):

```
{schema}
```
'''