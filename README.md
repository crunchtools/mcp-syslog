# mcp-syslog-crunchtools

MCP server for the logs collected by [`crunchtools/syslog`](https://github.com/crunchtools/syslog).

Built for RT #1460, to close a specific gap: Hermes gets paged by Nagios and can
restart a service, but it cannot read the service's logs — so every remediation
is a blind restart. This turns that into an informed one.

## Capabilities

| Tool | What it answers |
|---|---|
| `syslog_sources_tool` | What can I query? |
| `syslog_search_tool` | Show me ERRs from this service in the last 15 minutes |
| `syslog_grep_tool` | Where does this string appear across the whole fleet? |
| `syslog_tail_tool` | What are this service's most recent lines? |
| `syslog_context_tool` | What was *everything* saying around 03:14? |
| `syslog_stats_tool` | Which service is loudest, and which is actually unhealthy? |

## The triage loop

```
nagios_current_problems_tool          → what is broken
syslog_search_tool(source=…,          → why it broke
                   severity="ERR",
                   since="15m")
syslog_context_tool(timestamp=…)      → what else was happening at that moment
nagios_schedule_check_tool            → confirm the fix
```

`syslog_context_tool` without a `source` is the one that earns its keep. It spans
every source at once, which is how "the app died" gets connected to "the database
container OOMed four seconds earlier".

## Design notes

**Every result is bounded, and says when it is.** Logs are unbounded and this
output lands in a model's context window. Each tool caps its results, caps how
many lines it will scan, and annotates the answer when either limit is hit:

```
[!] Stopped after the 2,000,000-line scan limit, so this result is INCOMPLETE
    and an empty or short result does not mean nothing happened.
```

That annotation is load-bearing. A caller that cannot distinguish "no errors
occurred" from "I stopped looking" will draw the wrong conclusion from an empty
result — and this server exists to inform remediation decisions.

**Time filtering is cheap.** The collector puts the date in the filename, so a
ten-minute query opens one file rather than reading ninety days of history.

**Source names are untrusted.** They come from a model and are used to build a
filesystem path. Each is resolved and then confirmed to still be inside the log
root, which catches traversal, absolute paths, and symlinks pointing out of the
tree — see `tests/test_security.py`.

**Severity is "at least this severe".** `severity="ERR"` returns ERR, CRIT, ALERT
and EMERG. An unrecognised severity is kept rather than dropped, on the grounds
that hiding a line you do not understand is worse than showing it — but it is
*not* counted as an error in `syslog_stats_tool`, or a healthy service would
report a 57% error rate.

**Severity is not badness.** Podman records anything a container writes to stderr
at priority `err`, and plenty of services log routine INFO there. On lotor,
`mcp-trentina` sits around 65% "ERR" while being entirely healthy:

```
PRIORITY=3 | 2026-08-23 15:55:24 INFO  httpx: HTTP Request: GET https://... "200 OK"
```

The collector is reporting the journal faithfully; the journal is reporting the
file descriptor. Read the message, and prefer a *change* in error rate to its
absolute value. This caveat is in the server's MCP instructions too, so an agent
querying it is told the same thing.

**Two line formats are parsed.** The collector emitted five fields before
2026-08-23 and six after, and the old lines stay in retention for 90 days. Which
layout a line uses is decided by where a real severity sits, not by counting
fields.

## Log format

The collector writes six space-delimited fields:

```
2026-08-23T15:41:52+00:00 crunchtools.com crunchtools.com httpd ERR AH00169: caught SIGTERM
└─ timestamp ───────────┘ └─ host ──────┘ └─ source ────┘ └prog┘ └sev┘ └─ message ────────┘
```

`source` is the log stream — normally a container name. `program` is the process
inside it, which matters for systemd containers where `httpd`, `php-fpm` and
`mariadb` all file under one service name.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SYSLOG_LOG_ROOT` | `/logs` | Collector log root, mounted read-only |
| `SYSLOG_MAX_RESULTS` | `200` | Cap on entries returned per call |
| `SYSLOG_SCAN_LIMIT` | `2000000` | Cap on lines examined per call |

No credentials — the server reads files off a read-only bind mount.

## Running

```bash
podman run -d --name mcp-syslog \
  --network crunchtools \
  -p 127.0.0.1:8027:8027 \
  -v /srv/syslog.crunchtools.com/data/logs:/logs:ro \
  quay.io/crunchtools/mcp-syslog:latest \
  --transport streamable-http --host 0.0.0.0 --port 8027
```

Mount `:ro`. This server never needs to write, and a read-only mount means a bug
here cannot destroy the forensic record it exists to protect.

## Development

```bash
uv sync
uv run ruff check src tests
uv run mypy src
uv run pytest -v
```
