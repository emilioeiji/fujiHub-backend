from django.core.management.base import BaseCommand, CommandError

from operations.models import ProductionMonitorSource
from operations.services import import_production_snapshot


class Command(BaseCommand):
    help = "Importa snapshot de produção a partir de arquivo TXT/CSV."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, type=int, help="ID de ProductionMonitorSource.")
        parser.add_argument("--file", required=True, help="Caminho do arquivo TXT/CSV.")
        parser.add_argument("--dry-run", action="store_true", help="Valida e calcula métricas sem gravar.")
        parser.add_argument("--encoding", default="utf-8", help="Encoding do arquivo (ex: utf-8, shift_jis).")
        parser.add_argument(
            "--delimiter",
            default="auto",
            choices=["auto", ",", "tab", "semicolon"],
            help="Delimitador do arquivo.",
        )
        parser.add_argument("--shift", default="", help="Shift ID ou code para override.")
        parser.add_argument("--process", default="", help="Process ID ou code para override.")
        parser.add_argument("--area", default="", help="Área para override.")

    def handle(self, *args, **options):
        source_id = options["source"]
        file_path = options["file"]
        dry_run = bool(options["dry_run"])

        source = ProductionMonitorSource.objects.filter(pk=source_id).first()
        if not source:
            raise CommandError(f"Source {source_id} não encontrado.")

        try:
            result = import_production_snapshot(
                source=source,
                file_path=file_path,
                encoding=options["encoding"],
                delimiter=options["delimiter"],
                shift=options["shift"] or None,
                process=options["process"] or None,
                area=options["area"] or "",
                dry_run=dry_run,
            )
        except Exception as exc:
            raise CommandError(f"Falha na importação: {exc}") from exc

        mode = "DRY RUN" if dry_run else "IMPORTAÇÃO"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] linhas processadas: {result['rows_count']}"))
        self.stdout.write(
            f"Snapshot: {result['created_snapshot_id'] or '-'} | Capturado em: {result['captured_at']}"
        )
        self.stdout.write(
            f"KPI total={result['metrics']['production_total']} meta={result['metrics']['target_total']} "
            f"diff={result['metrics']['difference_total']} kadouritsu={result['metrics']['average_kadouritsu']}%"
        )
        self.stdout.write(
            f"running={result['metrics']['running_count']} stopped={result['metrics']['stopped_count']} "
            f"idle={result['metrics']['idle_count']} error={result['metrics']['error_count']} alarms={result['metrics']['alarms_active']}"
        )
        for warning in result.get("warnings", []):
            self.stdout.write(self.style.WARNING(f"Aviso: {warning}"))
