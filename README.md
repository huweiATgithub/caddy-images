# Custom Caddy images

A central repository for small, pinned extensions of the official Caddy container.
The first image is `ghcr.io/huweiatgithub/caddy-s3`, targeting **linux/amd64**.

## caddy-s3

| Input | Pin |
| --- | --- |
| Caddy | `2.11.7` |
| Plugin | `github.com/techknowlogick/certmagic-s3` |
| Plugin commit | `6c26852bb192f1f0ccfe36b0508b3b9f12116632` |
| Build revision | `1` |
| Initial tags | `2.11.7`, `2.11.7-r1` |

The official builder and Alpine runtime are digest-pinned in
[`image.json`](images/caddy-s3/image.json). The plugin's pinned `go.mod` requires
Go 1.26.0 and Caddy 2.11.6. `xcaddy build v2.11.7` explicitly selects the Caddy
version; CI checks the resulting binary rather than trusting a tag.

The final stage inherits the official image and replaces only `/usr/bin/caddy`,
restoring its privileged-port file capability. It retains the official command,
entrypoint (including its absence), environment, ports, working directory,
volume declarations (including their absence), default Caddyfile and web assets.
There is no custom startup wrapper or production Caddyfile baked into the image.

## Usage

Published package: `ghcr.io/huweiatgithub/caddy-s3`.

```sh
docker pull --platform linux/amd64 ghcr.io/huweiatgithub/caddy-s3:2.11.7
docker run --rm ghcr.io/huweiatgithub/caddy-s3:2.11.7 caddy version
docker run --rm ghcr.io/huweiatgithub/caddy-s3:2.11.7 caddy list-modules
```

