# AWS Deployment Guide

This project runs on an EC2 instance backed by an RDS PostgreSQL database and an S3 bucket for file storage.

---

## AWS Infrastructure Required

| Service | Purpose |
|---|---|
| EC2 | Application server (runs Django + Gunicorn) |
| RDS (PostgreSQL) | Main relational database |
| S3 | File storage for uploaded equilibria, plots, etc. |

---

## First-Time Setup on a Fresh EC2 Instance

### 1. Install Python

**Amazon Linux 2023:**
```bash
sudo dnf install -y python3.13 python3-pip git
```

**Ubuntu:**
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Clone the repo and create a virtual environment

```bash
git clone https://github.com/PlasmaControl/Stellarator-Database-Website.git
cd Stellarator-Database-Website
python3.13 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Fill in all values in .env
set -a; source .env; set +a
```

To check that environment variables are set correctly and python can access them, run `python -c "import os; print('Host:', os.environ.get('DB_HOST'))"`, if this prints `Host: None`, there is trouble.

All required variables are documented in `.env.example`. The critical ones:

| Variable | Notes |
|---|---|
| `ON_AWS` | Must be `true` — switches database, storage, and security settings |
| `SECRET_KEY` | Long random string; generate with `python -c "import secrets; print(secrets.token_hex(50))"` |
| `ALLOWED_HOSTS` | Your domain or EC2 public IP, comma-separated |
| `CSRF_TRUSTED_ORIGINS` | Full HTTPS origins, e.g. `https://yourdomain.com` — can be left empty when testing over HTTP |
| `SECURE_SSL_REDIRECT` | Defaults to `true`. Set to `false` when testing over HTTP without a domain. **Remove this line for real HTTPS deployments.** |
| `DB_*` | RDS connection details |
| `S3_*` | S3 bucket name, region, and IAM credentials |

### 4. Prepare the application

```bash
python manage.py migrate          # Create/update database tables
python manage.py collectstatic    # Copy static files to staticfiles/
python manage.py createsuperuser  # Create the first admin account
```

### 5. Run Gunicorn as a systemd service

Running Gunicorn directly in a terminal will kill it when the SSH session closes. Use systemd to keep it running permanently.

Create the service file:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Paste the following (adjust `User` and paths if your username or install location differs):

```ini
[Unit]
Description=Gunicorn for Stellarator DB
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/Stellarator-Database-Website
EnvironmentFile=/home/ec2-user/Stellarator-Database-Website/.env
ExecStart=/home/ec2-user/Stellarator-Database-Website/venv/bin/gunicorn \
    stellarator_db.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers 3
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

The `EnvironmentFile` line loads `.env` automatically — no need to `source .env` manually.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn   # auto-start on reboot
sudo systemctl start gunicorn
sudo systemctl status gunicorn   # verify it's running
```

Useful commands:

```bash
sudo systemctl restart gunicorn  # after code updates
sudo systemctl stop gunicorn     # shut down for maintenance (auto-starts on reboot)
sudo systemctl start gunicorn    # bring it back up
sudo systemctl disable gunicorn  # disable auto-start on reboot
sudo systemctl enable gunicorn   # re-enable auto-start on reboot
sudo journalctl -u gunicorn -f   # view live logs
```

---

## Redeployment (Code Updates)

When pushing new code to the running server:

```bash
source venv/bin/activate
git pull
pip install -r requirements.txt        # only needed if requirements changed
python manage.py migrate               # run BEFORE restarting the server
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
```

**Important:** Always run `migrate` before restarting — the new code may depend on schema changes that must exist before it starts serving requests.

---

## How the ON_AWS Flag Changes Behaviour

`settings.py` checks `os.environ.get("ON_AWS")` at startup and switches:

| Setting | Local (default) | AWS (`ON_AWS=true`) |
|---|---|---|
| `DEBUG` | `True` | `False` |
| Database | SQLite (`db.sqlite3`) | PostgreSQL (RDS) |
| File storage | `test-storage/` (local) | S3 via `django-storages` |
| `MEDIA_URL` | `/media/` | `https://<bucket>.s3.amazonaws.com/` |
| Static file serving | Django dev server | WhiteNoise (served by Gunicorn) |
| SSL redirect + secure cookies | Off | Controlled by `SECURE_SSL_REDIRECT` env var (default: on) |

Media files are never served by Django on AWS — they are served directly from S3 via public URLs stored in the database.

---

## S3 Bucket Configuration

- The bucket must allow public read on uploaded files (or use pre-signed URLs — current code uses public URLs).
- `AWS_S3_FILE_OVERWRITE = False` is set in `settings.py`, so uploading a file with the same name creates a new file with a suffixed name rather than overwriting.
- Uploaded files are organised under `descruns/desc-id-{descrunid}/` subdirectories.

---

## User Account Management

New registrations are **not** auto-approved. An admin must approve each account:

1. Go to `/admin/core/user/`
2. Open the user record
3. Tick **Is approved** and save

Alternatively, use the Django shell:
```bash
python manage.py shell
>>> from core.models import User
>>> User.objects.filter(username='someone').update(is_approved=True)
```

---

## Common Troubleshooting

| Symptom | Likely cause |
|---|---|
| 500 on startup, `MEDIA_ROOT` error | `ON_AWS` not set; the local media URL route tries to use `MEDIA_ROOT` which is undefined on AWS |
| CSRF errors on POST forms | `CSRF_TRUSTED_ORIGINS` not set or doesn't match the origin header |
| Static files returning 404 | `collectstatic` not run after deploy |
| Login/sessions not working over HTTP | `SECURE_SSL_REDIRECT` not set to `false`; secure cookies require HTTPS |
| SSL handshake errors in server log | Browser trying HTTPS because of `SECURE_SSL_REDIRECT=true`; set it to `false` for HTTP testing |
| Database connection refused | RDS security group doesn't allow inbound from EC2's security group on port 5432 |
| S3 upload fails | IAM user lacks `s3:PutObject` / `s3:GetObject` on the bucket |
| Gunicorn stops when SSH session closes | Run it as a systemd service (see setup step 5) |
