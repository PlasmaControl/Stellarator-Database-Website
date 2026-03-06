# Local Development Setup

No AWS account or environment variables are needed for local development. Django falls back to SQLite and local file storage automatically.

---

## Prerequisites

- Python 3.10+
- pip

---

## Setup

```bash
git clone https://github.com/Plasma-Control/Stellarator-Database-Website.git
cd Stellarator-Database-Website

# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # creates your admin login
python manage.py runserver
```

The site is now running at `http://127.0.0.1:8000/`.

---

## What runs locally

| Component | Local equivalent |
|---|---|
| PostgreSQL (RDS) | SQLite file at `db.sqlite3` |
| S3 file storage | Local directory `test-storage/` |
| Gunicorn | Django's built-in dev server (`runserver`) |

Both `db.sqlite3` and `test-storage/` are gitignored — they exist only on your machine.

---

## Approving a User Account

New registrations require admin approval. To approve your own test account:

1. Log in at `/admin/` with the superuser credentials
2. Go to **Core → Users**, open the account, tick **Is approved**, save

Or via the shell:
```bash
python manage.py shell
>>> from core.models import User
>>> User.objects.filter(username='yourname').update(is_approved=True)
```

---

## Testing File Uploads

Sample ZIP and CSV files are in `sample-data/`. Use them on the Upload page to create test records without needing real DESC output.

After uploading, files land in `test-storage/desc-id-{N}/`.

---

## Running After a Schema Change

If you pull changes that include new migrations:

```bash
python manage.py migrate
```

If you change `core/tables.py` yourself:

```bash
python manage.py makemigrations
python manage.py migrate
```

See `dev-notes/updating-database-schema.md` for the full schema change workflow.

---

## Common Issues

**`No module named 'psycopg2'`** — this is only needed for PostgreSQL (AWS). It is safe to ignore for local dev since SQLite is used instead.

**`OperationalError: no such table`** — you forgot to run `migrate` after a pull.

**Uploaded files not showing** — check that `MEDIA_URL` is `/media/` and `MEDIA_ROOT` points to `test-storage/`. These are the defaults when `ON_AWS` is not set.
