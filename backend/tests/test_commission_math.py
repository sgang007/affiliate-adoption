from decimal import Decimal

from app.services.commission import KEEP_SHARE, q2


def cascade(base: Decimal, depth: int) -> list[Decimal]:
    """Mirror of the engine's pool-splitting logic for an N-deep chain."""
    pool = q2(base)
    shares = []
    for i in range(depth):
        is_last = i == depth - 1
        share = pool if is_last else q2(pool * KEEP_SHARE)
        shares.append(share)
        pool = q2(pool - share)
        if pool <= 0:
            break
    return shares


def test_root_alone_gets_full_base():
    assert cascade(Decimal(100), 1) == [Decimal("100.00")]


def test_two_levels_match_spec_example():
    # Sub-affiliate 80, parent 20 — exactly the spec's Rs 100 example.
    assert cascade(Decimal(100), 2) == [Decimal("80.00"), Decimal("20.00")]
    # Subscription example: base 360 → 288 for the sub, 72 for the parent.
    assert cascade(Decimal(360), 2) == [Decimal("288.00"), Decimal("72.00")]


def test_three_levels_total_never_exceeds_base():
    shares = cascade(Decimal(300), 3)
    assert shares == [Decimal("240.00"), Decimal("48.00"), Decimal("12.00")]
    assert sum(shares) == Decimal("300.00")


def test_deep_chain_company_cost_constant():
    for depth in range(1, 10):
        shares = cascade(Decimal(1000), depth)
        assert sum(shares) == Decimal("1000.00")
