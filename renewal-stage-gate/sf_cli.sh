# sf_cli.sh — Salesforce CLI shim (no MCP). Same pattern as gh_cli.sh / snow.
# Reads the persistent sfdx auth URL from salesforce_auth.env (a `force://…@…` line,
# minted once on Aman's Mac via `sf org auth show-sfdx-auth-url`), logs the sandbox in,
# and runs read-only SOQL. Never prints the auth URL.
#
# Usage:
#   source "<BenOps folder>/sf_cli.sh"
#   soql "SELECT COUNT(Id) n FROM Opportunity"                 # default CSV to stdout
#   soql "SELECT Id, StageName FROM Opportunity LIMIT 5" json  # json | csv | human
#   sf_ready        # force (re)login without querying
#
# Notes:
#   - sf state is kept under SF_HOME=/tmp/sfhome (avoids the /sessions inode issue).
#   - sf is installed to /tmp/npm-global (ephemeral per session; sf_ensure re-installs if missing).
#   - Default org alias = gusto. Override SF_ORG / SF_NPM_PREFIX / SF_HOME before sourcing.

_sf_dir() { cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd; }
: "${SF_NPM_PREFIX:=/tmp/npm-global}"
: "${SF_HOME:=/tmp/sfhome}"
: "${SF_ORG:=gusto}"
export PATH="$SF_NPM_PREFIX/bin:$PATH"
mkdir -p "$SF_HOME" 2>/dev/null
# SELF-HEAL (2026-10-02): a prior run under a DIFFERENT sandbox uid can leave the
# default /tmp/sfhome owned by nobody:nogroup, so this run can't write the sf log
# (EACCES on $SF_HOME/.sf/sf-YYYY-MM-DD.log). The shim then misreports it as
# "auth expired/revoked". If SF_HOME isn't writable, fall back to a fresh per-run
# dir so login succeeds (re-login from salesforce_auth.env is silent + fast).
# /tmp is the sandbox, not the cowork mount, so creating a fresh dir here is fine.
if ! { mkdir -p "$SF_HOME/.sf" 2>/dev/null && touch "$SF_HOME/.sf/.wtest" 2>/dev/null; }; then
  SF_HOME="$(mktemp -d "${TMPDIR:-/tmp}/sfhome.XXXXXX")"
  echo "sf_cli: default SF_HOME not writable (stale/foreign-owned) — using fresh $SF_HOME" >&2
  mkdir -p "$SF_HOME/.sf" 2>/dev/null
fi
rm -f "$SF_HOME/.sf/.wtest" 2>/dev/null
export SF_HOME

sf_ensure() {
  command -v sf >/dev/null 2>&1 && return 0
  echo "sf_cli: installing @salesforce/cli -> $SF_NPM_PREFIX (one-time this session)…" >&2
  NPM_CONFIG_PREFIX="$SF_NPM_PREFIX" npm install -g @salesforce/cli >/tmp/sf_install.log 2>&1
  export PATH="$SF_NPM_PREFIX/bin:$PATH"
  command -v sf >/dev/null 2>&1 || { echo "sf_cli: install failed (see /tmp/sf_install.log)" >&2; return 1; }
}

sf_login() {
  sf_ensure || return 1
  local f="$(_sf_dir)/salesforce_auth.env"
  [ -f "$f" ] || { echo "sf_cli: salesforce_auth.env not found next to sf_cli.sh" >&2; return 1; }
  HOME="$SF_HOME" sf org login sfdx-url --sfdx-url-file "$f" --alias "$SF_ORG" >/dev/null 2>&1 \
    || { echo "sf_cli: login failed — auth URL may be expired/revoked; re-mint on the Mac" >&2; return 1; }
}

# idempotent: only logs in if the org isn't already connected in this SF_HOME
sf_ready() {
  sf_ensure || return 1
  HOME="$SF_HOME" sf org display --target-org "$SF_ORG" >/dev/null 2>&1 && return 0
  sf_login
}

# soql "<SOQL>" [csv|json|human]  -> read-only query against $SF_ORG (auto-login)
soql() {
  local q="$1" fmt="${2:-csv}"
  [ -n "$q" ] || { echo "usage: soql \"SELECT …\" [csv|json|human]" >&2; return 2; }
  sf_ready || return 1
  HOME="$SF_HOME" sf data query --target-org "$SF_ORG" --query "$q" --result-format "$fmt"
}
