#!/usr/bin/env bash
# =============================================================================
# foundry-agent-network-diagnostic — deploy-and-verify (Method 1)
# -----------------------------------------------------------------------------
# Provisions a small, real reproduction lab in YOUR subscription, then runs the
# READ-ONLY diagnostic against it and points you at the static HTML report.
#
# Progress UX (bar/step/run_cmd/ok/warn/fail + .deployment logs) is modeled on
# azure-ai-search-foundry-iq-live-knowledge-sources/scripts/deploy.sh.
#
# The diagnostic itself never mutates Azure. Only this script (and destroy.sh)
# create or delete resources, and only ones you own.
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Defaults / settings
# ---------------------------------------------------------------------------
SCENARIO="lab"
ENV_NAME="agent-net-lab"
LOCATION="eastus"
RESOURCE_GROUP=""
NAME_PREFIX=""
SUBSCRIPTION=""
CUSTOM_ZONE="internal.agentlab.example"
CUSTOM_HOST="llm"
DEPLOY_JUMP_VM=false
JUMP_VM_PASSWORD="${JUMP_VM_PASSWORD:-}"
WHATIF_ONLY=false
NO_DIAGNOSE=false
ASSUME_YES=false
NO_COLOR="${NO_COLOR:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BICEP_FILE="$SCRIPT_DIR/infra/main.bicep"
CONFIG_FILE="$REPO_ROOT/config.json"
LOG_DIR="$REPO_ROOT/.deployment"
LOG_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  bash deploy/deploy.sh [options]

Provisions a reproduction lab, then runs the read-only diagnostic against it.

Options:
  --scenario <lab|apim>    Reproduction scenario.
                           lab  = VNet + delegated agent subnet + private endpoint
                                  backend (fast, cheap, ~2-3 min). Default.
                           apim = adds API Management in internal VNet mode
                                  (faithful BYO AI Gateway path, slow ~45 min, costs more).
  --env-name <name>        Base name for the lab (default: agent-net-lab).
  --location <region>      Azure region (default: eastus). e.g. koreacentral, swedencentral.
  --resource-group <name>  Resource group (default: rg-<env-name>).
  --name-prefix <prefix>   Resource name prefix (3-12 lowercase). Default: auto.
  --subscription <id|name> Target subscription (default: current az context).
  --custom-zone <zone>     Custom private DNS zone (default: internal.agentlab.example).
  --custom-host <label>    Backend host label under the zone (default: llm).
  --deploy-jump-vm         Also deploy a small in-network jump VM (needs --vm-password).
  --vm-password <pwd>      Admin password for the jump VM (or set JUMP_VM_PASSWORD).
  --what-if                Preview changes only. Creates nothing. Free.
  --no-diagnose            Deploy only; skip running the diagnostic.
  --yes                    Do not prompt for confirmation before deploying.
  --no-color               Disable ANSI color output.
  -h, --help               Show this help.

Examples:
  bash deploy/deploy.sh --what-if
  bash deploy/deploy.sh --scenario lab --location koreacentral --yes
  bash deploy/deploy.sh --scenario apim --env-name agent-apim --yes
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="${2:-}"; shift 2 ;;
    --env-name) ENV_NAME="${2:-}"; shift 2 ;;
    --location) LOCATION="${2:-}"; shift 2 ;;
    --resource-group) RESOURCE_GROUP="${2:-}"; shift 2 ;;
    --name-prefix) NAME_PREFIX="${2:-}"; shift 2 ;;
    --subscription) SUBSCRIPTION="${2:-}"; shift 2 ;;
    --custom-zone) CUSTOM_ZONE="${2:-}"; shift 2 ;;
    --custom-host) CUSTOM_HOST="${2:-}"; shift 2 ;;
    --deploy-jump-vm) DEPLOY_JUMP_VM=true; shift ;;
    --vm-password) JUMP_VM_PASSWORD="${2:-}"; shift 2 ;;
    --what-if) WHATIF_ONLY=true; shift ;;
    --no-diagnose) NO_DIAGNOSE=true; shift ;;
    --yes) ASSUME_YES=true; shift ;;
    --no-color) NO_COLOR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$SCENARIO" in
  lab|apim) ;;
  *) echo "Invalid --scenario: $SCENARIO (expected lab or apim)" >&2; exit 2 ;;
esac

[[ -z "$RESOURCE_GROUP" ]] && RESOURCE_GROUP="rg-${ENV_NAME}"

