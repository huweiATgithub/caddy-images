# syntax=docker/dockerfile:1
# Values are supplied from image.json by CI; these defaults also support local builds.
ARG BUILDER_IMAGE=caddy:2.11.6-builder-alpine@sha256:096ec6e825e219175bd5be64b5e7a4000977f701a2bcaab825621d9fb1e1154b
ARG RUNTIME_IMAGE=caddy:2.11.6-alpine@sha256:d44355d3c2149dc580ce2cac735955d1c08d3d00882c30489c241aa51a5c10d9
FROM ${BUILDER_IMAGE} AS builder
ARG BUILD_CADDY_VERSION=2.11.6
ARG PLUGIN_MODULE=github.com/techknowlogick/certmagic-s3
ARG PLUGIN_REVISION=6c26852bb192f1f0ccfe36b0508b3b9f12116632
ENV CGO_ENABLED=0
RUN xcaddy build "v${BUILD_CADDY_VERSION}" \
    --with "${PLUGIN_MODULE}@${PLUGIN_REVISION}" \
    --output /usr/bin/caddy \
    && test "$(/usr/bin/caddy version | cut -d ' ' -f 1)" = "v${BUILD_CADDY_VERSION}" \
    && /usr/bin/caddy list-modules | grep -Fx caddy.storage.s3

# Inherit the official runtime, including command, environment, ports, working
# directory, default config/assets and any volume declarations. Do not redefine them.
FROM ${RUNTIME_IMAGE}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
# COPY does not preserve file capabilities; restore the official binary capability.
RUN chmod +x /usr/bin/caddy && setcap cap_net_bind_service=+ep /usr/bin/caddy
