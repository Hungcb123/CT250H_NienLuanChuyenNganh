-- Existing rows cannot be distinguished from the former interpolated backfill.
-- Preserve them for audit, but exclude them from measured performance.
ALTER TABLE portfolio_snapshots ADD COLUMN snapshot_source VARCHAR(32) NOT NULL DEFAULT 'LEGACY_UNVERIFIED';
