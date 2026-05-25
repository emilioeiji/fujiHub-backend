#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-safe}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${DEPLOY_ENV:-$SCRIPT_DIR/deploy.env}"
ENV_EXAMPLE="$SCRIPT_DIR/deploy.env.example"

log_ok() { printf '[OK] %s\n' "$*"; }
log_warn() { printf '[WARN] %s\n' "$*"; }
log_error() { printf '[ERROR] %s\n' "$*" >&2; }

die() {
  log_error "$*"
  exit 1
}

run() {
  printf '      %s\n' "$*"
  "$@"
}

systemctl_cmd() {
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl "$@"
  else
    sudo systemctl "$@"
  fi
}

journalctl_cmd() {
  if [[ "$(id -u)" -eq 0 ]]; then
    journalctl "$@"
  else
    sudo journalctl "$@"
  fi
}

load_config() {
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    log_ok "Configuração carregada: $ENV_FILE"
    return
  fi

  [[ -f "$ENV_EXAMPLE" ]] || die "Nenhum arquivo de configuração encontrado em $ENV_FILE ou $ENV_EXAMPLE"
  # shellcheck disable=SC1090
  source "$ENV_EXAMPLE"
  log_warn "deploy.env não encontrado. Usando deploy.env.example como fallback."
}

validate_mode() {
  case "$MODE" in
    safe|force) ;;
    *) die "Modo inválido: $MODE. Use: safe ou force." ;;
  esac
}

handle_local_changes() {
  local label="$1"
  local changes
  changes="$(git status --porcelain)"

  if [[ -z "$changes" ]]; then
    log_ok "$label sem alterações locais"
    return
  fi

  log_warn "$label possui alterações locais:"
  git status --short

  if [[ "$MODE" == "safe" ]]; then
    die "Deploy abortado no modo safe. Faça commit/stash manual ou rode em force."
  fi

  case "${FORCE_STRATEGY:-stash}" in
    stash)
      local stash_msg
      stash_msg="deploy auto stash $(date -u +%Y%m%dT%H%M%SZ)"
      run git stash push -u -m "$stash_msg"
      log_ok "$label alterações preservadas em stash: $stash_msg"
      ;;
    reset)
      log_warn "$label FORCE_STRATEGY=reset vai descartar alterações locais"
      run git reset --hard HEAD
      run git clean -fd
      ;;
    *)
      die "FORCE_STRATEGY inválido: ${FORCE_STRATEGY:-}. Use stash ou reset."
      ;;
  esac
}

update_repo() {
  local repo_dir="$1"
  local branch="$2"
  local label="$3"

  [[ -d "$repo_dir/.git" ]] || die "$label não é um repositório Git válido: $repo_dir"
  cd "$repo_dir"

  local current_branch
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  log_ok "$label branch atual: $current_branch"

  handle_local_changes "$label"

  run git fetch origin "$branch"

  if [[ "$current_branch" != "$branch" ]]; then
    if [[ "$MODE" == "safe" ]]; then
      die "$label está na branch '$current_branch', esperado '$branch'."
    fi
    run git checkout "$branch"
  fi

  run git pull --ff-only origin "$branch"
  log_ok "$label atualizado"
}

load_backend_env_file() {
  if [[ -f "$API_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$API_DIR/.env"
    set +a
    log_ok "Variáveis do backend carregadas de $API_DIR/.env"
  else
    log_warn "$API_DIR/.env não encontrado. Usando ambiente atual."
  fi
}

activate_venv() {
  : "${VENV_DIR:?VENV_DIR não definido}"
  [[ -f "$VENV_DIR/bin/activate" ]] || die "Virtualenv não encontrado em $VENV_DIR"
  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"
  log_ok "Virtualenv ativado: $VENV_DIR"
}

health_check() {
  local url="${BACKEND_HEALTH_URL:-}"
  if [[ -z "$url" ]]; then
    log_warn "BACKEND_HEALTH_URL vazio. Health check HTTP ignorado."
    return
  fi

  local status
  status="$(curl -k -sS -o /dev/null -w '%{http_code}' "$url" || true)"
  case "$status" in
    2*|3*) log_ok "Backend respondeu $status em $url" ;;
    *) die "Backend health check falhou em $url com status ${status:-sem resposta}" ;;
  esac
}

main() {
  validate_mode
  load_config

  : "${API_DIR:?API_DIR não definido}"
  : "${BACKEND_SERVICE:?BACKEND_SERVICE não definido}"
  local branch="${BACKEND_BRANCH:-main}"

  log_ok "Deploy backend iniciado em modo $MODE"
  update_repo "$API_DIR" "$branch" "Backend"

  cd "$API_DIR"
  load_backend_env_file
  activate_venv

  run python -m pip install -r requirements.txt
  run python manage.py migrate

  if [[ "${RUN_COLLECTSTATIC:-true}" == "true" ]]; then
    run python manage.py collectstatic --noinput
  else
    log_warn "collectstatic ignorado porque RUN_COLLECTSTATIC=false"
  fi

  run python manage.py check
  run systemctl_cmd restart "$BACKEND_SERVICE"
  log_ok "Serviço reiniciado: $BACKEND_SERVICE"

  health_check

  log_ok "Status do serviço $BACKEND_SERVICE"
  systemctl_cmd status "$BACKEND_SERVICE" --no-pager || true

  log_ok "Logs recentes do serviço $BACKEND_SERVICE"
  journalctl_cmd -u "$BACKEND_SERVICE" -n "${BACKEND_LOG_LINES:-80}" --no-pager || true

  log_ok "Deploy backend concluído"
}

main "$@"
