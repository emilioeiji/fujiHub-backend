from django.core.management.base import BaseCommand, CommandError

from operations.services import import_timecard_csv


class Command(BaseCommand):
    help = "Importa registros de cartão ponto a partir de CSV Shift_JIS/CP932."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Caminho do arquivo CSV.")
        parser.add_argument(
            "--encoding",
            default="cp932",
            choices=["cp932", "shift_jis", "utf-8"],
            help="Encoding do arquivo.",
        )
        parser.add_argument(
            "--delimiter",
            default="auto",
            choices=["auto", ",", "tab", "semicolon"],
            help="Delimitador do arquivo.",
        )
        parser.add_argument("--month", default="", help="Filtro opcional por mês no formato YYYY-MM.")
        parser.add_argument("--dry-run", action="store_true", help="Valida sem gravar no banco.")

    def handle(self, *args, **options):
        file_path = options["file"]
        month = options["month"] or None
        dry_run = bool(options["dry_run"])

        try:
            result = import_timecard_csv(
                file_path=file_path,
                encoding=options["encoding"],
                delimiter=options["delimiter"],
                month=month,
                dry_run=dry_run,
                source_file=file_path,
            )
        except Exception as exc:
            raise CommandError(f"Falha na importacao de cartão ponto: {exc}") from exc

        mode = "DRY RUN" if dry_run else "IMPORTACAO"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] linhas processadas: {result['rows_count']}"))
        self.stdout.write(
            f"criados={result.get('created', 0)} atualizados={result.get('updated', 0)} duplicados={result.get('duplicate_count', 0)}"
        )
        for warning in result.get("warnings", []):
            self.stdout.write(self.style.WARNING(f"Aviso: {warning}"))
