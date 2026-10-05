from decimal import Decimal

from app.services.commission import q2


def topdown(base: Decimal, pct: Decimal, branch_len: int) -> list[Decimal]:
    """Mirror of the engine's top-down split for a branch below the admin."""
    pool = q2(base)
    shares = []
    for i in range(branch_len):
        is_converter = i == branch_len - 1
        share = pool if is_converter else q2(pool * pct / 100)
        shares.append(share)
        pool = q2(pool - share)
        if pool <= 0:
            break
    return shares


def test_direct_child_of_admin_keeps_everything():
    assert topdown(Decimal(300), Decimal(20), 1) == [Decimal("300.00")]


def test_spec_example_three_levels():
    # A(admin) → B → C → D, D converts flat 300 at 20% network commission:
    # B: 60, C: 48, D keeps 192.
    assert topdown(Decimal(300), Decimal(20), 3) == [
        Decimal("60.00"),
        Decimal("48.00"),
        Decimal("192.00"),
    ]


def test_two_levels():
    # B takes 20% of 100 = 20, converter C keeps 80.
    assert topdown(Decimal(100), Decimal(20), 2) == [Decimal("20.00"), Decimal("80.00")]


def test_company_cost_constant_at_any_depth():
    for depth in range(1, 10):
        shares = topdown(Decimal(1000), Decimal(20), depth)
        assert sum(shares) == Decimal("1000.00")


def test_custom_network_pct():
    # 10% network commission, depth 3: B 30, C 27, D 243.
    assert topdown(Decimal(300), Decimal(10), 3) == [
        Decimal("30.00"),
        Decimal("27.00"),
        Decimal("243.00"),
    ]
