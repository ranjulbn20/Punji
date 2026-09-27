"""
Signal engine — Phase 1 of the proactive portfolio-monitoring architecture.

Independent signals feed a deterministic fusion (no LLM call spent on fusion
itself — only on reading news text, which is inherently unstructured):

  A. Price signal — pure quantitative, 1D *and* 5D change. Free, always
     available, catches both a sharp move and a slow multi-day bleed that no
     single day would cross the threshold for.
  B. News signal  — LLM-classified event (direction/materiality/confidence).
     See services/news_service.py::classify_news_signal.
  C. Benchmark context (services/benchmark_service.py) — moderates the fused
     signal rather than adding a third parallel signal: a move mostly
     explained by the market/sector is downgraded and annotated as such,
     since the goal is flagging company-specific risk, not "the market had a
     red day" (which the user doesn't need Punji to tell them).

Portfolio weight also moderates severity — the same % move matters more in a
25%-of-portfolio holding than a 2%-of-portfolio one.

Not built yet (later phases, see CLAUDE.md):
  D. Fundamentals — no data source exists in this codebase yet.
  Peer-basket benchmarks for industries with no clean NSE index — falls back
  to NIFTY FINANCIAL SERVICES / market-only for now instead.

Fusing negative+positive signals into a buy/sell recommendation (routing
through recommendation_node + devil_advocate_node) is Phase 3 — this module
only detects and explains, it does not suggest action.
"""
from config import settings

# Only two severity tiers, matching every other alert_type in this codebase
# (Alert.severity is "critical"/"significant" everywhere else) — no new tier
# for the frontend to not know how to style.
_SEVERITY_DOWN = {"high": "medium", "medium": "medium"}
_SEVERITY_UP = {"high": "high", "medium": "high"}

# Below this, a stock's move relative to its benchmark looks like "the market/
# sector moved", not "this company specifically did something" — see apply_context.
BROAD_MOVE_THRESHOLD_PCT = 2.0

# A holding this large deserves attention even at moderate severity.
LARGE_POSITION_THRESHOLD_PCT = 15.0


def compute_price_signal(change_1d: float | None, change_5d: float | None = None) -> dict | None:
    """
    Deterministic — no LLM. Triggers on an abnormal single-day move OR a slow
    multi-day bleed. `direction` and `trend` are kept as separate concepts
    rather than one field doing both jobs:
      direction — immediate risk direction. If every horizon that crossed the
                  threshold agrees in sign, that's it; if they disagree (e.g.
                  today's dip inside an otherwise-positive week), today's own
                  move wins, since that's the immediate thing to react to.
      trend     — the broader multi-day direction (sign of change_5d),
                  independent of today's move, so an alert can say "today's
                  move is negative, but the 5-day trend remains positive"
                  instead of collapsing that nuance into one value.
    """
    threshold = settings.price_move_threshold_pct
    candidates = []
    if change_1d is not None and abs(change_1d) >= threshold:
        candidates.append(("1-day", change_1d))
    if change_5d is not None and abs(change_5d) >= threshold:
        candidates.append(("5-day", change_5d))

    if not candidates:
        return None

    evidence = [f"{change:+.2f}% {label} price move" for label, change in candidates]

    signs = {change > 0 for _, change in candidates}
    if len(signs) == 1:
        direction = "positive" if signs == {True} else "negative"
    else:
        direction = "positive" if change_1d > 0 else "negative"

    trend = None
    if change_5d is not None and change_5d != 0:
        trend = "positive" if change_5d > 0 else "negative"

    strongest_label, strongest_change = max(candidates, key=lambda c: abs(c[1]))
    severity = "high" if abs(strongest_change) >= threshold * 1.6 else "medium"

    return {
        "signal_type": "price",
        "direction": direction,
        "trend": trend,
        "severity": severity,
        "confidence": 1.0,
        "evidence": evidence,
        "strongest_move_horizon": strongest_label,
        "strongest_move_pct": strongest_change,
    }


def fuse_signals(price_signal: dict | None, news_signal: dict | None) -> dict | None:
    """
    Combine whichever signals fired into one verdict. Either signal alone is
    enough to alert on — a price move with no news found, or material news
    on a stock that hasn't fully moved yet, are both worth surfacing.
    """
    signals = [s for s in (price_signal, news_signal) if s]
    if not signals:
        return None

    _severity_rank = {"medium": 1, "high": 2}
    directions = {s["direction"] for s in signals}
    direction = next(iter(directions)) if len(directions) == 1 else "mixed"
    severity = max((s["severity"] for s in signals), key=lambda s: _severity_rank[s])
    # min(), not mean() — price's confidence is always a constant 1.0 (it's
    # certainty the *number* is accurate, not a real probability), so
    # averaging it with news' genuinely-uncertain LLM confidence always
    # inflates the blend upward (e.g. mean(1.0, 0.65) = 0.825 clears an 0.8
    # gate the weak evidence shouldn't). The weakest signal should set the
    # ceiling, not get diluted by the deterministic one.
    confidence = min(s["confidence"] for s in signals)
    evidence = [item for s in signals for item in s["evidence"]]

    return {
        "direction": direction,
        "trend": price_signal.get("trend") if price_signal else None,
        "severity": severity,
        "confidence": confidence,
        "evidence": evidence,
        "signal_types": [s["signal_type"] for s in signals],
        "news": news_signal,
    }


def apply_context(signal: dict, benchmark_context: dict, portfolio_weight_pct: float | None = None) -> dict:
    """
    Moderates a fused signal using benchmark comparison and portfolio weight.
    Returns a new dict — does not mutate the input.
    """
    signal = dict(signal)
    evidence = list(signal["evidence"])

    market_change = benchmark_context.get("market_change_pct")
    market_rel = benchmark_context.get("market_relative_pct")
    industry = benchmark_context.get("industry")
    industry_change = benchmark_context.get("industry_change_pct")
    industry_rel = benchmark_context.get("industry_relative_pct")

    if market_change is not None:
        evidence.append(f"NIFTY 50: {market_change:+.2f}%, relative: {market_rel:+.2f}%")
    if industry_rel is not None:
        evidence.append(f"{industry} index: {industry_change:+.2f}%, relative: {industry_rel:+.2f}%")

    relevant_rel = industry_rel if industry_rel is not None else market_rel
    is_broad_based = relevant_rel is not None and abs(relevant_rel) < BROAD_MOVE_THRESHOLD_PCT

    if is_broad_based:
        signal["severity"] = _SEVERITY_DOWN[signal["severity"]]
        signal["market_context"] = "broad_based"
    else:
        signal["market_context"] = "company_specific"

    if portfolio_weight_pct is not None:
        if portfolio_weight_pct >= LARGE_POSITION_THRESHOLD_PCT:
            signal["severity"] = _SEVERITY_UP[signal["severity"]]
            evidence.append(f"{portfolio_weight_pct:.1f}% of your portfolio — a large position")
        signal["portfolio_weight_pct"] = portfolio_weight_pct

    signal["evidence"] = evidence
    return signal
