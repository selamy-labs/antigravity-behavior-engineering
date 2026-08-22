FROM --platform=linux/amd64 node:22.23.1-bookworm-slim@sha256:8607a9064d4a571140998ae9e52a3b3fcf9cff361d04642d5971e6cd76d39e27

LABEL org.opencontainers.image.title="Antigravity Behavior Engineering disposable worker"
LABEL org.opencontainers.image.description="Credential-free OCI worker boundary for public Antigravity behavior evaluation"
LABEL org.opencontainers.image.licenses="Apache-2.0"

RUN groupadd --system --gid 10001 abe \
  && useradd --system --uid 10001 --gid 10001 --home-dir /home/abe --create-home --shell /usr/sbin/nologin abe \
  && mkdir -p /opt/abe /opt/antigravity/bin /workspace/input /workspace/repo /workspace/profile /workspace/output /workspace/plugin-condition \
  && chown -R abe:abe /workspace /home/abe \
  && chmod 0555 /opt/abe /opt/antigravity /opt/antigravity/bin \
  && chmod 0755 /workspace /workspace/repo /workspace/profile /workspace/output

COPY --chown=root:root entrypoint.sh /opt/abe/entrypoint
COPY --chown=root:root verify-image.mjs /opt/abe/verify-image.mjs

RUN chmod 0555 /opt/abe/entrypoint /opt/abe/verify-image.mjs

ENV HOME=/workspace/profile
ENV XDG_CONFIG_HOME=/workspace/profile/.config
ENV XDG_CACHE_HOME=/workspace/profile/.cache
ENV npm_config_cache=/workspace/profile/.npm
ENV npm_config_update_notifier=false

USER 10001:10001
WORKDIR /workspace/repo
STOPSIGNAL SIGTERM
ENTRYPOINT ["/opt/abe/entrypoint"]
