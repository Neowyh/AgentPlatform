#!/usr/bin/env bash
# Updates only the pure upstream main reference; never force-pushes or copies tags.
set -euo pipefail
upstream_url=${UPSTREAM_MIRROR_URL:-https://github.com/bytedance/deer-flow.git}
origin_remote=${UPSTREAM_MIRROR_ORIGIN:-origin}
# ls-remote exit 2 means absent. Other failures must not authorize creation.
set +e
git ls-remote --exit-code "$origin_remote" refs/heads/main >/dev/null
origin_status=$?
set -e
if [[ $origin_status -ne 0 && $origin_status -ne 2 ]]; then
  echo 'Cannot inspect origin/main; mirror update stopped.' >&2
  exit "$origin_status"
fi
if [[ $origin_status -eq 2 && ${UPSTREAM_MIRROR_BOOTSTRAP:-0} != 1 ]]; then
  echo 'Missing origin/main requires explicit bootstrap with UPSTREAM_MIRROR_BOOTSTRAP=1.' >&2
  exit 1
fi
if [[ $origin_status -eq 0 ]]; then
  git fetch --no-tags "$origin_remote" main
fi
git fetch --no-tags "$upstream_url" main
mirror_head=$(git rev-parse FETCH_HEAD)
origin_head=absent
if [[ $origin_status -eq 0 ]]; then
  origin_head=$(git rev-parse refs/remotes/"$origin_remote"/main)
fi
if [[ $origin_status -eq 0 ]] && ! git merge-base --is-ancestor "$origin_head" "$mirror_head"; then
  echo "Mirror update blocked: origin/main cannot fast-forward to upstream main ($mirror_head)." >&2
  exit 1
fi
if [[ ${UPSTREAM_MIRROR_APPLY:-0} != 1 ]]; then
  echo "Mirror candidate verified: $origin_head -> $mirror_head. Set UPSTREAM_MIRROR_APPLY=1 to update main."
  exit 0
fi
git push "$origin_remote" "$mirror_head:refs/heads/main"
