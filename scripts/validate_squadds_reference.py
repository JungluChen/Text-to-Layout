"""Repository wrapper for the installed SQuADDS reference workflow."""
from textlayout.verification.squadds_reference import (
    ASSETS, DB_REV, GDS_REV, TOPS, main, validate, verified_asset,
)

__all__ = ["ASSETS", "DB_REV", "GDS_REV", "TOPS", "main", "validate", "verified_asset"]

if __name__ == "__main__":
    raise SystemExit(main())
