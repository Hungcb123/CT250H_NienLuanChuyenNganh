# Prepared portfolio performance

## Storage and API behavior

The cache is persisted in the application's existing PostgreSQL database. It does not require Redis or depend on one backend process's memory.

- `performance_daily`: prepared NAV, asset values, linked growth index and external cash flow for each user/date/generation.
- `performance_head`: the published generation, source version, formula version, generation time, price date, provisional status and precomputed risk metrics.
- `performance_dirty`: durable invalidation queue, earliest affected date, retry time and processing error.
- `benchmark_daily`, `benchmark_versions`, `benchmark_head`: shared versioned VN-Index history. It is stored once per benchmark generation rather than copied into every user's prepared series.

`GET /api/v1/ledger/history` and `GET /api/v1/ledger/risk-metrics` read published projections in read-only transactions. They do not calculate NAV, write snapshots, enqueue work or fetch an external market API. Chart ranges are normalized from stored growth/benchmark indices; this small presentation calculation still happens on reads.

The response includes `dataVersion`, `formulaVersion`, `generatedAt`, `priceAsOf`, `provisional`, `status` and `updating`. Before the initial projection is ready, history returns `PREPARING`. While a newer version is being prepared, it returns the last complete generation with `UPDATING`. The frontend polls only while an expanded chart is waiting for an update, and stops when the chart closes or the generation is ready.

## Refresh and corrections

Database triggers invalidate projections after relevant changes to users, accounts, posted ledger inputs, snapshots, asset prices and the reference interest rate. VN-Index synchronization publishes a shared benchmark generation and invalidates dependent user projections. These invalidations survive a backend restart.

`PreparedPerformanceWorker` runs every five seconds, processes at most 12 queued users per batch, and uses a PostgreSQL advisory lock to prevent overlapping workers. It bulk-loads inputs, values current holdings, reconstructs affected observed historical snapshots from posted ledger entries and historical prices, and prepares linked returns and risk metrics in the background. Existing demo histories retain their demo provenance.

The worker currently recomputes each changed user's linked growth/risk series in memory. Historical NAV reconstruction is restricted to the affected dates. Unchanged users do not require recomputation. This intentionally keeps formula correctness straightforward while moving expensive work off the request path.

Publishing is transactional: prepared daily rows and the head pointer become visible together. Readers use a repeatable-read transaction so they cannot mix generations while old rows are cleaned up. A source-version mismatch or concurrent conflicting update rolls back publication; the queue remains pending for retry. Missing prices or an incomplete historical ledger defer that user and preserve the last complete projection.

At day rollover the worker creates a provisional current-day projection. Successful STOCKS and GOLD runs in `daily_market_sync_runs` trigger finalization, including catch-up after restart. The market scheduler starts at **14:50 Asia/Ho_Chi_Minh**; it retries incomplete runs rather than claiming success when the expected price date is unavailable. The old independent 15:05 snapshot timer is removed. A later source correction can restate a finalized snapshot; ordinary GET requests cannot change it.

## Operations and validation

Migration `V14__prepared_portfolio_performance.sql` creates the tables, triggers and initial queue. Flyway applies it on backend startup. The worker automatically drains the queue; no user needs to open a chart to initialize it.

Useful read-only checks:

```sql
SELECT status, count(*) FROM daily_market_sync_runs GROUP BY status;
SELECT count(*) AS published_users FROM performance_head;
SELECT user_id, dirty_from, revalue_from, retry_after, last_error FROM performance_dirty;
SELECT user_id, generation, formula_version, generated_at, price_as_of, provisional FROM performance_head;
```

Unit tests cover flow-neutral linked growth, irregular intervals and normalization. `PreparedPerformanceDatabaseTest` applies V14 to a temporary PostgreSQL schema and verifies initial preparation, enforced read-only GETs, withdrawals, backdated ledger corrections, historical price corrections, atomic benchmark changes, finalization and preserving the last complete version when prices are missing. Set `EQUIFOLIO_GOLD_TEST_URL` to opt into the database test. Its isolated schema is dropped at completion.
