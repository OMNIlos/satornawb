#!/usr/bin/env bash
# Publish the frontend to the Beget server (https://comcookie.store).
#
#   deploy/frontend-release.sh                 build this commit and make it live
#   deploy/frontend-release.sh --no-switch     build and upload only
#   deploy/frontend-release.sh --list          releases on the server, * marks the live one
#   deploy/frontend-release.sh --switch NAME   make an uploaded release live (also the rollback)
#
# Every release is its own folder in /var/www/satorna-frontend/releases; nginx
# serves the "current" symlink, so switching is instant. The backend is not touched.
#
# Needs Node 22.12+, rsync and SSH access to DEPLOY_HOST (default: the
# "satorna-api" alias from ~/.ssh/config).
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-satorna-api}"
REMOTE_BASE=/var/www/satorna-frontend
KEEP_RELEASES=5
# Rewritten by every build (it embeds the build time), so it never blocks a release.
GENERATED_SNAPSHOT=frontend/src/features/vella-parity/vellaProductionSnapshot.generated.ts

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

remote() { ssh -o BatchMode=yes "$DEPLOY_HOST" bash -s -- "$@"; }

list_releases() {
  remote "$REMOTE_BASE" <<'REMOTE'
set -euo pipefail
base=$1
live=$(readlink "$base/current" 2>/dev/null | sed 's#^releases/##' || true)
ls -1 "$base/releases" | sort | while read -r name; do
  if [ "$name" = "$live" ]; then echo "* $name"; else echo "  $name"; fi
done
REMOTE
}

switch_release() {
  remote "$REMOTE_BASE" "$1" "$KEEP_RELEASES" <<'REMOTE'
set -euo pipefail
base=$1 name=$2 keep=$3
test -f "$base/releases/$name/index.html" || { echo "no such release: $name" >&2; exit 1; }
ln -sfn "releases/$name" "$base/current.tmp"
mv -T "$base/current.tmp" "$base/current"
echo "live: $name"
# Keep the newest $keep releases and whatever is live; names start with a UTC timestamp.
cd "$base/releases"
ls -1 | grep -E '^[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9._-]+$' | sort | head -n "-$keep" | while read -r old; do
  [ "$old" = "$name" ] || rm -rf -- "$old"
done
REMOTE
}

mode="${1:-}"
case "$mode" in
  --list) list_releases; exit 0 ;;
  --switch)
    [ -n "${2:-}" ] || { echo "usage: $0 --switch NAME" >&2; exit 2; }
    switch_release "$2"; exit 0 ;;
  "" | --no-switch) ;;
  *) echo "unknown option: $mode" >&2; exit 2 ;;
esac

cd "$repo_root"
if [ -n "$(git status --porcelain -- . ":(exclude)$GENERATED_SNAPSHOT")" ] && [ "${ALLOW_DIRTY:-0}" != 1 ]; then
  echo "Uncommitted changes: commit first so the release matches a commit (or set ALLOW_DIRTY=1)." >&2
  exit 1
fi
name="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)"

# Build-time flags; Vite inlines them into the bundle.
set -a
. "$repo_root/deploy/frontend-production.env"
set +a

cd "$repo_root/frontend"
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --no-audit --no-fund
npm run build
node "$repo_root/deploy/package-extensions.mjs" --origin=https://comcookie.store --to-dist
if [ ! -s dist/index.html ] || ! ls dist/assets/*.js >/dev/null 2>&1; then
  echo "The build produced no site in frontend/dist." >&2
  exit 1
fi
find dist -name .DS_Store -delete

rsync -az --delete -e "ssh -o BatchMode=yes" dist/ "$DEPLOY_HOST:$REMOTE_BASE/releases/$name/"
remote "$REMOTE_BASE" "$name" <<'REMOTE'
set -euo pipefail
rel=$1/releases/$2
if [ "$(id -u)" = 0 ]; then chown -R root:root "$rel"; fi
find "$rel" -type d -exec chmod 755 {} +
find "$rel" -type f -exec chmod 644 {} +
REMOTE
echo "uploaded: $name"

if [ "$mode" = "--no-switch" ]; then
  echo "Not live yet. To switch: $0 --switch $name"
else
  switch_release "$name"
fi
