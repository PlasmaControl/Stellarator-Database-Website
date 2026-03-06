# Updating the Database Schema

Django manages schema changes through **migrations** — versioned files that describe every change made to the database structure. Never alter the database directly; always go through Django's migration system so the history stays consistent across all environments.

---

## Where the Schema Lives

All table definitions are in `core/tables.py`. Each table is defined as a list of field tuples:

```python
("column_name", type, "description")
```

- `type` is `"str"`, `"text"`, `"int"`, `"float"`, `"bool"`, or `None` (system-managed fields like PKs, FKs, and dates).
- The Django model classes are generated from these lists at the bottom of `tables.py` using `type(...)`.

To add, rename, or remove a column, edit the field list and then follow the migration steps below.

---

## General Workflow

```bash
# 1. Edit core/tables.py (or the model class for system-set fields)
# 2. Generate a migration
python manage.py makemigrations

# 3. Preview the SQL that will run (optional but recommended)
python manage.py sqlmigrate core 0003   # replace with actual migration number

# 4. Apply the migration
python manage.py migrate
```

Always commit the generated migration file together with your model changes.

---

## Adding a New Column

1. Add the field tuple to the appropriate list in `core/tables.py`.
2. Run `makemigrations` + `migrate`.
3. All existing rows will have `NULL` for the new column (fields default to `null=True, blank=True`).
4. If you also want to expose the column in the query page, add it to `_OUTPUT_COLUMNS` in `core/views.py` under the right table group.

---

## Renaming a Column

Django cannot automatically detect a rename — it sees a delete + add and will ask interactively:

```bash
python manage.py makemigrations
# Django asks: "Did you rename X to Y? [y/N]"  → answer y
python manage.py migrate
```

The generated migration will use `RenameField`, which preserves all existing data.

If you also rename the DB column (via `db_column` on a ForeignKey), you may need to write the migration by hand — see the Django docs on `AlterField`.

---

## Removing a Column

1. Delete the field tuple from `core/tables.py`.
2. Run `makemigrations` + `migrate`.
3. The column and all its data are permanently deleted. Back up the database first if the data may be needed.

---

## Adding a New Table

1. Create a new field list (e.g. `MY_TABLE_FIELDS`) in `core/tables.py`.
2. Create the model class at the bottom of `tables.py` using the same `type(...)` pattern as the existing models.
3. Register it in `core/admin.py` if you want it visible in the admin panel.
4. Run `makemigrations` + `migrate`.
5. Add it to `_OUTPUT_COLUMNS` and `_JOINS` in `core/views.py` if it should be queryable.

---

## Inspecting Migration State

```bash
python manage.py showmigrations           # list all migrations and whether they're applied
python manage.py sqlmigrate core 0002     # show SQL for a specific migration
```

---

## On Production (AWS)

Always run `migrate` **before** restarting Gunicorn when deploying schema changes:

```bash
python manage.py migrate
sudo systemctl restart gunicorn
```

This ensures the new columns/tables exist before the new code tries to use them.

---

## Reverting a Migration

To roll back to a previous migration:

```bash
python manage.py migrate core 0002   # rolls back everything after 0002
```

Then delete the unwanted migration file and re-run `makemigrations` if needed. Only do this in development; rolling back on production risks data loss.

---

## What NOT to Do

- Do not edit existing migration files — Django uses the full chain to reconstruct history.
- Do not delete migration files.
- Do not alter the database tables directly (e.g. via `psql` or SQLite browser) without a corresponding migration — Django's state will go out of sync and future `makemigrations` will produce incorrect diffs.
