# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
