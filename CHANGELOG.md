# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Repository scaffold, MIT license, CI (ruff + pytest).
- Shared library `pocketknife`: 2D hull, minimum rectangle, polylabel, region
  grouping, minimum oriented box, layer-copy planning.
- Approved commands (in `commands/`, documented in `docs/commands/`): `pkLayerColorFromMaterial`, `pkCopyToLayerCopy`,
  `pkInnerPoint`, `pkMinBoundingRect`, `pkMinBoundingBox`, `pkOrientToMinRect`.

### Fixed
- `pkCopyToLayerCopy`: selected layers below another selected layer no longer split the copied tree.

### Changed
- `pkMinBoundingBox`: `Group=Yes` by default, slow-computation warning, progress bar and Esc.
