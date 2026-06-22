#!/usr/bin/env bash
# =============================================================================
# foundry-agent-network-diagnostic — teardown
# -----------------------------------------------------------------------------
# Deletes the reproduction lab created by deploy/deploy.sh. Deletes the resource
# group (and everything in it), so only point it at a group you created for the lab.
# =============================================================================
set -Eeuo pipefail

RESOURCE_GROUP=""
SUBSCRIPTION=""
ENV_FILE=""
ASSUME_YES=false
NO_WAIT=false
NO_COLOR="${NO_COLOR:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$REPO_ROOT/.deployment"

usage() {
  cat <<'USAGE'
Usage:
  bash deploy/destroy.sh --resource-group <name> [options]

Options:
  --resource-group <name>  Resource group to delete (required).
  --env-file <path>        Load settings (e.g. .env.external.local). Honors
                           EXTERNAL_AZURE_CONFIG_DIR for an isolated az login.
  --subscription <id|name> Target subscription (default: current az context).
  --no-wait                Return immediately; deletion continues in the background.
  --yes                    Do not prompt for confirmation.
  --no-color               Disable ANSI color output.
  -h, --help               Show this help.

Example:
  bash deploy/destroy.sh --resource-group rg-agent-net-lab --yes
  bash deploy/destroy.sh --env-file .env.external.local --resource-group rg-agent-net-lab --yes
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group) RESOURCE_GROUP="${2:-}"; shift 2 ;;
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --subscription) SUBSCRIPTION="${2:-}"; shift 2 ;;
    --no-wait) NO_WAIT=true; shift ;;
    --yes) ASSUME_YES=true; shift ;;
    --no-color) NO_COLOR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# Load env file first (may set SUBSCRIPTION and the isolated az profile).
if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: --env-file not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  if [[ -n "${EXTERNAL_AZURE_CONFIG_DIR:-}" ]]; then
    _az_cfg="${EXTERNAL_AZURE_CONFIG_DIR/#\~/$HOME}"
    mkdir -p "$_az_cfg"
    export AZURE_CONFIG_DIR="$_az_cfg"
  fi
fi

if [[ -z "$RESOURCE_GROUP" ]]; then
  echo "Error: --resource-group is required." >&2
  usage >&2
  exit 2
fi

if [[ -t 1 && -z "$NO_COLOR" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/destroy-$(date +%Y%m%d-%H%M%S).log"

log()  { printf '%s\n' "$*" | tee -a "$LOG_FILE"; }
ok()   { log "${C_GREEN}[OK]${C_RESET} $*"; }
warn() { log "${C_YELLOW}[WARN]${C_RESET} $*"; }
fail() { log "${C_RED}[FAIL]${C_RESET} $*"; }

if ! command -v az >/dev/null 2>&1; then
  fail "az CLI is required."; exit 1
fi
if ! az account show >/dev/null 2>&1; then
  fail "Not logged in to Azure. Run: az login"; exit 1
fi
if [[ -n "$SUBSCRIPTION" ]]; then
  az account set --subscription "$SUBSCRIPTION"
fi

if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  warn "Resource group '$RESOURCE_GROUP' not found. Nothing to delete."
  exit 0
fi

log "${C_BLUE}About to DELETE resource group:${C_RESET} ${C_BOLD}${RESOURCE_GROUP}${C_RESET}"
log "${C_DIM}This removes every resource it contains and cannot be undone.${C_RESET}"
az resource list --resource-group "$RESOURCE_GROUP" --query "[].{name:name,type:type}" -o table 2>/dev/null | tee -a "$LOG_FILE" || true

if [[ "$ASSUME_YES" != true ]]; then
  printf '%s' "${C_YELLOW}Type the resource group name to confirm: ${C_RESET}"
  read -r reply || true
  if [[ "$reply" != "$RESOURCE_GROUP" ]]; then
    warn "Confirmation did not match. Aborted."
    exit 0
  fi
fi

DELETE_ARGS=(group delete --name "$RESOURCE_GROUP" --yes)
[[ "$NO_WAIT" == true ]] && DELETE_ARGS+=(--no-wait)

log "${C_DIM}\$ az ${DELETE_ARGS[*]}${C_RESET}"
if az "${DELETE_ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"; then
  if [[ "$NO_WAIT" == true ]]; then
    ok "Deletion started for '$RESOURCE_GROUP' (running in background)."
  else
    ok "Deleted resource group '$RESOURCE_GROUP'."
  fi
else
  fail "Deletion failed. See log: $LOG_FILE"
  exit 1
fi
