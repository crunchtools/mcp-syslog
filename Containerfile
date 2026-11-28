# Two stages, because the runtime base has no shell.
#
# quay.io/hummingbird/python:3.14 was rebuilt distroless on 2026-08-19 and now
# contains 33 binaries and no /bin/sh, so a `RUN` in the final stage fails with
# "executable file `/bin/sh` not found". Anything that needs to execute has to
# happen in the builder; the final stage may only COPY.

FROM quay.io/hummingbird/python:3.14-builder AS pip-builder
USER 0

# uv from PyPI, hash-locked in container/build-requirements.txt. It was
# COPY --from=ghcr.io/astral-sh/uv:latest: an untrusted registry's floating tag,
# which sdlc's image job refuses once it verifies --from images like FROMs (#96).
WORKDIR /app
COPY container/build-requirements.txt ./
RUN pip install --no-cache-dir --no-deps --require-hashes --only-binary=:all: -r build-requirements.txt
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# --target rather than a plain install: the builder runs as a non-root user with
# HOME=/tmp, so pip would otherwise scatter a *user* install into /tmp/.local.
# It also avoids hardcoding a python3.NN path that changes under us on rebuild.
#
# Dependencies come from uv.lock (hash-pinned), not a fresh resolve, so the image
# runs the same versions the tests ran against. --frozen fails if the lock is stale.
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && pip install --no-cache-dir --no-deps --target=/site -r /tmp/requirements.txt \
    && pip install --no-cache-dir --no-deps --target=/site .

# Verified here rather than in the final stage, which cannot execute anything.
RUN PYTHONPATH=/site python -c "from mcp_syslog_crunchtools import main; print('Installation verified')"

FROM quay.io/hummingbird/python:3.14

LABEL name="mcp-syslog-crunchtools" \
      version="1.3.0" \
      summary="Secure MCP server for centrally collected infrastructure logs" \
      description="Search, tail, grep and correlate logs collected by crunchtools/syslog" \
      maintainer="crunchtools.com" \
      url="https://github.com/crunchtools/mcp-syslog" \
      io.k8s.display-name="MCP Syslog CrunchTools" \
      io.openshift.tags="mcp,syslog,logging,observability" \
      org.opencontainers.image.source="https://github.com/crunchtools/mcp-syslog" \
      org.opencontainers.image.description="Secure MCP server for centrally collected infrastructure logs" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"

WORKDIR /app

# Only the installed packages cross into the runtime image — no pip, no shell,
# no package manager.
COPY --from=pip-builder /site /site
ENV PYTHONPATH=/site

# Default log root. Mount the collector's log directory here read-only — this
# server never writes, and a read-only mount means a bug here cannot destroy the
# forensic record it exists to protect.
ENV SYSLOG_LOG_ROOT=/logs

EXPOSE 8027
ENTRYPOINT ["python", "-m", "mcp_syslog_crunchtools"]
