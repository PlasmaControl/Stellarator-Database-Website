# Stellarator Database

A web application for sharing, uploading, and querying DESC and VMEC stellarator equilibrium data across universities and research institutions.

Built with Django. Developed by the [Princeton University Plasma Control Group](https://control.princeton.edu/).

---

## What it does

- **Upload** DESC equilibrium runs (ZIP + CSV) with associated device, configuration, and publication metadata
- **Query** the database with a flexible filter and output column builder — supports cross-table joins and SQL-style criteria
- **Browse** individual run details including embedded 3D Plotly visualisations, surface plots, and Boozer plots
- **Download** equilibrium files individually or in bulk for any query result
- **Admin-approved** user accounts — new registrations require approval before access is granted

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5 (Python) |
| Database | SQLite (local dev) / PostgreSQL on AWS RDS |
| File storage | Local filesystem (local dev) / AWS S3 |
| WSGI server | Gunicorn (production) |
| Frontend | Vanilla JS + jQuery DataTables |

---

## For Maintainers

The `dev-notes/` folder contains detailed documentation for common maintenance tasks:

| File | Contents |
|---|---|
| `dev-notes/local-development.md` | How to run the project locally for development |
| `dev-notes/aws-deployment.md` | Full AWS deployment and redeployment guide |
| `dev-notes/updating-database-schema.md` | How to add, rename, or remove columns and tables safely |
| `dev-notes/repository-structure.md` | File layout, key files explained, database table relationships |
| `dev-notes/query-system.md` | How the query page and SQL builder work internally |
| `dev-notes/management-commands.md` | How to run custom commands to update the database SQL |

---

## Contact

Princeton University Plasma Control Group
Yigit Gunsur Elmacioglu — yigit.elma@princeton.edu
