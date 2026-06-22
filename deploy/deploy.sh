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
# CLI overrides (empty unless passed). Resolution precedence:
#   CLI flag  >  --env-file value  >  built-in default
# ---------------------------------------------------------------------------
CLI_SCENARIO=""; CLI_ENV_NAME=""; CLI_LOCATION=""; CLI_RESOURCE_GROUP=""
CLI_NAME_PREFIX=""; CLI_SUBSCRIPTION=""; CLI_TENANT=""
CLI_CUSTOM_ZONE=""; CLI_CUSTOM_HOST=""
ENV_FILE=""
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
  --env-file <path>        Load settings from a file (e.g. .env.external.local).
                           Honors EXTERNAL_AZURE_CONFIG_DIR to use an ISOLATED az
                           login (your default/internal az session is untouched),
                           EXTERNAL_TENANT_ID, SUBSCRIPTION, LOCATION, SCENARIO,
                           ENV_NAME, and the safety rails E2E_EXPECTED_TENANT_ID /
                           E2E_EXPECTED_SUBSCRIPTION_NAME.
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
  --tenant <id>            Expected tenant ID. Deploy aborts if the active login
                           is a different tenant (guards against wrong-tenant deploys).
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
  bash deploy/deploy.sh --env-file .env.external.local --what-if
  bash deploy/deploy.sh --env-file .env.external.local --scenario lab --yes
  bash deploy/deploy.sh --scenario apim --env-name agent-apim --yes
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --scenario) CLI_SCENARIO="${2:-}"; shift 2 ;;
    --env-name) CLI_ENV_NAME="${2:-}"; shift 2 ;;
    --location) CLI_LOCATION="${2:-}"; shift 2 ;;
    --resource-group) CLI_RESOURCE_GROUP="${2:-}"; shift 2 ;;
    --name-prefix) CLI_NAME_PREFIX="${2:-}"; shift 2 ;;
    --subscription) CLI_SUBSCRIPTION="${2:-}"; shift 2 ;;
    --tenant) CLI_TENANT="${2:-}"; shift 2 ;;
    --custom-zone) CLI_CUSTOM_ZONE="${2:-}"; shift 2 ;;
    --custom-host) CLI_CUSTOM_HOST="${2:-}"; shift 2 ;;
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

# Load the env file (if any) BEFORE resolving settings. It may set SCENARIO,
# ENV_NAME, LOCATION, SUBSCRIPTION, RESOURCE_GROUP, NAME_PREFIX, CUSTOM_ZONE,
# CUSTOM_HOST, EXTERNAL_TENANT_ID, EXTERNAL_AZURE_CONFIG_DIR, and the E2E_* rails.
if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: --env-file not found: $ENV_FILE" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  # Isolate the Azure CLI profile so the default/internal login is never touched.
  if [[ -n "${EXTERNAL_AZURE_CONFIG_DIR:-}" ]]; then
    _az_cfg="${EXTERNAL_AZURE_CONFIG_DIR/#\~/$HOME}"
    mkdir -p "$_az_cfg"
    export AZURE_CONFIG_DIR="$_az_cfg"
  fi
fi

# Resolve final settings: CLI > env file > default.
SCENARIO="${CLI_SCENARIO:-${SCENARIO:-lab}}"
ENV_NAME="${CLI_ENV_NAME:-${ENV_NAME:-agent-net-lab}}"
LOCATION="${CLI_LOCATION:-${LOCATION:-eastus}}"
RESOURCE_GROUP="${CLI_RESOURCE_GROUP:-${RESOURCE_GROUP:-}}"
NAME_PREFIX="${CLI_NAME_PREFIX:-${NAME_PREFIX:-}}"
SUBSCRIPTION="${CLI_SUBSCRIPTION:-${SUBSCRIPTION:-}}"
CUSTOM_ZONE="${CLI_CUSTOM_ZONE:-${CUSTOM_ZONE:-internal.agentlab.example}}"
CUSTOM_HOST="${CLI_CUSTOM_HOST:-${CUSTOM_HOST:-llm}}"
EXPECTED_TENANT="${CLI_TENANT:-${EXTERNAL_TENANT_ID:-${E2E_EXPECTED_TENANT_ID:-}}}"
EXPECTED_SUBSCRIPTION_NAME="${E2E_EXPECTED_SUBSCRIPTION_NAME:-}"

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
[[ -n "${AZURE_CONFIG_DIR:-}" ]] && log "az profile:      ${AZURE_CONFIG_DIR} (isolated)"
[[ -n "$EXPECTED_TENANT" ]] && log "Expected tenant: ${EXPECTED_TENANT}"
[[ "$WHATIF_ONLY" == true ]] && log "Mode:            WHAT-IF (preview; no billable resources are created)"