# ---------------------------------------------------------------------------
# Colors / logging
# ---------------------------------------------------------------------------
if [[ -t 1 && -z "$NO_COLOR" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"

# Total steps depend on the run shape.
TOTAL_STEPS=6
if [[ "$WHATIF_ONLY" != true ]]; then
  TOTAL_STEPS=$((TOTAL_STEPS + 2))           # deploy + write config
  [[ "$NO_DIAGNOSE" != true ]] && TOTAL_STEPS=$((TOTAL_STEPS + 1))  # diagnose
fi
CURRENT_STEP=0

log() { printf '%s\n' "$*" | tee -a "$LOG_FILE"; }
plain_log() { printf '%s\n' "$*" >> "$LOG_FILE"; }

bar() {
  local current="$1" total="$2" width=24
  local filled=$(( current * width / total ))
  local empty=$(( width - filled ))
  printf '['
  printf '%*s' "$filled" '' | tr ' ' '#'
  printf '%*s' "$empty" '' | tr ' ' '-'
  printf '] %d/%d' "$current" "$total"
}

header() {
  cat <<'BANNER' | tee -a "$LOG_FILE"

+---------------------------------------------------------------------+
| foundry-agent-network-diagnostic                                    |
| Method 1: deploy a reproduction lab, then run the read-only checks  |
+---------------------------------------------------------------------+
BANNER
  log "Log file: $LOG_FILE"
  log ""
}

step() {
  CURRENT_STEP=$(( CURRENT_STEP + 1 ))
  log ""
  log "${C_BLUE}$(bar "$CURRENT_STEP" "$TOTAL_STEPS")${C_RESET} ${C_BOLD}${1}${C_RESET}"
  log "$(printf '%*s' 72 '' | tr ' ' '-')"
}

ok()   { log "${C_GREEN}[OK]${C_RESET} $*"; }
warn() { log "${C_YELLOW}[WARN]${C_RESET} $*"; }
fail() { log "${C_RED}[FAIL]${C_RESET} $*"; }

print_cleanup_hint() {
  log ""
  log "To remove anything that was created, run:"
  log "  bash deploy/destroy.sh --resource-group ${RESOURCE_GROUP}"
}

run_cmd() {
  local description="$1"; shift
  log "${C_DIM}\$ $*${C_RESET}"
  plain_log ""; plain_log ">>> $description"; plain_log ">>> $*"
  set +e
  "$@" 2>&1 | tee -a "$LOG_FILE"
  local status=${PIPESTATUS[0]}
  set -e
  if [[ "$status" -ne 0 ]]; then
    fail "$description"; log "Exit code: $status"; log "See log: $LOG_FILE"
    print_cleanup_hint
    exit "$status"
  fi
  ok "$description"
}

# Like run_cmd but captures stdout to a variable (CAPTURE) instead of teeing.
CAPTURE=""
capture_cmd() {
  local description="$1"; shift
  plain_log ""; plain_log ">>> $description"; plain_log ">>> $*"
  set +e
  CAPTURE="$("$@" 2>>"$LOG_FILE")"
  local status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    fail "$description"; log "Exit code: $status"; log "See log: $LOG_FILE"
    print_cleanup_hint
    exit "$status"
  fi
  ok "$description"
}

probe_cmd() {
  local description="$1"; shift
  log "${C_DIM}\$ $*${C_RESET}"
  set +e
  "$@" 2>&1 | tee -a "$LOG_FILE"
  local status=${PIPESTATUS[0]}
  set -e
  if [[ "$status" -ne 0 ]]; then
    warn "$description failed; continuing."
    return 0
  fi
  ok "$description"
}

require_command() {
  local name="$1" hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    fail "$name is required."; log "$hint"; exit 1
  fi
  ok "$name found: $(command -v "$name")"
}

confirm() {
  [[ "$ASSUME_YES" == true ]] && return 0
  local reply
  printf '%s' "${C_YELLOW}Proceed with deployment to subscription above? [y/N] ${C_RESET}"
  read -r reply || true
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) warn "Aborted by user."; exit 0 ;;
  esac
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
header
log "Scenario:        ${SCENARIO}"
log "Resource group:  ${RESOURCE_GROUP}"
log "Location:        ${LOCATION}"
log "Backend FQDN:    ${CUSTOM_HOST}.${CUSTOM_ZONE}"
[[ "$WHATIF_ONLY" == true ]] && log "Mode:            WHAT-IF (no resources will be created)"

# --- Step 1: preflight tools + login ---
step "Preflight: tools and Azure login"
require_command az "Install: https://learn.microsoft.com/cli/azure/install-azure-cli"
require_command python3 "Install Python 3.10+ from https://www.python.org/downloads/"
if ! az account show >/dev/null 2>&1; then
  fail "You are not logged in to Azure."
  log "Run: az login"
  exit 1
fi
if [[ -n "$SUBSCRIPTION" ]]; then
  run_cmd "Select subscription ${SUBSCRIPTION}" az account set --subscription "$SUBSCRIPTION"
fi
capture_cmd "Read current subscription" az account show --query "{name:name,id:id,user:user.name}" -o json
log "$CAPTURE"

# --- Step 2: resolve settings ---
step "Resolve deployment settings"
if [[ "$SCENARIO" == "apim" ]]; then
  warn "apim scenario provisions API Management (Developer). This can take ~45 minutes and incurs cost."
fi
if [[ "$DEPLOY_JUMP_VM" == true && -z "$JUMP_VM_PASSWORD" ]]; then
  fail "--deploy-jump-vm requires --vm-password (or JUMP_VM_PASSWORD env)."
  exit 2
fi
ok "Settings resolved."

# --- Step 3: register resource providers ---
step "Register required resource providers"
probe_cmd "Register Microsoft.Network"  az provider register --namespace Microsoft.Network  --wait
probe_cmd "Register Microsoft.Storage"  az provider register --namespace Microsoft.Storage  --wait
probe_cmd "Register Microsoft.App"      az provider register --namespace Microsoft.App      --wait
if [[ "$SCENARIO" == "apim" ]]; then
  probe_cmd "Register Microsoft.ApiManagement" az provider register --namespace Microsoft.ApiManagement --wait
fi
if [[ "$DEPLOY_JUMP_VM" == true ]]; then
  probe_cmd "Register Microsoft.Compute" az provider register --namespace Microsoft.Compute --wait
fi

# --- Step 4: resource group ---
step "Ensure resource group"
run_cmd "Create/verify resource group ${RESOURCE_GROUP}" \
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --tags project=foundry-agent-network-diagnostic purpose=repro-lab -o none

# Common bicep parameters.
BICEP_PARAMS=(
  scenario="$SCENARIO"
  customDnsZoneName="$CUSTOM_ZONE"
  customBackendHost="$CUSTOM_HOST"
  deployJumpVm="$DEPLOY_JUMP_VM"
  location="$LOCATION"
)
[[ -n "$NAME_PREFIX" ]] && BICEP_PARAMS+=( namePrefix="$NAME_PREFIX" )
[[ "$DEPLOY_JUMP_VM" == true ]] && BICEP_PARAMS+=( adminPassword="$JUMP_VM_PASSWORD" )

# --- Step 5: validate template ---
step "Validate Bicep template"
run_cmd "Validate deployment" \
  az deployment group validate \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$BICEP_FILE" \
    --parameters "${BICEP_PARAMS[@]}" \
    -o none

# --- Step 6: what-if preview ---
step "Preview changes (what-if)"
probe_cmd "What-if analysis" \
  az deployment group what-if \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$BICEP_FILE" \
    --parameters "${BICEP_PARAMS[@]}"

if [[ "$WHATIF_ONLY" == true ]]; then
  log ""
  ok "What-if complete. No resources were created."
  log "Re-run without --what-if to deploy."
  exit 0
fi

confirm

# --- Step 7: deploy ---
step "Deploy reproduction lab"
DEPLOY_NAME="fandx-$(date +%Y%m%d-%H%M%S)"
run_cmd "Deploy infrastructure (${DEPLOY_NAME})" \
  az deployment group create \
    --name "$DEPLOY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$BICEP_FILE" \
    --parameters "${BICEP_PARAMS[@]}" \
    -o none

# --- Step 8: generate config.json ---
step "Generate config.json from deployment outputs"
capture_cmd "Read deployment outputs" \
  az deployment group show --resource-group "$RESOURCE_GROUP" --name "$DEPLOY_NAME" --query properties.outputs -o json
OUTPUTS_JSON="$CAPTURE"

if [[ -f "$CONFIG_FILE" ]]; then
  cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
  warn "Existing config.json backed up."
fi

printf '%s' "$OUTPUTS_JSON" | python3 "$SCRIPT_DIR/_write_config.py" "$CONFIG_FILE"
ok "Wrote $CONFIG_FILE"
plain_log "$(cat "$CONFIG_FILE")"

# --- Step 9: run diagnostic ---
if [[ "$NO_DIAGNOSE" == true ]]; then
  log ""
  ok "Deployment complete. Skipped diagnostic (--no-diagnose)."
  log "Run it later with:  python3 src/diagnose.py --config config.json"
  print_cleanup_hint
  exit 0
fi

step "Run read-only diagnostic"
log "Note: the lab has no Foundry account, so Foundry-specific checks may report"
log "      SKIPPED/manual — that is expected. Network-path checks run for real."
run_cmd "Diagnose" python3 "$REPO_ROOT/src/diagnose.py" --config "$CONFIG_FILE" --out-dir "$REPO_ROOT"

log ""
ok "Done. Open the static report to verify:"
log "  ${C_BOLD}${REPO_ROOT}/report.html${C_RESET}"
log ""
log "When finished, tear everything down with:"
log "  bash deploy/destroy.sh --resource-group ${RESOURCE_GROUP}"
