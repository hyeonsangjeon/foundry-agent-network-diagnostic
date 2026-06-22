#!/usr/bin/env bash
# =============================================================================
# foundry-agent-network-diagnostic — verify-existing (Method 2)
# -----------------------------------------------------------------------------
# For an environment that is ALREADY deployed. Collects your endpoint + network
# settings (via flags or interactive prompts), writes config.json, and runs the
# READ-ONLY diagnostic. Nothing is created or modified in Azure.
# =============================================================================
set -Eeuo pipefail

SUBSCRIPTION_ID=""
RESOURCE_GROUP=""
REGION=""
FOUNDRY_ACCOUNT=""
FOUNDRY_PROJECT=""
BACKEND_FQDN=""
EXPECTED_VIP=""
AGENT_SUBNET_ID=""
PE_SUBNET_ID=""
APIM_RESOURCE_ID=""
APIM_MODE=""
NO_DIAGNOSE=false
NO_COLOR="${NO_COLOR:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/config.json"

usage() {
  cat <<'USAGE'
Usage:
  bash deploy/verify-existing.sh [options]

Verify an environment that is already deployed. Any required value not passed as
a flag is prompted for interactively.

Required:
  --subscription-id <guid>
  --resource-group <name>
  --region <region>
  --foundry-account <name>
  --foundry-project <name>
  --backend-fqdn <fqdn>          e.g. llm.contoso-apim.contoso.example
  --expected-vip <ip>            Expected private VIP, e.g. 10.20.30.40

Optional:
  --agent-subnet-id <id>
  --pe-subnet-id <id>
  --apim-resource-id <id>
  --apim-mode <internal|external|PE|unknown>
  --no-diagnose                  Write config.json but do not run the diagnostic.
  --no-color                     Disable ANSI color output.
  -h, --help                     Show this help.

Example:
  bash deploy/verify-existing.sh \
    --subscription-id 00000000-0000-0000-0000-000000000000 \
    --resource-group rg-foundry --region eastus \
    --foundry-account my-foundry --foundry-project my-project \
    --backend-fqdn llm.my-apim.internal.example --expected-vip 10.20.30.40 \
    --apim-mode internal
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription-id) SUBSCRIPTION_ID="${2:-}"; shift 2 ;;
    --resource-group) RESOURCE_GROUP="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --foundry-account) FOUNDRY_ACCOUNT="${2:-}"; shift 2 ;;
    --foundry-project) FOUNDRY_PROJECT="${2:-}"; shift 2 ;;
    --backend-fqdn) BACKEND_FQDN="${2:-}"; shift 2 ;;
    --expected-vip) EXPECTED_VIP="${2:-}"; shift 2 ;;
    --agent-subnet-id) AGENT_SUBNET_ID="${2:-}"; shift 2 ;;
    --pe-subnet-id) PE_SUBNET_ID="${2:-}"; shift 2 ;;
    --apim-resource-id) APIM_RESOURCE_ID="${2:-}"; shift 2 ;;
    --apim-mode) APIM_MODE="${2:-}"; shift 2 ;;
    --no-diagnose) NO_DIAGNOSE=true; shift ;;
    --no-color) NO_COLOR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -t 1 && -z "$NO_COLOR" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi

ok()   { printf '%s\n' "${C_GREEN}[OK]${C_RESET} $*"; }
warn() { printf '%s\n' "${C_YELLOW}[WARN]${C_RESET} $*"; }
fail() { printf '%s\n' "${C_RED}[FAIL]${C_RESET} $*"; }

# Prompt for a value if it is still empty and we have a terminal.
prompt_if_empty() {
  local varname="$1" label="$2" current="${!1}"
  if [[ -n "$current" ]]; then return 0; fi
  if [[ ! -t 0 ]]; then return 0; fi
  local value
  printf '%s' "${C_BOLD}${label}:${C_RESET} " > /dev/tty
  read -r value < /dev/tty || true
  printf -v "$varname" '%s' "$value"
}

printf '%s\n' "${C_BLUE}foundry-agent-network-diagnostic — verify an existing environment${C_RESET}"
printf '%s\n' "Enter values for the deployed environment (or pass them as flags)."
echo

prompt_if_empty SUBSCRIPTION_ID  "Subscription ID (GUID)"
prompt_if_empty RESOURCE_GROUP   "Resource group"
prompt_if_empty REGION           "Region (e.g. eastus)"
prompt_if_empty FOUNDRY_ACCOUNT  "Foundry account name"
prompt_if_empty FOUNDRY_PROJECT  "Foundry project name"
prompt_if_empty BACKEND_FQDN     "Backend FQDN (e.g. llm.my-apim.internal.example)"
prompt_if_empty EXPECTED_VIP     "Expected private VIP (e.g. 10.20.30.40)"
echo
printf '%s\n' "Optional (press Enter to skip):"
prompt_if_empty AGENT_SUBNET_ID  "Agent subnet resource ID"
prompt_if_empty PE_SUBNET_ID     "Private endpoint subnet resource ID"
prompt_if_empty APIM_RESOURCE_ID "APIM resource ID"
prompt_if_empty APIM_MODE        "APIM mode (internal|external|PE|unknown)"

if [[ -f "$CONFIG_FILE" ]]; then
  cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
  warn "Existing config.json backed up."
fi

export FANDX_SUBSCRIPTION_ID="$SUBSCRIPTION_ID"
export FANDX_RESOURCE_GROUP="$RESOURCE_GROUP"
export FANDX_REGION="$REGION"
export FANDX_FOUNDRY_ACCOUNT="$FOUNDRY_ACCOUNT"
export FANDX_FOUNDRY_PROJECT="$FOUNDRY_PROJECT"
export FANDX_BACKEND_FQDN="$BACKEND_FQDN"
export FANDX_EXPECTED_VIP="$EXPECTED_VIP"
export FANDX_AGENT_SUBNET_ID="$AGENT_SUBNET_ID"
export FANDX_PE_SUBNET_ID="$PE_SUBNET_ID"
export FANDX_APIM_RESOURCE_ID="$APIM_RESOURCE_ID"
export FANDX_APIM_MODE="$APIM_MODE"

if ! python3 "$SCRIPT_DIR/_write_config_manual.py" "$CONFIG_FILE"; then
  fail "Could not write config.json — fill in all required values."
  exit 1
fi
ok "Wrote $CONFIG_FILE"

if [[ "$NO_DIAGNOSE" == true ]]; then
  ok "Skipped diagnostic (--no-diagnose)."
  printf '%s\n' "Run it later with:  python3 src/diagnose.py --config config.json"
  exit 0
fi

echo
printf '%s\n' "${C_BLUE}Running read-only diagnostic...${C_RESET}"
python3 "$REPO_ROOT/src/diagnose.py" --config "$CONFIG_FILE" --out-dir "$REPO_ROOT"

echo
ok "Done. Open the static report to verify:"
printf '%s\n' "  ${C_BOLD}${REPO_ROOT}/report.html${C_RESET}"
