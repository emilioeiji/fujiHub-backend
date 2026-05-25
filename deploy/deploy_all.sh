#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-safe}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${DEPLOY_ENV:-$SCRIPT_DIR/deploy.env}"

log_ok() { printf '[OK] %s\n' "$*"; }
log_error() { printf '[ERROR] %s\n' "$*" >&2; }

die() {
  log_error "$*"
  exit 1
}

case "$MODE" in
  safe|force) ;;
  *) die "Modo inválido: $MODE. Use: safe ou force." ;;
esac

if [[ ! -f "$ENV_FILE" && ! -f "$SCRIPT_DIR/deploy.env.example" ]]; then
  die "Nenhum deploy.env ou deploy.env.example encontrado em $SCRIPT_DIR"
fi

log_ok "Deploy completo FujiHub iniciado em modo $MODE"

DEPLOY_ENV="$ENV_FILE" "$SCRIPT_DIR/deploy_backend.sh" "$MODE"
DEPLOY_ENV="$ENV_FILE" "$SCRIPT_DIR/deploy_web.sh" "$MODE"

log_ok "Deploy completo FujiHub concluído"
