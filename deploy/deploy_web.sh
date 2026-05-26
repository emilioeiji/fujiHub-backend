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

validate_api_url() {
  if [[ -z "${VITE_API_URL:-}" ]]; then
    die "VITE_API_URL está vazio. Configure deploy/deploy.env antes do build. Exemplo: VITE_API_URL=https://api.emilioeiji.com.br"
  fi

  if [[ "$VITE_API_URL" == *localhost* || "$VITE_API_URL" == *127.0.0.1* ]]; then
    log_warn "VITE_API_URL aponta para localhost: $VITE_API_URL"
    if [[ "$MODE" == "safe" ]]; then
      die "Modo safe bloqueou build com API local."
    fi
  fi

  export VITE_API_URL
  log_ok "VITE_API_URL: $VITE_API_URL"
}

install_dependencies() {
  if [[ "${USE_NPM_CI:-true}" == "true" && -f package-lock.json ]]; then
    run npm ci
  else
    run npm install
  fi
}

publish_build() {
  local build_dir="$WEB_DIR/${WEB_BUILD_DIR:-dist}"
  local publish_dir="${WEB_PUBLISH_DIR:-$build_dir}"

  [[ -d "$build_dir" ]] || die "Build não encontrado: $build_dir"

  if [[ "$publish_dir" == "$build_dir" ]]; then
    log_ok "Build já está no diretório servido: $publish_dir"
    return
  fi

  run mkdir -p "$publish_dir"

  if command -v rsync >/dev/null 2>&1; then
    run rsync -a --delete "$build_dir"/ "$publish_dir"/
  else
    log_warn "rsync não encontrado. Usando cópia com rm/cp."
    run rm -rf "$publish_dir"
    run mkdir -p "$publish_dir"
    run cp -a "$build_dir"/. "$publish_dir"/
  fi

  log_ok "Build publicado em $publish_dir"
}

health_check() {
  local url="${WEB_HEALTH_URL:-}"
  if [[ -z "$url" ]]; then
    log_warn "WEB_HEALTH_URL vazio. Health check HTTP ignorado."
    return
  fi

  local status
  status="$(curl -k -sS -o /dev/null -w '%{http_code}' "$url" || true)"
  case "$status" in
    2*|3*) log_ok "Frontend respondeu $status em $url" ;;
    *) die "Frontend health check falhou em $url com status ${status:-sem resposta}" ;;
  esac
}

reload_web_server() {
  local service_name="${WEB_SERVER_SERVICE:-${NGINX_SERVICE:-}}"

  if [[ -z "$service_name" ]]; then
    log_warn "WEB_SERVER_SERVICE vazio. Reload do web server ignorado."
    return
  fi

  run systemctl_cmd reload "$service_name"
  log_ok "Web server recarregado: $service_name"
}

main() {
  validate_mode
  load_config

  : "${WEB_DIR:?WEB_DIR não definido}"
  local branch="${WEB_BRANCH:-master}"

  log_ok "Deploy web iniciado em modo $MODE"
  update_repo "$WEB_DIR" "$branch" "Frontend"

  cd "$WEB_DIR"
  validate_api_url
  install_dependencies
  run npm run build
  publish_build

  reload_web_server

  health_check
  log_ok "Deploy web concluído"
}

main "$@"
