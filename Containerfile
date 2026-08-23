FROM quay.io/hummingbird/python:latest-builder

LABEL name="mcp-syslog-crunchtools" \
      version="0.1.0" \
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
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
RUN python -c "from mcp_syslog_crunchtools import main; print('Installation verified')"

# Default log root. Mount the collector's log directory here read-only — this
# server never writes, and a read-only mount means a bug here cannot destroy the
# forensic record it exists to protect.
ENV SYSLOG_LOG_ROOT=/logs

EXPOSE 8027
ENTRYPOINT ["python", "-m", "mcp_syslog_crunchtools"]
