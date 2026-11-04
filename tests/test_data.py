"""Cleaning must leave exactly one correctly aligned exposure per user."""

import pytest

from abtest import data


@pytest.fixture(scope="module")
def raw():
    return data.load_raw()


def test_integrity_numbers(raw):
    rep = data.integrity_report(raw)
    assert rep.raw_rows == 294_478
    assert rep.misaligned_rows == 3_893
    assert rep.duplicate_users == 3_894
    assert rep.misaligned_rows_in_non_duplicate_users == 0   # every bad row belongs to a duplicated user
    assert rep.missing_country == 0


@pytest.mark.parametrize("strategy", ["exclude_contaminated", "keep_aligned_first"])
def test_clean_one_aligned_row_per_user(raw, strategy):
    df = data.clean(raw, strategy)
    assert df["user_id"].is_unique
    expected = df["group"].map(data.EXPECTED_PAGE)
    assert (df["landing_page"] == expected).all()


def test_primary_strategy_removes_all_contaminated_users(raw):
    df = data.clean(raw, "exclude_contaminated")
    dup_ids = set(raw.loc[raw["user_id"].duplicated(), "user_id"])
    assert not set(df["user_id"]) & dup_ids
    assert len(df) == raw["user_id"].nunique() - len(dup_ids)


def test_unknown_strategy_rejected(raw):
    with pytest.raises(ValueError):
        data.clean(raw, "nope")
