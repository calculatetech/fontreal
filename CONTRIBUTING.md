# Contributing

Keep documentation usable from a fresh public checkout. Use repository-relative links, configurable output locations, and generic examples. Do not publish personal filesystem locations, machine names, local network links, or private work records.

Standard operating-system paths can appear when a procedure needs them. Public capture metadata must use filenames or descriptive source identifiers. Keep font versions, hashes, source relationships, and crop coordinates intact. Source identifiers describe capture inputs and are not download links.

## When to run tests

Run tests when Fontreal itself changes. This includes changes to rendering, patches, build recipes, integration logic and launch behavior. Select checks for the changed behavior.

Building unchanged Fontreal sources for a supported application does not require another test run. Installing a validated profile, moving to another machine and updating a supported application do not trigger regression tests, pixel comparisons, application qualification or VM lifecycle checks.

Routine deployment still requires a successful build, artifact integrity, compatible packages and ordinary activation checks. Test reports are development evidence. Native installation and application activation do not require a report for each build.

Honor an explicit instruction to skip tests. Do not run tests indirectly through another tool or agent. Record the skipped checks without claiming that they passed.

For documentation affected by a Fontreal change, the documentation checks are:

```sh
python3 tests/docs_test.py --self-test
python3 tests/docs_test.py
```

CI also runs these checks for ready pull requests and changes to the default branch. They inspect prose, structured metadata, and PNG text metadata. Review visible text in screenshots before adding them. Do not retouch scientific captures to conceal a path. Replace or omit the affected capture instead.

Build sources, profiles, logs, and results belong in ignored output directories. Preserve upstream licenses and public author attribution. Describe tested rendering paths and limitations accurately.
