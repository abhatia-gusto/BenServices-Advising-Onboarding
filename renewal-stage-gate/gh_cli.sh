# gh_cli.sh — lightweight GitHub CLI shim (no gh, no MCP).
# Mirrors the snow-CLI pattern: reads the local PAT (github_pat.env, bare ghp_ token),
# never prints it, talks to GitHub via curl (reads) + git (clone/commit/push).
#
# Usage:
#   source "<BenOps folder>/gh_cli.sh"
#   ghfetch advising-hub/queries/auto_renewal.sql            # print a file (default ref=main)
#   ghfetch advising-hub/catalog.json some-branch            # from a branch
#   ghtree  advising-hub/queries                             # list a directory (names only)
#   ghapi   /repos/$GH_REPO/pulls?state=open                 # raw API call (JSON)
#   ghclone [target-dir]                                     # authed clone of the repo
#   (inside a clone) ghpush                                  # push current branch with auth
#
# Defaults target the BenOps source-of-truth repo; override GH_OWNER/GH_REPO to reuse elsewhere.

_gh_dir() { cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd; }
GH_OWNER="${GH_OWNER:-abhatia-gusto}"
GH_REPO="${GH_REPO:-abhatia-gusto/BenServices-Advising-Onboarding}"

_gh_token() {
  local f="$(_gh_dir)/github_pat.env"
  [ -f "$f" ] || { echo "gh_cli: github_pat.env not found next to gh_cli.sh" >&2; return 1; }
  tr -d ' \n\r' < "$f"
}

# ghfetch <path-in-repo> [ref]  -> prints raw file contents
ghfetch() {
  local path="$1" ref="${2:-main}" tok; tok="$(_gh_token)" || return 1
  curl -fsSL -H "Authorization: token $tok" -H "Accept: application/vnd.github.raw" \
    "https://api.github.com/repos/$GH_REPO/contents/$path?ref=$ref"
}

# ghtree <dir-in-repo> [ref]  -> lists entry names (one per line)
ghtree() {
  local path="$1" ref="${2:-main}" tok; tok="$(_gh_token)" || return 1
  curl -fsSL -H "Authorization: token $tok" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$GH_REPO/contents/$path?ref=$ref" \
    | python3 -c "import sys,json;[print(e['type'][0]+' '+e['name']) for e in json.load(sys.stdin)]"
}

# ghapi <endpoint>  -> raw JSON from the API (endpoint starts with /)
ghapi() {
  local ep="$1" tok; tok="$(_gh_token)" || return 1
  curl -fsSL -H "Authorization: token $tok" -H "Accept: application/vnd.github+json" \
    "https://api.github.com$ep"
}

# ghclone [target-dir]  -> authed clone (token injected inline, not persisted to remote config)
ghclone() {
  local dir="${1:-$GH_REPO##*/}" tok; tok="$(_gh_token)" || return 1
  git clone "https://x-access-token:$tok@github.com/$GH_REPO.git" "$dir" \
    && git -C "$dir" remote set-url origin "https://github.com/$GH_REPO.git"  # scrub token from saved remote
}

# ghpush  -> push current branch using the PAT without persisting it in .git/config
ghpush() {
  local tok; tok="$(_gh_token)" || return 1
  local br; br="$(git rev-parse --abbrev-ref HEAD)"
  git -c "http.https://github.com/.extraheader=Authorization: token $tok" push -u origin "$br"
}