# --- Step 1: preflight tools + login ---
step "Preflight: tools and Azure login"
require_command az "Install: https://learn.microsoft.com/cli/azure/install-azure-cli"
require_command python3 "Install Python 3.10+ from https://www.python.org/downloads/"
if ! az account show >/dev/null 2>&1; then
  fail "You are not logged in to Azure (profile: ${AZURE_CONFIG_DIR:-default})."
  if [[ -n "${AZURE_CONFIG_DIR:-}" ]]; then
    log "Log in to this isolated profile, e.g.:"
    log "  AZURE_CONFIG_DIR=${AZURE_CONFIG_DIR} az login --tenant ${EXPECTED_TENANT:-<tenant-id>}"
  else
    log "Run: az login"
  fi
  exit 1
fi
if [[ -n "$SUBSCRIPTION" ]]; then
  run_cmd "Select subscription ${SUBSCRIPTION}" az account set --subscription "$SUBSCRIPTION"
fi
capture_cmd "Read current subscription" az account show --query "{name:name,id:id,tenantId:tenantId,user:user.name}" -o json
log "$CAPTURE"

# Safety rails: refuse to deploy if the active login is not the expected tenant/sub.
ACTIVE_TENANT="$(az account show --query tenantId -o tsv 2>/dev/null || true)"
ACTIVE_SUB_NAME="$(az account show --query name -o tsv 2>/dev/null || true)"
if [[ -n "$EXPECTED_TENANT" && "$ACTIVE_TENANT" != "$EXPECTED_TENANT" ]]; then
  fail "Active tenant ($ACTIVE_TENANT) does not match expected tenant ($EXPECTED_TENANT)."
  log "Refusing to deploy to the wrong tenant. Check --tenant / EXTERNAL_TENANT_ID and your login."
  exit 1
fi
if [[ -n "$EXPECTED_SUBSCRIPTION_NAME" && "$ACTIVE_SUB_NAME" != "$EXPECTED_SUBSCRIPTION_NAME" ]]; then
  fail "Active subscription ($ACTIVE_SUB_NAME) does not match expected ($EXPECTED_SUBSCRIPTION_NAME)."
  log "Refusing to deploy to the wrong subscription. Check SUBSCRIPTION / E2E_EXPECTED_SUBSCRIPTION_NAME."
  exit 1
fi
[[ -n "$EXPECTED_TENANT" ]] && ok "Tenant verified: $ACTIVE_TENANT"

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
# Group-scope validate/what-if need the RG to exist. An empty RG is free, so we
# create it even in --what-if mode; no billable resources are created there.
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
  ok "What-if complete. No billable resources were created."
  log "(An empty resource group '${RESOURCE_GROUP}' may exist for previewing — free.)"
  log "Re-run without --what-if to deploy. To remove the empty group:"
  log "  bash deploy/destroy.sh --resource-group ${RESOURCE_GROUP} --yes"
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

# For the lab scenario the expected private VIP is the storage private endpoint's
# NIC IP. Resolve it from the live resource (robust; bicep cannot read it reliably).
VIP_OVERRIDE=""
if [[ "$SCENARIO" == "lab" ]]; then
  PE_NAME="$(printf '%s' "$OUTPUTS_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("privateEndpointName",{}).get("value",""))' 2>/dev/null || true)"
  if [[ -n "$PE_NAME" ]]; then
    NIC_ID="$(az network private-endpoint show --resource-group "$RESOURCE_GROUP" --name "$PE_NAME" --query 'networkInterfaces[0].id' -o tsv 2>>"$LOG_FILE" || true)"
    if [[ -n "$NIC_ID" ]]; then
      VIP_OVERRIDE="$(az network nic show --ids "$NIC_ID" --query 'ipConfigurations[0].privateIPAddress' -o tsv 2>>"$LOG_FILE" || true)"
    fi
  fi
  if [[ -n "$VIP_OVERRIDE" ]]; then
    ok "Resolved private endpoint VIP: $VIP_OVERRIDE"
  else
    warn "Could not resolve the private endpoint VIP automatically; set expected_private_vip in config.json manually."
  fi
fi

if [[ -f "$CONFIG_FILE" ]]; then
  cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
  warn "Existing config.json backed up."
fi

printf '%s' "$OUTPUTS_JSON" | FANDX_VIP_OVERRIDE="$VIP_OVERRIDE" python3 "$SCRIPT_DIR/_write_config.py" "$CONFIG_FILE"
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
