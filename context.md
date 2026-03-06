# Project context

## Workspace
- Project folder: Petpooja
- Key files:
  - schema.sql: PostgreSQL schema for restaurant system tables.
  - seed_static.sql / final_static_seed.sql: static seed data for menu, addons, combos.
  - generate_data_final.py / generate_data_final (1).py: Python data generator for customers, orders, inventory, etc.

## Database
- Target DB: postgres
- Host/port: localhost:5432 (IPv6 ::1)
- Schema: public
- Verified: public.customers exists in postgres.

## Script behavior (generate_data_final (1).py)
- Connects to PostgreSQL and prints current DB info.
- Inserts customers (currently commented out to avoid re-inserting duplicates).
- Generates orders, order_items, addons, payments, KOT, offer_redemptions, feedback, inventory_log.
- Resets sequences at end and prints row counts + sanity checks.

## Fixes applied
- Converted numpy-derived values to native Python types before inserts to avoid psycopg2 errors:
  - Cast qty/discount to int.
  - Cast prices/totals/tax to float.
  - Cast channel/method to str.
  - Cast feedback ratings to int.
- IDs now start from current max values in tables to avoid duplicate key errors on reruns.
- Customers block commented out by user to avoid duplicate inserts.

## Recent runtime issues and resolutions
- "relation customers does not exist": due to running the wrong file and/or different DB context.
  - Resolved by running the correct script and verifying DB context.
- "schema np does not exist": caused by numpy types in SQL parameters.
  - Resolved by casting numpy values to native types.
- "can't adapt type numpy.int64": caused by numpy int in feedback ratings.
  - Resolved by casting to int.

## How to run
- Use quotes for filename with parentheses:
  - python "generate_data_final (1).py"

## Notes
- If customers already inserted, keep customers block disabled.
- If re-running, ID counters now auto-start from MAX(id) in each table.