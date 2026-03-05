# Stellarator Database

A web application for sharing and querying DESC stellarator equilibrium data across universities and research institutions.

Built with Django. Developed by the [Princeton University Plasma Physics Control Group](https://control.princeton.edu/).

---

## Features

- Upload DESC equilibrium runs (ZIP + CSV) with associated device, configuration, and publication metadata
- Query the database with a flexible filter/output column builder
- Admin-approved user accounts

---

## Local Development Setup

### Prerequisites

- Python 3.10+
- pip

### Install

```bash
git clone https://github.com/Plasma-Control/Stellarator-Database-Website.git
cd Stellarator-Database-Website
pip install Django
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

No environment variables are needed for local dev — defaults to SQLite and local file storage.

Uploaded files are stored in `test-storage/` (excluded from git).

---

## Deployment (AWS)

### Install Python

On a fresh Amazon Linux 2023 / Ubuntu EC2 instance, install Python 3 if it isn't already present:

**Amazon Linux 2023:**
```bash
sudo dnf install -y python3 python3-pip
```

**Ubuntu:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

### Clone the repository

```bash
git clone https://github.com/Plasma-Control/Stellarator-Database-Website.git
cd Stellarator-Database-Website
```

### Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

The `(venv)` prefix in your prompt confirms the environment is active. Always activate it before running any project commands.

### Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env`, fill in real values, and export them before starting the server:

```bash
cp .env.example .env
# edit .env with your values
source .env
```

| Variable | Description |
|---|---|
| `ON_AWS` | Set to `true` to enable AWS mode (PostgreSQL + S3) |
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames |
| `DB_NAME` | PostgreSQL database name |
| `DB_HOST` | RDS endpoint |
| `DB_USER` | Database username |
| `DB_PASS` | Database password |
| `DB_PORT` | Database port (default: 5432) |
| `S3_BUCKET` | S3 bucket name for file uploads |
| `S3_REGION` | AWS region (e.g. `us-east-1`) |
| `S3_ACCESS_KEY` | AWS access key ID |
| `S3_SECRET_KEY` | AWS secret access key |

### Migrate and collect static files

```bash
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
```

---

## Project Structure

```
StellaratorWebsite/
├── manage.py
├── requirements.txt
├── .env.example            # Template for environment variables
├── stellarator_db/         # Django project settings and URL config
│   ├── settings.py
│   └── urls.py
└── core/                   # Main application
    ├── models.py           # User, Device, Configuration, Publication, DescRun, VmecRun
    ├── views.py            # Page views and AJAX query API
    ├── urls.py
    ├── forms.py
    ├── admin.py
    ├── migrations/         # Creates required tables/columns for SQL (don't change)
    ├── static/core/css/    # Custom CSS for styling
    └── templates/core/     # HTML that is rendered for pages
```

---

## User Accounts

New user registrations require admin approval before login is permitted. Approve accounts via the Django admin panel at `/admin/core/user/`.

---

## Developer Notes

- `ON_AWS=false` (default): uses SQLite (`db.sqlite3`) and local storage (`test-storage/`). Neither is committed to git.
- `ON_AWS=true`: switches to PostgreSQL and S3. Requires `psycopg2-binary`, `django-storages`, and `boto3`.
- The query API endpoint (`/api/query/`) uses a column whitelist to prevent SQL injection — never pass raw user input to SQL directly.
- All file uploads are stored per DESC run under a subdirectory named by `descrunid`.

---

## Contact

Princeton University Plasma Physics Control Group
Yigit Gunsur Elmacioglu — ye2698@princeton.edu
