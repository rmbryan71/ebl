# Backup and restore plan

## Problem statement
We need a reliable backup and restore approach for the website and database that minimizes data loss, is easy to execute, and can be verified quickly.

## Requirements
1. Back up the database and website assets with clear retention.
2. Restore should be repeatable with documented, deterministic steps.
3. Backups must be protected (access control and encryption).
4. The process should work in the current hosting environment.
5. Verification checks must confirm integrity and usability.

## Assumptions
1. Website assets include any uploaded files and static content that is not regenerated.
2. Database backups can be performed with Postgres-native tools.

## Plan
### 1) Inventory current storage
- Identify where the database runs and how it is hosted.
- List all website assets that need backup (uploads, static artifacts, generated reports).
- Identify secrets/config handling needed for backup/restore tooling.
- Note runtime constraints (cron, storage, permissions, environment variables).

### 2) Define backup strategy
- Database: choose dump format, schedule, retention, and storage target.
- Assets: choose snapshot method, schedule, retention, and storage target.
- Encryption and access controls for all backup artifacts.
- Document ownership and rotation procedures.

### 3) Define restore strategy
- Write a step-by-step runbook for DB restore.
- Write a step-by-step runbook for asset restore.
- Include verification steps (row counts, sample queries, page checks).
- Include rollback/safety measures and failure handling.

### 4) Implementation plan
- Add scripts or automation for backup and restore.
- Add monitoring/alerts for backup failures.
- Document the process in repo docs and ops notes.

## Open questions
1. Where should backup artifacts live (object storage, local disk, other)?
2. What are acceptable RPO/RTO targets?
3. Which environments require backups (prod only, staging too)?
