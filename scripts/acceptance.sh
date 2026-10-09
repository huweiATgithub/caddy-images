#!/usr/bin/env bash
set -euo pipefail
image=${1:?Usage: acceptance.sh IMAGE VERSION OFFICIAL_RUNTIME [OUTPUT_DIR]}
version=${2:?}
base=${3:?}
out=${4:-acceptance-results}
mkdir -p "$out"
if [[ ${PULL_IMAGE:-true} == true ]]; then
  docker pull --platform linux/amd64 "$image"
fi
docker pull --platform linux/amd64 "$base"
docker run --rm --platform linux/amd64 "$image" caddy version | tee "$out/version.txt"
[[ $(head -n1 "$out/version.txt" | cut -d' ' -f1) == "v$version" ]]
docker run --rm --platform linux/amd64 "$image" caddy list-modules | tee "$out/modules.txt"
grep -Fxq 'caddy.storage.s3' "$out/modules.txt"
docker run --rm --platform linux/amd64 \
  -v "$PWD/tests/Caddyfile:/tmp/Caddyfile:ro" "$image" \
  caddy adapt --config /tmp/Caddyfile --adapter caddyfile --pretty > "$out/adapted.json"
python3 - "$out/adapted.json" <<'PY'
import json,sys
storage=json.load(open(sys.argv[1]))["storage"]
assert storage["module"] == "s3", storage
assert storage["bucket"] == "caddy-ci-adapt-only", storage
assert storage["region"] == "us-east-1", storage
assert storage["prefix"] == "caddy-ci", storage
PY
docker image inspect "$image" > "$out/image-inspect.json"
docker image inspect "$base" > "$out/base-inspect.json"
python3 - "$out" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); custom=json.load(open(p/'image-inspect.json'))[0]; base=json.load(open(p/'base-inspect.json'))[0]
assert (custom['Os'],custom['Architecture']) == ('linux','amd64')
for key in ['Entrypoint','Cmd','WorkingDir','User','ExposedPorts','Volumes','Env','Healthcheck','StopSignal']:
    assert custom['Config'].get(key) == base['Config'].get(key), key
PY
docker run --rm "$image" sh -ec 'getcap /usr/bin/caddy | grep -F "cap_net_bind_service=ep"'
# Check the inherited default command and shipped content actually serve HTTP.
container=$(docker run -d --platform linux/amd64 -p 127.0.0.1::80 "$image")
trap 'docker logs "$container" > "$out/server.log" 2>&1; docker rm -f "$container" >/dev/null' EXIT
port=$(docker port "$container" 80/tcp | head -1 | awk -F: '{print $NF}')
for attempt in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$port/" > "$out/default-page.html"; then
    echo "PASS: $image ($version, linux/amd64, S3 adapter, official runtime)"
    exit 0
  fi
  sleep 1
done
echo 'Default Caddy HTTP smoke test failed' >&2
exit 1
