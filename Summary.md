# Summary

## Context
We observed that `/cad-to-bdt` returns a constant CAD→BDT rate for many historical dates. This is due to limited historical coverage in the local SQLite pricing snapshots, so older dates fall back to the most recent available snapshot instead of having distinct historical data.

## Goal
Reseed all historical pricing data with refreshed data from better API sources to improve historical accuracy and reduce fallback behavior.

## Plan
1. Inventory existing data coverage (min/max dates per data type, counts per cadence).
2. Choose improved providers and validate API key availability and rate limits.
3. Define a backfill window and cadence strategy (daily/weekly/monthly) for each data type.
4. Implement and run a controlled backfill process with logging and retry strategy.
5. Validate data quality (spot checks across dates, compare to prior values, ensure no gaps).
6. Mirror refreshed snapshots to R2 and verify cache consistency.
7. Update documentation and operational notes for ongoing refreshes.
