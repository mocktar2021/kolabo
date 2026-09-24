#!/usr/bin/env bash
#
# Bring this environment up. ONE COMMAND ON EVERY BOX:
#
#   cd kolabo/deploy && bash up.sh
#
# Arguments are passed through, so `bash up.sh caddy` or
# `bash up.sh --force-recreate` work as you would expect.
#
# WHY A WRAPPER RATHER THAN THE COMPOSE COMMAND IN THE README. Two reasons, and
# both of them have already cost real time on this project.
#
# THE PREFLIGHT ONLY HELPS IF IT RUNS. deploy/README.md says to run
# checks/preflight-env.sh before every `up`, and a documented step that sits
# beside the command rather than inside it is a step that gets skipped on the
# deploy where it mattered. It now runs first, every time, and a refusal stops
# the deploy instead of being scrolled past.
#
# SOME BOXES NEED A SECOND -f AND FORGETTING IT IS SILENT AND EXPENSIVE. The dev
# box's caddy is the shared TLS edge for three products, and reaching the other
# two means joining a network that only exists on that box. That cannot go in
# docker-compose.prod.yml, because an `external: true` network is a hard error
# anywhere it does not exist, which would be every other environment. So it goes
# in docker-compose.local.yml, gitignored, and this script adds it when it is
# there. Run the bare compose command on that box instead and caddy comes back
# up without the network, at which point six hostnames belonging to two other
# products answer 502 and nothing says why.
#
# A box with no docker-compose.local.yml behaves exactly as before.

set -euo pipefail

cd "$(dirname "$0")"

bash checks/preflight-env.sh

files=(-f docker-compose.prod.yml)
if [[ -f docker-compose.local.yml ]]; then
  files+=(-f docker-compose.local.yml)
  echo "Including docker-compose.local.yml (this box has per box additions)."
  echo
fi

set -x
exec docker compose "${files[@]}" up -d --build "$@"
