# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Gatehouse triage receives the review job's result (`review_result`), so a PR whose review died before posting anything is held instead of passing.
- Promote signs the image with the fleet cosign key (`sign: true`), because
  bootc hosts are moving to trust only signed `quay.io/crunchtools` images
  (crunchtools/rhel10-bootc-server#47). Needs the repo's `cosign-signing`
  environment to hold `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD`.
- The container release runs constitution v1.51.0's `container-release.yml`
  (was v1.46.0) and grants it `issues: write`, so a failed weekly rebuild opens
  an issue instead of only emailing whoever last touched the cron line. A `v*`
  promote now also refuses an image whose `version` label names a different
  release of this repo; each release PR moves this image's label to the new
  version, so a release cut that way passes.

## [1.2.3] - 2026-11-17

### Security

- Bump dnspython 2.9.1 to 2.9.2 in `uv.lock` for CVE-2026-128089
  (GHSA-vvf4-9x63-8xvv, CVSS 7.5): unbounded WKS service numbers in
  `from_text()` could exhaust memory and CPU. It arrives transitively
  through email-validator.

## [1.2.2] - 2026-11-10

### Fixed

- Dependency install from `uv.lock` was missing `--no-deps` on the `-r requirements.txt` step, letting pip re-resolve past the locked set. Added `--no-deps` so the image installs exactly what CI tested.

## [1.2.1] - 2026-10-31

### Security

- Upgraded locked dependencies within their declared ranges to clear the
  advisories the fleet dependency audit found (authlib, dnspython, fastmcp, joserfc, opentelemetry-api, pyjwt).

## [1.2.0] - 2026-10-20

### Changed

- Container base images pinned to `quay.io/hummingbird/python:3.14*` instead of
  `latest`, which moved to Python 3.15.0 on 2026-10-20 (crunchtools/constitution#66).

## [1.1.1] - 2026-10-11

### Fixed
- Container image now installs dependencies from `uv.lock` instead of resolving them at build time

## [1.1.0] - 2026-10-10

### Added
- All six tools publish `readOnlyHint: true`; each only reads log files. A
  gateway uses the annotation to decide whether an invalid optional argument
  may be dropped or must refuse the call (crunchtools/mcp-trentina#335).
- A test pins every registered tool into a `READ_ONLY` or a `WRITES` set, so a
  new tool fails the suite until it is classified (constitution v1.22.0).

### Fixed
- `server.json` and the container label still said 0.1.0.

### Changed
- Inherits constitution v1.22.0.

## [1.0.1] - 2026-10-02

### Fixed

- The package, `__version__` and the MCP server reported 0.1.0 while the
  v1.0.0 release and image said 1.0.0; all three now carry the release version.

### Changed
- Constitution is now a v1.18.0 manifest: only repo-specific facts remain;
  fleet and profile rules apply by reference.
- Constitution validation is pinned via `.github/workflows/constitution.yml`.
- Dependabot auto-merges GitHub Actions minor and patch updates.

## [1.0.0] - 2026-09-20

First tagged release. This image has been running in production since before
it had version control. No changes are recorded prior to this point --
RT #1484 added this file on 2026-09-19, before this repo's first tag.
