-- Down migration for PRD: Bank Statement Free Quota (Additive Tables)
-- Run this script ONLY if rolling back the PRD Free Quota release.
-- Existing tables (users, daily_usage, conversions, etc.) are completely preserved.

DROP INDEX IF EXISTS idx_quota_audit_log_target;
DROP INDEX IF EXISTS idx_quota_exceptions_user;
DROP INDEX IF EXISTS idx_job_pages_job_id;
DROP INDEX IF EXISTS idx_quota_reservations_job;
DROP INDEX IF EXISTS idx_daily_quota_usage_lookup;

DROP TABLE IF EXISTS quota_audit_log;
DROP TABLE IF EXISTS quota_exceptions;
DROP TABLE IF EXISTS job_pages;
DROP TABLE IF EXISTS quota_reservations;
DROP TABLE IF EXISTS daily_quota_usage;
