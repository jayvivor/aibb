import json
import random
import sys
import urllib.request

import yaml

# example cast.yaml:
# token_output_no_reasoning: 235
# token_output_with_reasoning: 820
# cast:
#   - name: Alice
#     model: anthropic/claude-fable-5
#     reasoning: true
#   - name: Bob
#     model: moonshotai/kimi-k3
#     provider_id: moonshot
#     reasoning: true
#   - name: Carol
#     model: z-ai/glm-5.2
#     price_in: 1.0     # $/M overrides skip the API lookup
#     price_out: 3.0
#     tps: 80
#     ttft: 1.0

TOKEN_OUTPUT_NO_REASONING = 235
TOKEN_OUTPUT_WITH_REASONING = 820

CALLS_PER_WEEK = 22
BATCHES_PER_WEEK = 23
INPUT_FIXED = 2250
INPUT_PER_ACTIVE = 135
FINALISTS = 3
DEFAULT_TPS = 60.0
DEFAULT_TTFT = 1.5
TAIL = 1.8
ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{}/endpoints"


def fetch_endpoint(model, provider_id):
    with urllib.request.urlopen(ENDPOINTS_URL.format(model), timeout=15) as r:
        eps = json.load(r)["data"]["endpoints"]
    if provider_id:
        match = [e for e in eps if provider_id.lower() in
                 (str(e.get("provider_name", "")) + str(e.get("tag", "")) + str(e.get("name", ""))).lower()]
        if not match:
            print(f"warning: provider '{provider_id}' not found for {model}, using best available")
        eps = match or eps
    return max(eps, key=lambda e: float(e.get("throughput_last_30m") or 0))


def resolve(hg, out_reason, out_plain):
    h = dict(hg)
    needed = not all(k in h for k in ("price_in", "price_out", "tps", "ttft"))
    if needed:
        try:
            ep = fetch_endpoint(h["model_id"], h.get("provider_id"))
        except Exception as e:
            sys.exit(f"error: could not resolve '{h['name']}' ({h['model_id']}): {e}")
        h.setdefault("price_in", float(ep["pricing"]["prompt"]) * 1e6)
        h.setdefault("price_out", float(ep["pricing"]["completion"]) * 1e6)
        h.setdefault("tps", float(ep.get("throughput_last_30m") or DEFAULT_TPS))
        lat = float(ep.get("latency_last_30m") or DEFAULT_TTFT)
        h.setdefault("ttft", lat / 1000 if lat > 100 else lat)  # normalize if reported in ms
    h["out_tokens"] = out_reason if h.get("reasoning") else out_plain
    h["call_time"] = h["ttft"] + h["out_tokens"] / h["tps"]
    return h


def input_tokens(survived_weeks, cast_size):
    return sum(CALLS_PER_WEEK * (INPUT_FIXED + INPUT_PER_ACTIVE * (cast_size - k))
               for k in range(survived_weeks))


def seat_cost(hg, survived_weeks, cast_size):
    inp = input_tokens(survived_weeks, cast_size)
    out = CALLS_PER_WEEK * hg["out_tokens"] * survived_weeks
    return (inp * hg["price_in"] + out * hg["price_out"]) / 1e6


def season_cost(order, survivals, cast_size):
    return sum(seat_cost(h, s, cast_size) for h, s in zip(order, survivals))


def season_hours(eviction_order, weeks):
    active, total = list(eviction_order), 0.0
    for _ in range(weeks):
        total += BATCHES_PER_WEEK * max(h["call_time"] for h in active) * TAIL
        if len(active) > FINALISTS:
            active.pop(0)
    return total / 3600


def main(path):
    cfg = yaml.safe_load(open(path))
    out_reason = cfg.get("token_output_with_reasoning", TOKEN_OUTPUT_WITH_REASONING)
    out_plain = cfg.get("token_output_no_reasoning", TOKEN_OUTPUT_NO_REASONING)
    cast = [resolve(hg, out_reason, out_plain) for hg in cfg["cast"]]
    n = len(cast)
    weeks = n - FINALISTS
    survivals = list(range(1, weeks + 1)) + [weeks] * FINALISTS

    full = lambda h: seat_cost(h, weeks, n)
    print(f"assumptions: output/call = {out_plain} plain / {out_reason} reasoning, "
          f"{CALLS_PER_WEEK} calls + {BATCHES_PER_WEEK} batches per hg-week, tail x{TAIL}")
    print(f"cast of {n} -> {weeks} weeks, {weeks * BATCHES_PER_WEEK} batches\n")
    for h in sorted(cast, key=full, reverse=True):
        print(f"  {h['name']:<12} {h['model_id']:<36} ${h['price_in']:>6.2f}/${h['price_out']:>6.2f} "
              f"{h['tps']:>5.0f} tps  {h['call_time']:>5.1f}s/call  full-season ${full(h):.2f}")

    best = season_cost(sorted(cast, key=full, reverse=True), survivals, n)
    worst = season_cost(sorted(cast, key=full), survivals, n)
    expected = sum(sum(seat_cost(h, s, n) for s in survivals) / n for h in cast)
    print(f"\ncost:     best ${best:.2f}   expected ${expected:.2f}   worst ${worst:.2f}")

    t_best = season_hours(sorted(cast, key=lambda h: -h["call_time"]), weeks)
    t_worst = season_hours(sorted(cast, key=lambda h: h["call_time"]), weeks)
    t_expected = sum(season_hours(random.sample(cast, n), weeks) for _ in range(500)) / 500
    print(f"duration: best {t_best:.1f}h   expected {t_expected:.1f}h   worst {t_worst:.1f}h")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "cast.yaml")