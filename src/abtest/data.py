"""Load the experiment log and decide which users are valid for analysis.

The raw log has one row per page exposure: user_id, timestamp, group, landing_page,
converted. Two integrity problems show up:

1. Misaligned rows: a 'control' user shown the new page, or a 'treatment' user shown
   the old page (3,893 rows).
2. Duplicate users: 3,894 users appear twice. Every misaligned row belongs to one of
   them, and 1,895 of them were logged in BOTH groups.

Both point to a bug in assignment/logging for those users, so we can't be sure which
experience they actually had. Two cleaning strategies are provided:

* "exclude_contaminated" (PRIMARY): drop every user with more than one row. Clean and
  conservative: each remaining user has exactly one, correctly aligned exposure.
* "keep_aligned_first" (SENSITIVITY): the common textbook fix: drop misaligned rows,
  then keep each user's first remaining row.

If both strategies lead to the same decision, the result doesn't hinge on the cleaning.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

EXPECTED_PAGE = {"control": "old_page", "treatment": "new_page"}


def load_raw() -> pd.DataFrame:
    """Load the raw experiment log joined with country, flagging misaligned exposures."""
    df = pd.read_csv(RAW / "ab_data.csv", parse_dates=["timestamp"])
    countries = pd.read_csv(RAW / "countries.csv")
    df = df.merge(countries, on="user_id", how="left", validate="many_to_one")
    df["aligned"] = df["landing_page"] == df["group"].map(EXPECTED_PAGE)
    return df


@dataclass
class IntegrityReport:
    """Counts describing the two integrity problems in the raw log (see module docstring)."""

    raw_rows: int
    raw_users: int
    misaligned_rows: int
    duplicate_users: int
    users_in_both_groups: int
    misaligned_rows_in_non_duplicate_users: int
    missing_country: int

    def as_dict(self) -> dict:
        """Return the report's fields as a plain dict, for JSON output."""
        return self.__dict__.copy()


def integrity_report(raw: pd.DataFrame) -> IntegrityReport:
    """Compute the IntegrityReport counts (misaligned rows, duplicate users, etc.) from the raw log."""
    per_user = raw.groupby("user_id").agg(rows=("group", "size"), groups=("group", "nunique"))
    dup_ids = set(per_user.index[per_user["rows"] > 1])
    return IntegrityReport(
        raw_rows=len(raw),
        raw_users=raw["user_id"].nunique(),
        misaligned_rows=int((~raw["aligned"]).sum()),
        duplicate_users=len(dup_ids),
        users_in_both_groups=int((per_user["groups"] > 1).sum()),
        misaligned_rows_in_non_duplicate_users=int(
            (~raw["aligned"] & ~raw["user_id"].isin(dup_ids)).sum()
        ),
        missing_country=int(raw["country"].isna().sum()),
    )


def clean(raw: pd.DataFrame, strategy: str = "exclude_contaminated") -> pd.DataFrame:
    """Return one row per user, ready for analysis."""
    if strategy == "exclude_contaminated":
        counts = raw["user_id"].value_counts()
        out = raw[raw["user_id"].isin(counts.index[counts == 1])]
    elif strategy == "keep_aligned_first":
        out = (raw[raw["aligned"]]
               .sort_values("timestamp")
               .drop_duplicates("user_id", keep="first"))
    else:
        raise ValueError(f"unknown strategy {strategy!r}")

    out = out.copy()
    out["date"] = out["timestamp"].dt.date
    assert out["user_id"].is_unique, "cleaning must leave one row per user"
    assert out["aligned"].all(), "cleaning must leave only correctly aligned exposures"
    return out.drop(columns="aligned").reset_index(drop=True)
