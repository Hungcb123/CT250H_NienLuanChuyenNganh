-- Signed VND value at posting time, independent from subsequent market prices.
ALTER TABLE entries ADD COLUMN monetary_value NUMERIC(19,4);
-- VND entries require no historical exchange rate.
UPDATE entries e SET monetary_value = e.amount
FROM accounts a WHERE e.account_id = a.id AND a.asset_type = 'VND';
-- Correct the known credit-normal sign bug only when the full entry history
-- proves that the snapshot is exactly its opposite. Other discrepancies remain visible.
UPDATE accounts a SET balance = totals.balance, version = a.version + 1
FROM (SELECT account_id, SUM(amount) AS balance FROM entries GROUP BY account_id) totals
WHERE a.id = totals.account_id
  AND a.account_code IN ('EQUITY_CAPITAL', 'INTEREST_INCOME')
  AND a.balance = -totals.balance AND a.balance <> totals.balance;
-- Do not infer missing stock/gold values from today's prices or force sums to zero.
