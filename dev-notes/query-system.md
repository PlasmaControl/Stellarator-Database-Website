# Query System

The query page (`/query/`) lets users filter any table and select output columns across related tables. It works through a chain of AJAX calls and a server-side SQL builder.

---

## User Flow

1. User picks a **table** (e.g. `configurations`)
2. The page fetches available **filter columns** (`/api/columns/single/`) — only the chosen table's own columns
3. User optionally enters a **filter column + criteria** (SQL syntax, e.g. `>5`, `LIKE '%W7%'`)
4. User picks **output columns** (`/api/columns/`) — includes columns from related tables
5. On submit, the form POSTs to `/api/query/` which returns an HTML table fragment

---

## API Endpoints

### `GET /api/columns/single/?tableName=X`

Returns `<option>` elements for the filter column dropdown. Only the primary table's own columns are included (users can only filter on columns that belong to the table they're querying).

### `GET /api/columns/?tableName=X`

Returns `<option>` elements for the output column multi-select. Includes columns from related tables, prefixed with the table name (e.g. `configurations.NFP`, `devices.name`).

### `POST /api/query/`

Parameters: `qtable`, `qfin` (filter column), `qthr` (filter criteria), `qfout` (comma-separated output columns).

Returns an HTML `<table>` fragment injected directly into the page.

---

## How `api_query` Builds SQL

```
SELECT {output_cols} + {hidden_extras}
FROM {qtable}
{LEFT JOINs from _JOINS[qtable]}
[WHERE {qtable}.{qfin} {operator} %s]
```

### Column whitelisting (SQL injection prevention)

All column and table names are validated against `_OUTPUT_COLUMNS` before being interpolated into SQL. Filter values are passed as parameterised arguments (`%s`), never interpolated directly.

### Automatic column additions

The view always adds certain columns to the SELECT even if the user didn't choose them, hiding them from the display but using them for link/media generation:

| Condition | Hidden columns added |
|---|---|
| `desc_runs` in result | `descrunid`, `surface_plot`, `boozer_plot`, `desc_outputfile` |
| `vmec_runs` in result | `vmecrunid`, `vmec_outputfile` |

`outputfile` columns are aliased (`desc_outputfile`, `vmec_outputfile`) to prevent name collision when both are in the same query.

Additionally:
- The **primary key** of the queried table is always forced to the first visible column
- The **filter column** (if used) is always added to the output right after the PK, even if the user didn't select it

### Column output order

1. DESC Details link (if desc_runs data is present)
2. VMEC Details link (if vmec_runs data is present)
3. Primary key of the queried table
4. Filter column (if applied)
5. User-selected columns
6. Surface Plot / Boozer Plot / Download (if desc_runs data is present)

---

## `_OUTPUT_COLUMNS`

Defined in `core/views.py`. Maps each table to a dict of `{table_name: [columns]}`. The group whose key equals the queried table name holds the filterable main columns; other keys are related tables.

```python
_OUTPUT_COLUMNS = {
    "desc_runs": {
        "desc_runs": ["descrunid", "version", ...],        # filterable
        "configurations": ["configurations.NFP", ...],     # related
        "devices": ["devices.name"],                       # related
        "publications": ["publications.DOI", ...],         # related
    },
    ...
}
```

---

## `_JOINS`

Defines the LEFT JOIN chain for each primary table. Only the joins needed to reach all related columns are included. vmec_runs and desc_runs connect to devices **indirectly** through configurations.

```python
_JOINS = {
    "desc_runs": [
        "LEFT JOIN configurations ON desc_runs.configid = configurations.configid",
        "LEFT JOIN devices ON configurations.deviceid = devices.deviceid",
        "LEFT JOIN publications ON desc_runs.publicationid = publications.publicationid",
    ],
    ...
}
```

---

## Adding a New Queryable Column

1. Add the column to the field list in `core/tables.py` and run migrations
2. Add it to the appropriate group in `_OUTPUT_COLUMNS` in `core/views.py`
3. If it belongs to a new related table, also add the JOIN to `_JOINS`

---

## Download Buttons

After a query runs, the JS reads hidden `<div>` elements embedded in the result HTML:

- `#dl-all-meta` with `data-runids="1,2,3"` → shows **DOWNLOAD ALL DESC FILES** button
- `#dl-vmec-meta` with `data-runids="4,5"` → shows **DOWNLOAD ALL VMEC FILES** button

These POST to `/download-all/` and `/download-all-vmec/` respectively, which zip the requested files server-side and stream them as a single download.

---

## Filter Criteria Parsing

The `_parse_criteria` function in `views.py` accepts SQL-style expressions:

| Input | Resulting SQL |
|---|---|
| `>5` | `col > 5` |
| `= 'SOLOVEV'` | `col = 'SOLOVEV'` |
| `LIKE '%W7%'` | `col LIKE '%W7%'` |
| `>=2.5` | `col >= 2.5` |

The value is always passed as a parameterised argument — it is never interpolated into the SQL string.
