"""
Value filter v3.1
Centralised filtering logic used by dashboard and TOP VALUE block.

Value formula:  value = probability * odds
Show bet if:    probability >= 0.55  AND  value >= 1.08
"""

# Thresholds
MIN_PROBABILITY = 0.55
MIN_VALUE       = 1.08   # probability * odds >= 1.08  (i.e. EV > 0)


def passes_filter(probability: float, odds: float) -> bool:
    """Return True if the bet meets minimum criteria."""
    if probability < MIN_PROBABILITY:
        return False
    value = probability * odds
    return value >= MIN_VALUE


def compute_value(probability: float, odds: float) -> float:
    """Returns probability * odds. Values > 1.0 are profitable in expectation."""
    return probability * odds


def value_pct(probability: float, odds: float) -> float:
    """Returns EV as a percentage above break-even, e.g. 0.12 = +12%."""
    return compute_value(probability, odds) - 1.0


def red_flags(home: str, away: str, df_history=None) -> list:
    """
    Returns list of warning strings for a match.
    Checks: derby, end-of-season, recent European match.
    """
    flags = []

    DERBY_PAIRS = [
        ("Arsenal","Chelsea"),("Arsenal","Tottenham"),("Chelsea","Tottenham"),
        ("Man City","Man United"),("Man City","Liverpool"),("Liverpool","Everton"),
        ("Real Madrid","Barcelona"),("Real Madrid","Atletico"),("Barcelona","Atletico"),
        ("Bayern","Dortmund"),("Inter","Milan"),("Inter","Juventus"),("Milan","Juventus"),
        ("PSG","Marseille"),("Galatasaray","Fenerbahce"),("Galatasaray","Besiktas"),
        ("Benfica","Porto"),("Benfica","Sporting"),("Porto","Sporting"),
    ]
    for h, a in DERBY_PAIRS:
        if (h.lower() in home.lower() and a.lower() in away.lower()) or \
           (a.lower() in home.lower() and h.lower() in away.lower()):
            flags.append("⚠ Дерби — высокая непредсказуемость")
            break

    import datetime
    now = datetime.datetime.now()
    # May/June = end of season
    if now.month in (5, 6):
        flags.append("⚠ Конец сезона — мотивация неизвестна")

    return flags
