(changelog)=
# Changelog

<a id="v2.9.0"></a>
# [v2.9.0](https://github.com/sandialabs/firewheel/releases/tag/v2.9.0) - 2025-09-10

## 🚀 Features

- feat: Support for using Ansible playbooks for installing model components [@sdelliot](https://github.com/sdelliot) ([#113](https://github.com/sandialabs/firewheel/pull/113))

## 🐛 Bug Fixes

- fix: Address repository installation short circuit [@sdelliot](https://github.com/sdelliot) ([#161](https://github.com/sandialabs/firewheel/pull/161))
- fix: Expand docker variables and fix discovery path [@sdelliot](https://github.com/sdelliot) ([#157](https://github.com/sandialabs/firewheel/pull/157))

## ⚙️  Build/CI

- ci: Dynamically get config path [@gregjacobus](https://github.com/gregjacobus) ([#164](https://github.com/sandialabs/firewheel/pull/164))
- ci: Adding `$FIREWHEEL_ROOT_DIR` to the config path [@sdelliot](https://github.com/sdelliot) ([#163](https://github.com/sandialabs/firewheel/pull/163))
- ci: Updating the GitLab CI for ansible usage [@sdelliot](https://github.com/sdelliot) ([#162](https://github.com/sandialabs/firewheel/pull/162))
- ci: generate static webpage for performance testing [@sdelliot](https://github.com/sdelliot) ([#154](https://github.com/sandialabs/firewheel/pull/154))
- ci: Moving to a clear binary git repo base structure [@sdelliot](https://github.com/sdelliot) ([#156](https://github.com/sandialabs/firewheel/pull/156))

## 📄 Documentation

- feat: Support for using Ansible playbooks for installing model components [@sdelliot](https://github.com/sdelliot) ([#113](https://github.com/sandialabs/firewheel/pull/113))

**Full Changelog**: https://github.com/sandialabs/firewheel/compare/v2.8.1...v2.8.2


[Changes][v2.9.0]


<a id="v2.8.1"></a>
# [v2.8.1](https://github.com/sandialabs/firewheel/releases/tag/v2.8.1) - 2025-07-09

## 🚀 Features

- feat: Adding new docker build paramameters [@sdelliot](https://github.com/sdelliot) ([#134](https://github.com/sandialabs/firewheel/pull/134))
- feat(cli): Adding a new firewheel config edit command [@sdelliot](https://github.com/sdelliot) ([#128](https://github.com/sandialabs/firewheel/pull/128))
- feat: Docker firewheel ssh [@gregjacobus](https://github.com/gregjacobus) ([#112](https://github.com/sandialabs/firewheel/pull/112))
- feat: Create a initial docker container for FIREWHEEL [@sdelliot](https://github.com/sdelliot) ([#68](https://github.com/sandialabs/firewheel/pull/68))

## 🐛 Bug Fixes

- fix: Refactor the MCPI to deduplicate MCs by absolute path [@mitchnegus](https://github.com/mitchnegus) ([#141](https://github.com/sandialabs/firewheel/pull/141))
- fix: Fixing namespaces [@gregjacobus](https://github.com/gregjacobus) ([#125](https://github.com/sandialabs/firewheel/pull/125))
- fix: Ensuring users know when a duplicate repository is trying to be added [@sdelliot](https://github.com/sdelliot) ([#81](https://github.com/sandialabs/firewheel/pull/81))
- fix: Clearly delineate between editable/non-editable MC installs [@mitchnegus](https://github.com/mitchnegus) ([#114](https://github.com/sandialabs/firewheel/pull/114))
- fix: Not sleeping for infinity in docker container [@gregjacobus](https://github.com/gregjacobus) ([#117](https://github.com/sandialabs/firewheel/pull/117))
- ci: Fix pydocstyle version to prevent linting errors [@mitchnegus](https://github.com/mitchnegus) ([#104](https://github.com/sandialabs/firewheel/pull/104))
- ci: Fix the testing, linting, and documentation CI workflows [@mitchnegus](https://github.com/mitchnegus) ([#95](https://github.com/sandialabs/firewheel/pull/95))
- ci: adjusting the PR label checking to a working version [@sdelliot](https://github.com/sdelliot) ([#93](https://github.com/sandialabs/firewheel/pull/93))
- ci: fixing an issue where checking for labels fails [@sdelliot](https://github.com/sdelliot) ([#92](https://github.com/sandialabs/firewheel/pull/92))
- fix: Address adding duplicate repositories and conflicts with manual vs package installed repositories. [@sdelliot](https://github.com/sdelliot) ([#65](https://github.com/sandialabs/firewheel/pull/65))
- fix: Fixing the paths to various model components via the install script [@sdelliot](https://github.com/sdelliot) ([#85](https://github.com/sandialabs/firewheel/pull/85))
- fix: Fixing a bug where the model components are both cloned and pip installed leading to duplication. [@sdelliot](https://github.com/sdelliot) ([#80](https://github.com/sandialabs/firewheel/pull/80))
- fix: Making adjustments to the tab completion to work with `/bin/sh` [@sdelliot](https://github.com/sdelliot) ([#70](https://github.com/sandialabs/firewheel/pull/70))
- fix: fixing quoted expansion of FIREWHEEL\_NODES variable in install.sh [@gregjacobus](https://github.com/gregjacobus) ([#77](https://github.com/sandialabs/firewheel/pull/77))
- fix: Correct behavior of the SSH Manager for quoted strings [@mitchnegus](https://github.com/mitchnegus) ([#76](https://github.com/sandialabs/firewheel/pull/76))

## ⚠️ Changes

- chore: Remove duplicate pip installation instruction [@mitchnegus](https://github.com/mitchnegus) ([#130](https://github.com/sandialabs/firewheel/pull/130))
- chore: Tightening dependencies to address python 3.8 support [@sdelliot](https://github.com/sdelliot) ([#127](https://github.com/sandialabs/firewheel/pull/127))
- test: Use mock for simulating permissioned systems [@mitchnegus](https://github.com/mitchnegus) ([#102](https://github.com/sandialabs/firewheel/pull/102))
- fix: Address adding duplicate repositories and conflicts with manual vs package installed repositories. [@sdelliot](https://github.com/sdelliot) ([#65](https://github.com/sandialabs/firewheel/pull/65))
- deps: update pytest requirement from \<=8.3.4 to \<=8.3.5 @[dependabot[bot]](https://github.com/apps/dependabot) ([#73](https://github.com/sandialabs/firewheel/pull/73))

## ⚙️  Build/CI

- ci: Use additional files and reference tags for CI setup [@mitchnegus](https://github.com/mitchnegus) ([#120](https://github.com/sandialabs/firewheel/pull/120))
- ci: Removing 'git lfs install' from Gitlab CI [@gregjacobus](https://github.com/gregjacobus) ([#116](https://github.com/sandialabs/firewheel/pull/116))
- ci: Updating the discovery link to an official release. [@sdelliot](https://github.com/sdelliot) ([#109](https://github.com/sandialabs/firewheel/pull/109))
- ci: Update the GitLab CI file to work with new paths [@gregjacobus](https://github.com/gregjacobus) ([#108](https://github.com/sandialabs/firewheel/pull/108))
- ci: Fix pydocstyle version to prevent linting errors [@mitchnegus](https://github.com/mitchnegus) ([#104](https://github.com/sandialabs/firewheel/pull/104))
- ci: Fix the testing, linting, and documentation CI workflows [@mitchnegus](https://github.com/mitchnegus) ([#95](https://github.com/sandialabs/firewheel/pull/95))
- ci: Run PR label check only in pull request contexts [@mitchnegus](https://github.com/mitchnegus) ([#94](https://github.com/sandialabs/firewheel/pull/94))
- ci: adjusting the PR label checking to a working version [@sdelliot](https://github.com/sdelliot) ([#93](https://github.com/sandialabs/firewheel/pull/93))
- ci: fixing an issue where checking for labels fails [@sdelliot](https://github.com/sdelliot) ([#92](https://github.com/sandialabs/firewheel/pull/92))
- ci: Clean up GitLab CI and reduce duplicate code [@sdelliot](https://github.com/sdelliot) ([#86](https://github.com/sandialabs/firewheel/pull/86))
- ci: Updating CI to use specific tagged versions of github actions and minimizing/enforcing permissions for all actions. [@sdelliot](https://github.com/sdelliot) ([#69](https://github.com/sandialabs/firewheel/pull/69))
- ci: Enhance CI reusability [@mitchnegus](https://github.com/mitchnegus) ([#66](https://github.com/sandialabs/firewheel/pull/66))

## 🔐 Security

- ci: Updating CI to use specific tagged versions of github actions and minimizing/enforcing permissions for all actions. [@sdelliot](https://github.com/sdelliot) ([#69](https://github.com/sandialabs/firewheel/pull/69))

## 📄 Documentation

- feat(cli): Adding a new firewheel config edit command [@sdelliot](https://github.com/sdelliot) ([#128](https://github.com/sandialabs/firewheel/pull/128))
- fix: Clearly delineate between editable/non-editable MC installs [@mitchnegus](https://github.com/mitchnegus) ([#114](https://github.com/sandialabs/firewheel/pull/114))
- docs: Fixing docker README about ssh and scp being overwritten [@gregjacobus](https://github.com/gregjacobus) ([#118](https://github.com/sandialabs/firewheel/pull/118))
- doc: Adding a reference to Cyberwheel [@sdelliot](https://github.com/sdelliot) ([#84](https://github.com/sandialabs/firewheel/pull/84))
- feat: Create a initial docker container for FIREWHEEL [@sdelliot](https://github.com/sdelliot) ([#68](https://github.com/sandialabs/firewheel/pull/68))

## 🧩 Dependency Updates

<details>
<summary>15 changes</summary>

- deps: update coverage requirement from \<=7.8.0 to \<=7.8.2 @[dependabot[bot]](https://github.com/apps/dependabot) ([#132](https://github.com/sandialabs/firewheel/pull/132))
- deps: bump requests from 2.32.3 to 2.32.4 in the pip group @[dependabot[bot]](https://github.com/apps/dependabot) ([#139](https://github.com/sandialabs/firewheel/pull/139))
- deps: update rich requirement from \<13.10,>=13.6.0 to >=13.6.0,\<14.1 @[dependabot[bot]](https://github.com/apps/dependabot) ([#100](https://github.com/sandialabs/firewheel/pull/100))
- deps: update coverage requirement from \<=7.7.1 to \<=7.8.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#98](https://github.com/sandialabs/firewheel/pull/98))
- deps: update python-dotenv requirement from \<=1.0.1 to \<=1.1.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#99](https://github.com/sandialabs/firewheel/pull/99))
- deps: update grpcio-tools requirement from \<=1.67.0,>=1.63.0 to >=1.63.0,\<=1.68.1 @[dependabot[bot]](https://github.com/apps/dependabot) ([#75](https://github.com/sandialabs/firewheel/pull/75))
- deps: Update grpcio requirement from \<=1.67.0,>=1.49.0 to >=1.49.0,\<=1.70.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#52](https://github.com/sandialabs/firewheel/pull/52))
- deps: bump ruff from 0.11.0 to 0.11.2 @[dependabot[bot]](https://github.com/apps/dependabot) ([#89](https://github.com/sandialabs/firewheel/pull/89))
- deps: update coverage requirement from \<=7.6.10 to \<=7.7.1 @[dependabot[bot]](https://github.com/apps/dependabot) ([#88](https://github.com/sandialabs/firewheel/pull/88))
- deps: update jinja2 requirement from \<=3.1.5,>=3.1.2 to >=3.1.2,\<=3.1.6 @[dependabot[bot]](https://github.com/apps/dependabot) ([#87](https://github.com/sandialabs/firewheel/pull/87))
- deps: update pytest requirement from \<=8.3.4 to \<=8.3.5 @[dependabot[bot]](https://github.com/apps/dependabot) ([#73](https://github.com/sandialabs/firewheel/pull/73))
- deps: bump ruff from 0.9.6 to 0.11.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#82](https://github.com/sandialabs/firewheel/pull/82))
- deps: bump ruff from 0.9.2 to 0.9.6 @[dependabot[bot]](https://github.com/apps/dependabot) ([#64](https://github.com/sandialabs/firewheel/pull/64))
- deps: Update importlib-metadata requirement from \<=8.5.0,>=3.6 to >=3.6,\<=8.6.1 @[dependabot[bot]](https://github.com/apps/dependabot) ([#60](https://github.com/sandialabs/firewheel/pull/60))
- deps: Update clustershell requirement from \<=1.9.2 to \<=1.9.3 @[dependabot[bot]](https://github.com/apps/dependabot) ([#55](https://github.com/sandialabs/firewheel/pull/55))
</details>

**Full Changelog**: https://github.com/sandialabs/firewheel/compare/v2.8.0...v2.8.1


[Changes][v2.8.1]


<a id="v2.8.0"></a>
# [v2.8.0](https://github.com/sandialabs/firewheel/releases/tag/v2.8.0) - 2025-02-10


## 🚀 Features

- feat: resolve [#33](https://github.com/sandialabs/firewheel/issues/33) by enhancing the 'dry-run' flag [@sdelliot](https://github.com/sdelliot) ([#50](https://github.com/sandialabs/firewheel/pull/50))
- Feature: restructure SSH [@sdelliot](https://github.com/sdelliot) ([#49](https://github.com/sandialabs/firewheel/pull/49))

## ⚠️ Changes

- refactor: Replace the gRPC-backed RepositoryDB with a JSON-file backed one. [@sdelliot](https://github.com/sdelliot) ([#48](https://github.com/sandialabs/firewheel/pull/48))
- Ignore experiment history file [@mitchnegus](https://github.com/mitchnegus) ([#39](https://github.com/sandialabs/firewheel/pull/39))

## ⚙️  Build/CI

- Using built-in tools to automatically version FIREWHEEL [@sdelliot](https://github.com/sdelliot) ([#14](https://github.com/sandialabs/firewheel/pull/14))
- Cleaning up the gitlab CI based on newly open sourced model components [@sdelliot](https://github.com/sdelliot) ([#19](https://github.com/sandialabs/firewheel/pull/19))
- Allow workflow reuse across the FIREWHEEL ecosystem [@mitchnegus](https://github.com/mitchnegus) ([#21](https://github.com/sandialabs/firewheel/pull/21))
- Enabling the passing of the PYPI token to this workflow [@sdelliot](https://github.com/sdelliot) ([#30](https://github.com/sandialabs/firewheel/pull/30))
- ci: Add new CI actions to autotag PRs and update release notes and changelog entries [@sdelliot](https://github.com/sdelliot) ([#62](https://github.com/sandialabs/firewheel/pull/62))
- Provide CI testing support [@mitchnegus](https://github.com/mitchnegus) ([#8](https://github.com/sandialabs/firewheel/pull/8))

## 📄 Documentation

- This fixes the license appearance on PyPI [@sdelliot](https://github.com/sdelliot) ([#9](https://github.com/sandialabs/firewheel/pull/9))
- Adding the horizontal logo for FIREWHEEL to the README [@sdelliot](https://github.com/sdelliot) ([#12](https://github.com/sandialabs/firewheel/pull/12))
- Adding a badge for the Open Source Security Foundation (OpenSSF) Best Practices [@sdelliot](https://github.com/sdelliot) ([#13](https://github.com/sandialabs/firewheel/pull/13))
- Fixing a few references to gitlab that should be github [@sdelliot](https://github.com/sdelliot) ([#10](https://github.com/sandialabs/firewheel/pull/10))
- Update documentation with minor changes [@mitchnegus](https://github.com/mitchnegus) ([#56](https://github.com/sandialabs/firewheel/pull/56))
- Adding the model component documentation once it becomes available. [@sdelliot](https://github.com/sdelliot) ([#15](https://github.com/sandialabs/firewheel/pull/15))
- Fixing minor spacing issue with installing model components [@sdelliot](https://github.com/sdelliot) ([#45](https://github.com/sandialabs/firewheel/pull/45))
- Removing outdated references to Elasticsearch [@sdelliot](https://github.com/sdelliot) ([#26](https://github.com/sandialabs/firewheel/pull/26))

## 🧩 Dependency Updates

<details>
<summary>15 changes</summary>

- Update grpcio requirement from \<=1.68.0,>=1.49.0 to >=1.49.0,\<=1.69.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#40](https://github.com/sandialabs/firewheel/pull/40))
- Update grpcio-tools requirement from \<=1.68.1,>=1.49.0 to >=1.49.0,\<=1.69.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#42](https://github.com/sandialabs/firewheel/pull/42))
- Update protobuf requirement from \<=5.28.3,>=5.0.0 to >=5.0.0,\<=5.29.3 @[dependabot[bot]](https://github.com/apps/dependabot) ([#43](https://github.com/sandialabs/firewheel/pull/43))
- Bump ruff from 0.7.4 to 0.9.2 @[dependabot[bot]](https://github.com/apps/dependabot) ([#46](https://github.com/sandialabs/firewheel/pull/46))
- Update coverage requirement from \<=7.6.8 to \<=7.6.10 @[dependabot[bot]](https://github.com/apps/dependabot) ([#37](https://github.com/sandialabs/firewheel/pull/37))
- Update jinja2 requirement from \<=3.1.4,>=3.1.2 to >=3.1.2,\<=3.1.5 @[dependabot[bot]](https://github.com/apps/dependabot) ([#34](https://github.com/sandialabs/firewheel/pull/34))
- Update grpcio-tools requirement from \<=1.68.0,>=1.49.0 to >=1.49.0,\<=1.68.1 @[dependabot[bot]](https://github.com/apps/dependabot) ([#25](https://github.com/sandialabs/firewheel/pull/25))
- Update pytest requirement from \<=8.3.3 to \<=8.3.4 @[dependabot[bot]](https://github.com/apps/dependabot) ([#24](https://github.com/sandialabs/firewheel/pull/24))
- Update grpcio requirement from \<=1.67.0,>=1.49.0 to >=1.49.0,\<=1.68.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#17](https://github.com/sandialabs/firewheel/pull/17))
- Update coverage requirement from \<=7.6.7 to \<=7.6.8 @[dependabot[bot]](https://github.com/apps/dependabot) ([#16](https://github.com/sandialabs/firewheel/pull/16))
- Update grpcio-tools requirement from \<=1.66.2,>=1.49.0 to >=1.49.0,\<=1.68.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#11](https://github.com/sandialabs/firewheel/pull/11))
- Update pytest-cov requirement from \<=5.0.0 to \<=6.0.0 @[dependabot[bot]](https://github.com/apps/dependabot) ([#6](https://github.com/sandialabs/firewheel/pull/6))
- Bump ruff from 0.7.1 to 0.7.4 @[dependabot[bot]](https://github.com/apps/dependabot) ([#4](https://github.com/sandialabs/firewheel/pull/4))
- Update coverage requirement from \<=7.6.1 to \<=7.6.7 @[dependabot[bot]](https://github.com/apps/dependabot) ([#7](https://github.com/sandialabs/firewheel/pull/7))
- Update protobuf requirement from \<=5.28.2,>=5.0.0 to >=5.0.0,\<=5.28.3 @[dependabot[bot]](https://github.com/apps/dependabot) ([#5](https://github.com/sandialabs/firewheel/pull/5))
</details>

**Full Changelog**: https://github.com/sandialabs/firewheel/compare/v2.7.0...v2.8.0


[Changes][v2.8.0]


<a id="v2.7.0"></a>
# [v2.7.0](https://github.com/sandialabs/firewheel/releases/tag/v2.7.0) - 2024-11-15

This is the initial release of FIREWHEEL. 

FIREWHEEL releases can be installed from the [Python Package Index (PyPI)](https://pypi.org/project/firewheel/2.7.0/).

[Changes][v2.7.0]


[v2.9.0]: https://github.com/sandialabs/firewheel/compare/v2.8.1...v2.9.0
[v2.8.1]: https://github.com/sandialabs/firewheel/compare/v2.8.0...v2.8.1
[v2.8.0]: https://github.com/sandialabs/firewheel/compare/v2.7.0...v2.8.0
[v2.7.0]: https://github.com/sandialabs/firewheel/tree/v2.7.0

<!-- Generated by https://github.com/rhysd/changelog-from-release v3.9.0 -->
