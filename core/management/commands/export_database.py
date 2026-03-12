import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand

from core.tables import Configuration, DescRun, Device, Publication, VmecRun

# Django names FK attnames as field_name + "_id"; remap to the actual DB column names.
_FK_RENAMES = {
    "device_id": "deviceid",
    "config_id": "configid",
    "publication_id": "publicationid",
}

_TABLES = [
    ("devices", Device),
    ("configurations", Configuration),
    ("publications", Publication),
    ("desc_runs", DescRun),
    ("vmec_runs", VmecRun),
]


class Command(BaseCommand):
    help = "Dump all database tables to CSV files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default=".",
            help="Directory to write CSV files into (default: current directory).",
        )

    def handle(self, *args, **options):
        out_dir = options["output_dir"]
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for table_name, Model in _TABLES:
            rows = list(Model.objects.values())
            if not rows:
                self.stdout.write(f"  {table_name}: 0 rows — skipped")
                continue

            # Rename FK attnames to their DB column names
            cleaned = [
                {_FK_RENAMES.get(k, k): v for k, v in row.items()} for row in rows
            ]

            path = os.path.join(out_dir, f"{table_name}_{stamp}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(cleaned[0].keys()))
                writer.writeheader()
                writer.writerows(cleaned)

            self.stdout.write(
                self.style.SUCCESS(f"  {table_name}: {len(cleaned)} rows → {path}")
            )

        self.stdout.write(self.style.SUCCESS("Export complete."))
