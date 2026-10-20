# Gold data

The gold chart and quote endpoints read PostgreSQL only. Opening a page, switching
SJC/ring, polling prices, or changing indicators never starts a provider request.

## Ingestion

The existing application-start and scheduled market-sync jobs call
`GoldHistorySync`. Configure `market-data.vnappmob.api-key` and `gold-url`.

On the first successful run, request provider history from Unix second **1**:
the provider interprets zero as a missing lower bound and returns only the latest
quote. Ranges with at least 100 records are split to avoid accepting a capped
response. A run has a 64-request budget; failure leaves its cursor unchanged.
The current quote endpoint is also read to include the latest session.

Later runs read `gold_sync_state.covered_until` and request only recent changes,
with a two-day overlap. The cursor is stored transactionally with the data and
survives application restarts. A provider outage retains the existing series.

## Storage

`gold_price_observations` stores one verified closing observation per ticker and
Vietnam calendar day, keeping the latest provider timestamp within that day.
Prices are VND per chỉ (provider fields are converted from VND per lượng).
Buy/sell values, provider timestamp, source, unit and fetch timestamp are retained.

The same verified sell price is upserted into `market_prices` for existing
valuation consumers. Legacy/sample market-price rows are preserved, but the gold
chart and current gold quotes read only `gold_price_observations`. No synthetic
prices or forward-filled daily rows are generated.

## Verification

Unit tests exercise provider timestamps, units, dense history, incremental sync
and failures. The opt-in PostgreSQL test creates and drops an isolated schema:

```sh
EQUIFOLIO_GOLD_TEST_URL=jdbc:postgresql://localhost:5432/equifolio \
mvn -f backend/pom.xml -Dtest=GoldPriceStoreDatabaseTest test
```

It uses DB_USER / DB_PASSWORD (defaults: postgres) and never changes application
tables. GoldHistorySyncTest and GoldHistoryControllerTest need no database.

## Daily 14:50 synchronization

`DailyMarketSyncJob` runs at 14:50 in `Asia/Ho_Chi_Minh`. It updates tracked stocks
and VN-Index on weekdays, and gold every day. Existing background jobs continue
to refresh prices afterward; 14:50 is the requested collection time, not an
assertion that every provider has finalized that day's price.

`daily_market_sync_runs` persists each date/market, attempt count, state,
timestamps and outcome. A stock attempt succeeds only after DNSE reports a new
VN-Index response dated today and all tracked stocks have today's stored price.
Gold requires a successful provider sync and both verified gold series for today.
Older data leaves the job PENDING rather than fabricating a new date.

A once-per-minute dispatcher checks missed/pending work between 14:50 and 23:45.
The database enforces a 15-minute retry lease and prevents repeating a successful
daily run, including after process restart. Weekday holidays or suspended stocks
can remain PENDING when the provider has no current-date bar. Jobs never invent
prices for these dates. A stopped backend cannot run cron; restarting it within
the catch-up window retries today's work. Normal backfill still catches historical
provider bars on subsequent starts.
