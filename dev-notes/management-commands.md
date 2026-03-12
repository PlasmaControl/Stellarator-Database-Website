# Management Commands

Django management commands are scripts run from the terminal via `manage.py`. They have full access to the Django ORM and settings, making them safe for bulk database operations that would be awkward or risky to do through the admin panel or raw SQL.

Run any command from the project root (same directory as `manage.py`):

```bash
python manage.py <command_name> [options]
```

All custom commands live in `core/management/commands/`.

---

## `export_database`

Dumps every table to a CSV file. Produces one file per table, with a timestamp in the filename so repeated exports don't overwrite each other.

**Tables exported:** `devices`, `configurations`, `publications`, `desc_runs`, `vmec_runs`

```bash
# Export to the current directory
python manage.py export_database

# Export to a specific folder (created automatically if it doesn't exist)
python manage.py export_database --output-dir exports/
```

**Output files** (example with `--output-dir exports/`):

```
exports/
  devices_20260312_143000.csv
  configurations_20260312_143000.csv
  publications_20260312_143000.csv
  desc_runs_20260312_143000.csv
  vmec_runs_20260312_143000.csv
```

Column headers match the actual database column names (`configid`, `deviceid`, etc.).

---

## `fix_missing_files`

Scans every `DescRun` and `VmecRun` record for file-path fields that point to files that no longer exist in storage (local `test-storage/` or S3, depending on environment). Useful after manually moving or deleting files.

**Behaviour by field:**

| Field | If missing |
|---|---|
| `outputfile` (ZIP) | **Delete the entire record** — a run without its output file is not useful |
| `surface_plot`, `boozer_plot`, `plot3d` | Clear the field (set to empty string) — the record is kept |

```bash
# Preview — print what would change without touching the database
python manage.py fix_missing_files

# Apply: delete records with missing ZIPs, clear missing image fields
python manage.py fix_missing_files --fix
```

Always run without `--fix` first to review what would be changed.

---

## `update_desc_paths`

One-time migration command. Prepends `descruns/` to existing DESC run file paths in the database that don't already have it.

This is needed when migrating from the old flat layout (`desc-id-{N}/...`) to the new nested layout (`descruns/desc-id-{N}/...`). After running this command, all stored paths will match the new folder structure.

```bash
# Preview — print every path change without writing to the database
python manage.py update_desc_paths --dry-run

# Apply the changes
python manage.py update_desc_paths
```

**Migration procedure:**

1. On the server, move all `desc-id-*` folders into a new `descruns/` parent folder.
2. Run `python manage.py update_desc_paths --dry-run` to confirm the changes look correct.
3. Run `python manage.py update_desc_paths` to update the database.

This command is idempotent — running it a second time will find nothing to update (all paths already start with `descruns/`).
