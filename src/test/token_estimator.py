import random
import time

from aibb import helpers as aibb_helpers
from dummy import core, pools


# Output tokens can't be measured from dummies (they never generate text), so
# they're estimated at a flat rate per call, matching cost_estimator.py
TOKEN_OUTPUT_PER_CALL = 235

try:
    import tiktoken
    ENCODING = tiktoken.get_encoding("o200k_base")
except Exception:
    ENCODING = None
    print("tiktoken unavailable; estimating at 4 characters per token")


def count_tokens(text: str) -> int:
    if ENCODING:
        return len(ENCODING.encode(text))
    return len(text) // 4


class CountingHouseguest(core.DummyHouseguest):

    calls: int = 0
    input_tokens: int = 0

    def get_move[R: core.DefaultMoveResponse](self, prompt: str, user_message: str, response_type: type[R]) -> R: # type: ignore
        self.calls += 1
        self.input_tokens += count_tokens(prompt) + count_tokens(user_message)
        return super().get_move(prompt, user_message, response_type)


cast = [CountingHouseguest(name=name) for name in random.sample(pools.NAMES, k=16)]
house = aibb_helpers.get_default_house(cast=cast)

start = time.time()
house.simulate_season()
print(f"\nSeason simulated in {time.time() - start:.0f}s ({len(house.history)} turns)\n")

rows = [(hg.name, hg.calls, hg.input_tokens, hg.calls * TOKEN_OUTPUT_PER_CALL) for hg in cast]
rows.sort(key=lambda row: row[2], reverse=True)

name_width = max(len(name) for name, _, _, _ in rows)
header = f"{'Houseguest':<{name_width}}  {'Calls':>6}  {'Input':>12}  {'Output (est)':>12}  {'Total':>12}"
print(header)
print("-" * len(header))
for name, calls, input_tokens, output_tokens in rows:
    print(f"{name:<{name_width}}  {calls:>6}  {input_tokens:>12,}  {output_tokens:>12,}  {input_tokens + output_tokens:>12,}")
print("-" * len(header))
total_calls = sum(calls for _, calls, _, _ in rows)
total_input = sum(input_tokens for _, _, input_tokens, _ in rows)
total_output = sum(output_tokens for _, _, _, output_tokens in rows)
print(f"{'TOTAL':<{name_width}}  {total_calls:>6}  {total_input:>12,}  {total_output:>12,}  {total_input + total_output:>12,}")