Mount your Caddyfile at `/etc/caddy/Caddyfile`, using normal official Caddy
container options and persistent `/data` and `/config` mounts as needed. Configure
S3 through the global `storage s3` block; see [`tests/Caddyfile`](tests/Caddyfile)
and the [plugin's pinned documentation](https://github.com/techknowlogick/certmagic-s3/tree/6c26852bb192f1f0ccfe36b0508b3b9f12116632).
Supply production credentials securely at runtime; never commit them or bake
them into the image. CI adaptation is deliberately credential-free and does not
perform S3 API operations or request certificates.

## Release any upstream tag

1. Open [Actions → Build, test and publish caddy-s3](https://github.com/huweiATgithub/caddy-images/actions/workflows/caddy-s3.yml).
2. Choose **Run workflow**, select branch **main**, and enter a stable upstream
   tag such as `v2.11.7` in **upstream_tag**. Leave **build_revision** blank for
   the first release of a new version, or enter `2`, `3`, etc. for a rebuild.
3. Wait for both jobs and the anonymous-pull gate to finish successfully.
   Revision 1 publishes `VERSION` and `VERSION-r1`; later revisions publish
   only `VERSION-rN`. The summary contains the public image digest.

No manifest edit, personal access token, or plugin selection is needed. The
workflow verifies an official non-draft, non-prerelease Caddy release, resolves
its official Alpine builder/runtime **linux/amd64 manifest digests**, and keeps
the repository's pinned S3 plugin. These inputs are resolved once, passed from
the test job to the publishing job, and saved as `resolved-image.json` in the
`local-acceptance` artifact. Both builds use those exact base digests.
Only stable `vX.Y.Z` tags are supported; branches, prereleases, shell syntax and
arbitrary image references are rejected. If upstream has not published both
Docker images yet, the run fails safely; retry once the images are available.

Leaving **upstream_tag** blank uses `image.json`. Requesting its version also
uses its recorded base pins. Other versions resolve fresh official image pins
at the start of the test job. A **failed publishing job** can be rerun with the
same successful test job's frozen inputs. Rerunning all jobs or starting a new
run re-resolves non-default versions: if upstream rebuilt a base or repository
build/verification inputs changed, the immutable-tag guard will refuse to
replace an existing release. Use a new **build_revision** for changed inputs;
the original bare tag remains untouched. To reproduce an older build locally,
use its saved resolved manifest and repository commit, or pull its image digest.

Manual releases do not rewrite the repository's default manifest or Dockerfile.
The checked-in default is 2.11.7. Promoting another version to that default is an
optional reviewed source change; it is not required to release it.

## CI and first publication

The GitHub Actions workflow runs automatically for relevant changes on `main`
and pull requests, and supports **Run workflow** (`workflow_dispatch`). Only
`main` can publish. Pull-request jobs have read-only permissions and do not log
in to GHCR. Publishing uses the repository's `GITHUB_TOKEN` with `packages:write`;
no personal access token or new long-lived credential is needed.

1. Push this repository to the selected GitHub owner with default branch `main`.
   GitHub Actions and package publishing must be permitted for that owner.
2. The workflow builds locally, tests, pushes a unique candidate, checks immutable release tags, pulls the selected image back
   from GHCR by digest, tests again, and promotes the tested digest to release tags.
3. **A newly created GHCR package is private by default, even for a public repo.**
   Open your GitHub profile/organization's Packages → `caddy-s3` → Package settings
   → Change visibility → Public. Check that this repository has Actions access.
   GitHub may require an owner/admin to do this.
4. If the first workflow stops at the anonymous-pull gate, change the visibility
   and rerun the failed job or dispatch the workflow on `main`. Matching existing
   release images are reused by digest and never silently replaced. A rerun may
   push another candidate while retaining the existing release digest.
5. Completion means the anonymous-pull gate is green, not merely that a push
   succeeded. The workflow summary records the verified digest. Acceptance logs,
   module list, adapted JSON and image inspection are uploaded as run artifacts.

Acceptance covers the actual published image: anonymous tag and digest pulls,
exact `caddy version`, `caddy.storage.s3` module, valid S3 Caddyfile adaptation,
`linux/amd64`, inherited runtime metadata and default HTTP startup.

## Versioning and updates

- Treat published release tags as immutable. Initial `2.11.7` and `2.11.7-r1`
  point to the same digest. The bare `2.11.7` tag permanently denotes revision 1.
- For plugin, builder, runtime, Dockerfile, test or workflow changes at the same
  Caddy version, increment `build_revision`: for example `2.11.7-r2`. This avoids
  silently changing the image behind `2.11.7`.
- For a new Caddy version, use the manual workflow above. To also update local
  defaults, update `caddy_version` and the builder/runtime pins in `image.json`,
  reset `build_revision` to `1`, and align Dockerfile defaults. Plugin upgrades
  remain explicit reviewed source changes.
- An input fingerprint covers the effective resolved manifest, Dockerfile, scripts, tests and this
  workflow. If an existing release tag has a different fingerprint, publication
  fails and tells you to bump the revision. Documentation-only changes do not
  republish or require a revision change. Serialized publishing prevents races
  between this repository's workflows; other writers must also respect this
  repository's immutable-tag policy.
- Candidate tags include the GitHub run ID/attempt. They are debugging artifacts,
  not supported release aliases. The repository does not publish a mutable
  `latest` tag. For deployment-level reproducibility, use `image@sha256:...`.
- New upstream versions are adopted by explicit manual workflow runs or reviewed
  manifest changes. No scheduled unattended upgrades are enabled.

## Local checks

With Docker, Buildx and Python 3 installed:

```sh
python3 scripts/metadata.py
docker buildx build --platform linux/amd64 --load \
  -f images/caddy-s3/Dockerfile -t caddy-s3:local .
PULL_IMAGE=false bash scripts/acceptance.sh caddy-s3:local 2.11.7 \
  "$(python3 -c 'import json; print(json.load(open("images/caddy-s3/image.json"))["runtime_image"])')"
```

To repeat remote acceptance, pass a GHCR image digest as the first argument and
omit `PULL_IMAGE=false`. For a true anonymous check, use an empty temporary
`DOCKER_CONFIG` directory. The test must pull from the registry; testing only a
locally built image does not establish publication or public visibility.

## Adding another image

Add an `images/<name>/` Dockerfile and pin manifest, its own tests and a workflow
with a separate concurrency group and GHCR package name. Keep package-specific
configuration outside the runtime image and preserve the official base's
container interface.

## Upstream sources

- [Official Caddy image source](https://github.com/caddyserver/caddy-docker)
- [Caddy 2.11.7](https://github.com/caddyserver/caddy/releases/tag/v2.11.7)
- [Pinned plugin source](https://github.com/techknowlogick/certmagic-s3/tree/6c26852bb192f1f0ccfe36b0508b3b9f12116632)
- [GitHub package visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)

Upstream Caddy and plugin code retain their respective licenses. No S3 service
credentials or end-to-end S3 storage validation are included in this repository.
