#!/usr/bin/env bash
#
# Bring this environment up. ONE COMMAND ON EVERY BOX:
#
#   cd kolabo/deploy && bash up.sh
#
# Arguments are passed through, so `bash up.sh caddy` or
# `bash up.sh --force-recreate` work as you would expect.
#
# WHY A WRAPPER RATHER THAN THE COMPOSE COMMAND IN THE README. Three reasons,
# and all of them have already cost real time on this project.
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
#
# AND NOW TWO BOXES DO OPPOSITE THINGS WITH THE SAME COMMAND. KOL-56 moved the
# image build into CI: docker-compose.prod.yml names images from ghcr.io and
# deploy/.env pins the tag, so production pulls a known artifact and rolls back
# by naming an earlier tag. The dev box cannot use those images, because the web
# bundle is compiled against one api hostname, so it sets KOLABO_BUILD=1 and
# this script adds docker-compose.build.yml and builds. Deciding that here, from
# one setting in .env, is the only way `bash up.sh` keeps meaning "bring this box
# up correctly" on both of them.

set -euo pipefail

cd "$(dirname "$0")"

bash checks/preflight-env.sh

# Read one value out of .env WITHOUT sourcing the file, the same way
# checks/preflight-env.sh does and for the same reason: a value containing a
# backtick or a $( would otherwise run as this script's user, and that file
# holds every credential the stack has.
env_value() {
  sed -n "s/^[[:space:]]*$1=//p" .env | tail -n 1 \
    | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

files=(-f docker-compose.prod.yml)

build_locally=0
case "$(env_value KOLABO_BUILD)" in
  ""|0|false|no) ;;
  *) build_locally=1 ;;
esac

if (( build_locally )); then
  files+=(-f docker-compose.build.yml)
  echo "KOLABO_BUILD is set, so this box builds its own images rather than"
  echo "pulling them. Including docker-compose.build.yml."
  echo
fi

# AFTER the build file, so a per box addition wins over both.
if [[ -f docker-compose.local.yml ]]; then
  files+=(-f docker-compose.local.yml)
  echo "Including docker-compose.local.yml (this box has per box additions)."
  echo
fi

if (( build_locally )); then
  set -x
  exec docker compose "${files[@]}" up -d --build "$@"
fi

# PULL BEFORE UP, ONLY TO GET A BETTER ERROR. `up` would pull a missing image
# by itself; what it would not do is explain a refusal. The repository is
# private, so its packages are private, and a box whose `docker login ghcr.io`
# has never been done or has expired gets a denial from the daemon that names
# neither the registry credential nor the file holding the tag. When the tag is
# already on the box this costs one request per image.
set -x
if ! docker compose "${files[@]}" pull backend sweeps web; then
  set +x
  echo
  echo "Could not pull the images for this tag. Two things it is likely to be:"
  echo
  echo "  NOT LOGGED IN TO ghcr.io. The images are private because the"
  echo "  repository is. GitHub's documentation says the container registry"
  echo "  accepts only a classic personal access token, so a fine grained one"
  echo "  will not work. Create one with the read:packages scope and run:"
  echo
  echo "    docker login ghcr.io -u mocktar2021"
  echo
  echo "  It asks for the token as the password. Do not put it in deploy/.env;"
  echo "  docker stores it in ~/.docker/config.json."
  echo
  echo "  THE TAG DOES NOT EXIST. KOLABO_TAG in deploy/.env has to name a tag"
  echo "  that CI published. The run summary for each merge to main prints the"
  echo "  line to paste, and the Packages page on GitHub lists every tag that"
  echo "  exists. A sha that only ever lived on a branch was never built."
  echo
  exit 1
fi
exec docker compose "${files[@]}" up -d "$@"
