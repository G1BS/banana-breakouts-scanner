"""
Numeric-only "best probability" swing trade scoring.

No news/catalyst search — everything here comes from the screener's own
numbers, so it's free to run and fully deterministic. Weights sum to 100.

This ranks candidates against EACH OTHER. It does not tell you whether to
trade at all today — that's a separate, market-wide "regime" check (see
regime_multiplier below) that applies equally to every stock.
"""

WEIGHTS = {
    "rs": 15,
    "volume": 15,
    "cir": 10,
    "extension": 20,
    "base_freshness": 10,
    "resistance": 10,
    "risk_reward": 20,
}


def _clamp(x, lo=0, hi=None):
    if hi is not None:
        x = min(x, hi)
    return max(x, lo)


def score_rs(stock):
    rs = stock.get("rs_rating")
    if rs is None:
        return WEIGHTS["rs"] * 0.5  # neutral if missing
    return _clamp(rs / 99.0, 0, 1) * WEIGHTS["rs"]


def score_volume(stock):
    vol = stock.get("breakout_volume")
    if vol is None:
        return WEIGHTS["volume"] * 0.5
    # 3.5x normal volume or higher = full marks; scales down below that
    return _clamp(vol / 3.5, 0, 1) * WEIGHTS["volume"]


def score_cir(stock):
    cir = stock.get("cir")
    if cir is None:
        return WEIGHTS["cir"] * 0.5
    return _clamp(cir, 0, 1) * WEIGHTS["cir"]


def score_extension(stock):
    """
    Lower extension above pivot = lower risk of chasing = higher score.
    A NEGATIVE value means price is back below its pivot — that's a
    failed/failing breakout, not a "low risk entry", so it scores near
    zero rather than using abs().
    """
    ext = stock.get("vs_pivot_pct")
    if ext is None:
        return WEIGHTS["extension"] * 0.5
    if ext < 0:
        return _clamp(1 + (ext / 5.0), 0, 0.15) * WEIGHTS["extension"]  # capped low
    # 0% extension = full marks, 10%+ extension = zero
    return _clamp(1 - (ext / 10.0), 0, 1) * WEIGHTS["extension"]


def score_base_freshness(stock):
    """Fewer bases this year + younger base = more fuel left in the move."""
    base_count = stock.get("base_count")
    base_age = stock.get("base_age_wk")
    if base_count is None and base_age is None:
        return WEIGHTS["base_freshness"] * 0.5
    count_score = 1.0
    if base_count is not None:
        # 1st-2nd base = full marks; 8th+ base = near zero
        count_score = _clamp(1 - ((base_count - 1) / 8.0), 0, 1)
    age_score = 1.0
    if base_age is not None:
        # Sweet spot ~2-6 weeks; older bases (16-20wk) score lower
        age_score = _clamp(1 - max(0, base_age - 6) / 15.0, 0, 1)
    return ((count_score + age_score) / 2) * WEIGHTS["base_freshness"]


def score_resistance(stock):
    """Uses overhead supply % as a proxy for room to run."""
    overhead = stock.get("overhead_supply_pct")
    if overhead is None:
        return WEIGHTS["resistance"] * 0.5
    overhead = abs(overhead)
    return _clamp(1 - (overhead / 5.0), 0, 1) * WEIGHTS["resistance"]


def score_risk_reward(stock):
    """
    Proxy R:R: smaller extension above pivot means a tighter, more
    defensible stop for the same assumed target distance. This is a
    simplification (no real target/stop data without a news/technical
    read) — treat this score as directional, not precise. Below-pivot
    (negative extension) scores near zero, same reasoning as extension.
    """
    ext = stock.get("vs_pivot_pct")
    if ext is None:
        return WEIGHTS["risk_reward"] * 0.5
    if ext < 0:
        return _clamp(1 + (ext / 6.0), 0, 0.15) * WEIGHTS["risk_reward"]
    return _clamp(1 - (ext / 12.0), 0, 1) * WEIGHTS["risk_reward"]


SCORERS = {
    "rs": score_rs,
    "volume": score_volume,
    "cir": score_cir,
    "extension": score_extension,
    "base_freshness": score_base_freshness,
    "resistance": score_resistance,
    "risk_reward": score_risk_reward,
}


def score_stock(stock):
    breakdown = {k: round(fn(stock), 1) for k, fn in SCORERS.items()}
    total = sum(breakdown.values())
    # BananaPatterns' own "Cooling off" tag means momentum has already
    # stalled post-breakout — respect that signal directly rather than
    # relying only on the numeric proxies to catch it.
    if stock.get("status") == "Cooling off":
        total *= 0.75
        breakdown["cooling_off_penalty"] = round(total - sum(v for k, v in breakdown.items()), 1)
    total = round(total, 1)
    return total, breakdown


def rank_stocks(stocks):
    ranked = []
    for s in stocks:
        total, breakdown = score_stock(s)
        ranked.append({**s, "score": total, "breakdown": breakdown})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def verdict(score):
    if score >= 75:
        return "STRONG"
    if score >= 60:
        return "OK"
    return "WEAK"
