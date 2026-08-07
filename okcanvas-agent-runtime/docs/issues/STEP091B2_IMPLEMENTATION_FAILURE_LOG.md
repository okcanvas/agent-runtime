# STEP091B2 Implementation Failure Log

This document records implementation and packaging failures encountered while adding the PostgreSQL
Product and Submission atomic store. Product defects and test/packaging defects must remain distinct.

## Initial environment limitation

The current Linux build environment did not provide `psycopg`, PostgreSQL server binaries, Docker, or
an installable package index entry for psycopg. Therefore this step must not claim PostgreSQL-live
acceptance from this environment. The adapter is validated through deterministic SQL/transaction
contracts and must receive a real PostgreSQL Windows or Linux live acceptance before promotion.

## Full-suite package identity regression

Partition 11 found that the historical STEP084 test correctly tracked the current `PACKAGE_STEP` but still pinned the STEP091B1 default ZIP filename. The test was aligned to the STEP091B2 package identity. Product behavior was unaffected.

## Second current package filename regression

Partition 12 found the STEP089 routing regression test also pinned the prior STEP091B1 default ZIP filename. The current package expectation was aligned to STEP091B2; historical behavior assertions were unchanged.
