from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from core.tables import DescRun, VmecRun

# (Model, primary-key field name, zip field, image/ancillary fields)
_FILE_MODELS = [
    (DescRun, "descrunid", "outputfile", ["surface_plot", "boozer_plot", "plot3d"]),
    (VmecRun, "vmecrunid", "outputfile", []),
]


class Command(BaseCommand):
    help = (
        "Scan the database for file-path fields that point to missing files. "
        "Records whose ZIP output file is missing are deleted entirely; "
        "records with only missing image/ancillary files have those fields cleared."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help=(
                "Apply fixes: delete records with a missing ZIP, "
                "clear fields for missing image/ancillary files."
            ),
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        deleted = 0
        cleared = 0

        for Model, pk_field, zip_field, ancillary_fields in _FILE_MODELS:
            for record in Model.objects.all():
                pk = getattr(record, pk_field)
                table = Model._meta.db_table

                # Check ZIP / primary output file
                zip_val = getattr(record, zip_field, "") or ""
                zip_missing = bool(zip_val and not default_storage.exists(zip_val))

                if zip_missing:
                    self.stdout.write(
                        f"  {table} #{pk}  {zip_field}: {zip_val!r}  → MISSING ZIP"
                    )
                    if fix:
                        record.delete()
                        self.stdout.write(f"    Deleted {table} #{pk}.")
                    deleted += 1
                    continue  # no point checking images if the record will be deleted

                # Check ancillary files (images, 3D plot)
                missing_ancillary = []
                for field in ancillary_fields:
                    val = getattr(record, field, "") or ""
                    if val and not default_storage.exists(val):
                        missing_ancillary.append(field)
                        self.stdout.write(
                            f"  {table} #{pk}  {field}: {val!r}  → missing"
                        )

                if missing_ancillary and fix:
                    for field in missing_ancillary:
                        setattr(record, field, "")
                    record.save(update_fields=missing_ancillary)
                cleared += len(missing_ancillary)

        if deleted == 0 and cleared == 0:
            self.stdout.write(self.style.SUCCESS("All file references are valid."))
            return

        if fix:
            self.stdout.write(
                self.style.WARNING(
                    f"Deleted {deleted} record(s) with missing ZIP. "
                    f"Cleared {cleared} missing image/ancillary field(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {deleted} record(s) with missing ZIP (would be deleted). "
                    f"Found {cleared} missing image/ancillary field(s) (would be cleared). "
                    f"Run with --fix to apply."
                )
            )
