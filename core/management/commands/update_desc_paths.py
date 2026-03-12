from django.core.management.base import BaseCommand
from django.db.models import Q

from core.tables import DescRun

PREFIX = "descruns/"
FIELDS = ["outputfile", "surface_plot", "boozer_plot", "plot3d"]


class Command(BaseCommand):
    help = "Prepend 'descruns/' to existing DESC run file paths that don't already have it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be changed without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Find runs that have at least one path not yet prefixed
        needs_update = Q()
        for field in FIELDS:
            needs_update |= Q(**{f"{field}__gt": ""}) & ~Q(
                **{f"{field}__startswith": PREFIX}
            )

        runs = DescRun.objects.filter(needs_update)
        count = 0

        for run in runs:
            changed = []
            for field in FIELDS:
                val = getattr(run, field, "") or ""
                if val and not val.startswith(PREFIX):
                    new_val = PREFIX + val
                    if dry_run:
                        self.stdout.write(
                            f"  run #{run.descrunid} {field}: {val!r} → {new_val!r}"
                        )
                    else:
                        setattr(run, field, new_val)
                    changed.append(field)

            if changed and not dry_run:
                run.save(update_fields=changed)
            if changed:
                count += 1

        label = "Would update" if dry_run else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{label} {count} DESC run record(s)."))
