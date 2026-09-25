#!/usr/bin/env bash
# Link the frozen scientific artifacts from the Render persistent disk into the
# repository tree before the API starts.
#
# The application resolves every artifact relative to the repository root
# (backend/agents/investigation/data_access.py, backend/api/projections.py), and
# those artifacts are gitignored, so a git-based deploy checks out without them.
# The disk holds the exact files unpacked from
# deploy/smartess-scientific-artifacts.tar; this script only creates symlinks.
#
# It never regenerates, rewrites, or synthesises an artifact, and it never
# overwrites a file that is tracked in git: a repository path that already
# exists is left alone.
#
# Local development is unaffected. When the disk is absent the script logs what
# is missing and exits 0, so `GET /readiness` reports precise blockers instead of
# the service entering a crash loop.
set -euo pipefail

ARTIFACT_ROOT="${SMARTESS_ARTIFACT_ROOT:-/var/data}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '%s bootstrap %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if [ ! -d "$ARTIFACT_ROOT" ]; then
  log "ERROR artifact root $ARTIFACT_ROOT does not exist; scientific artifacts unavailable"
  log "seed it once from the Render shell: tar -xf deploy/smartess-scientific-artifacts.tar -C $ARTIFACT_ROOT"
  exit 0
fi

# Investigation records are written at runtime
# (backend/agents/investigation/persistence.py INVESTIGATIONS_ROOT), so this
# directory is linked whole rather than per-file. That puts new investigations on
# the disk, where they survive a restart or redeploy.
INV_REL="ml/datasets/investigations"
INV_DISK="$ARTIFACT_ROOT/$INV_REL"
INV_REPO="$REPO_ROOT/$INV_REL"

mkdir -p "$INV_DISK/reference"
if [ ! -L "$INV_REPO" ]; then
  # Preserve anything the checkout brought in (reference/healthy-reference.json
  # is tracked) by copying it onto the disk before replacing the directory.
  if [ -d "$INV_REPO" ]; then
    cp -R "$INV_REPO/." "$INV_DISK/" 2>/dev/null || true
    rm -rf "$INV_REPO"
  fi
  ln -s "$INV_DISK" "$INV_REPO"
  log "linked $INV_REL -> $INV_DISK (writable, persistent)"
fi

# Everything else is read-only and linked file by file, so a tracked file is
# never shadowed by the disk copy.
linked=0
skipped=0
while IFS= read -r -d '' src; do
  rel="${src#"$ARTIFACT_ROOT"/}"
  case "$rel" in
    "$INV_REL"/*) continue ;;  # already covered by the directory symlink
  esac
  dest="$REPO_ROOT/$rel"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    skipped=$((skipped + 1))
    continue
  fi
  mkdir -p "$(dirname "$dest")"
  ln -s "$src" "$dest"
  linked=$((linked + 1))
done < <(find "$ARTIFACT_ROOT" -type f -print0)

log "linked $linked artifact(s), left $skipped existing path(s) untouched"
