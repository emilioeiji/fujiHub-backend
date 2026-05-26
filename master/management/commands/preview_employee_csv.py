from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from master.csv_import import MAPPING_USED, parse_employee_rows, preview_employee_import, read_csv_rows


class Command(BaseCommand):
    help = "Preview employee CSV import without changing database."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to MT.csv")
        parser.add_argument(
            "--update-empty",
            action="store_true",
            help="Allow empty CSV fields to clear existing data.",
        )
        parser.add_argument(
            "--limit-warnings",
            type=int,
            default=20,
            help="Maximum warning samples to print.",
        )
        parser.add_argument(
            "--limit-errors",
            type=int,
            default=20,
            help="Maximum error samples to print.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists() or not csv_path.is_file():
            raise CommandError(f"CSV not found: {csv_path}")

        update_empty = bool(options["update_empty"])
        limit_warnings = max(0, int(options["limit_warnings"]))
        limit_errors = max(0, int(options["limit_errors"]))

        with csv_path.open("rb") as csv_file:
            rows, detected_headers = read_csv_rows(csv_file)

        parsed_rows = parse_employee_rows(rows, update_empty=update_empty)
        preview = preview_employee_import(parsed_rows)

        self.stdout.write(self.style.MIGRATE_HEADING("Employee CSV Preview"))
        self.stdout.write(f"File: {csv_path}")
        self.stdout.write(f"Update empty fields: {update_empty}")
        self.stdout.write("")
        self.stdout.write(f"Total rows: {preview['total_rows']}")
        self.stdout.write(f"Creates: {preview['creates']}")
        self.stdout.write(f"Updates: {preview['updates']}")
        self.stdout.write(f"Unchanged: {preview['unchanged']}")
        self.stdout.write(f"Total errors: {len(preview['errors'])}")
        self.stdout.write(f"Total warnings: {len(preview['warnings'])}")
        self.stdout.write("")
        self.stdout.write("Detected headers:")
        for header in detected_headers:
            self.stdout.write(f"- {header}")
        self.stdout.write("")
        self.stdout.write("Mapping used:")
        for source, target in MAPPING_USED.items():
            self.stdout.write(f"- {source} -> {target}")
        self.stdout.write("")

        creates_samples = [row for row in preview["sample_rows"] if row["action"] == "create"][:5]
        updates_samples = [row for row in preview["sample_rows"] if row["action"] == "update"][:5]
        self.stdout.write("Sample rows to create:")
        if creates_samples:
            for row in creates_samples:
                self.stdout.write(
                    f"- row={row['row']} employee_id={row['employee_id']} changed={','.join(row['changed_fields']) or '-'}"
                )
        else:
            self.stdout.write("- none")
        self.stdout.write("Sample rows to update:")
        if updates_samples:
            for row in updates_samples:
                self.stdout.write(
                    f"- row={row['row']} employee_id={row['employee_id']} changed={','.join(row['changed_fields']) or '-'}"
                )
        else:
            self.stdout.write("- none")
        self.stdout.write("")

        self.stdout.write(f"Top warnings (limit {limit_warnings}):")
        warnings = preview["warnings"][:limit_warnings]
        if warnings:
            for warning in warnings:
                self.stdout.write(
                    f"- row={warning['row']} employee_id={warning['employee_id'] or '-'} :: {' | '.join(warning['messages'])}"
                )
        else:
            self.stdout.write("- none")

        self.stdout.write(f"Top errors (limit {limit_errors}):")
        errors = preview["errors"][:limit_errors]
        if errors:
            for error in errors:
                self.stdout.write(
                    f"- row={error['row']} employee_id={error['employee_id'] or '-'} :: {' | '.join(error['messages'])}"
                )
        else:
            self.stdout.write("- none")

        if preview["errors"]:
            raise CommandError(f"Preview finished with {len(preview['errors'])} error(s).")

        self.stdout.write(self.style.SUCCESS("Preview finished with no critical errors."))
