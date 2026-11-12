# Contributing

Keep documentation usable from a fresh public checkout. Use repository-relative links, configurable output locations, and generic examples. Do not publish personal filesystem locations, machine names, local network links, or private work records.

Standard operating-system paths can appear when a procedure needs them. Public capture metadata must use filenames or descriptive source identifiers. Keep font versions, hashes, source relationships, and crop coordinates intact. Source identifiers describe capture inputs and are not download links.

Before you commit documentation, run:

```sh
python3 tests/docs_test.py --self-test
python3 tests/docs_test.py
```

These checks also run for ready pull requests and changes to the default branch. They inspect prose, structured metadata, and PNG text metadata. Review visible text in screenshots before adding them. Do not retouch scientific captures to conceal a path. Replace or omit the affected capture instead.

Build sources, profiles, logs, and results belong in ignored output directories. Preserve upstream licenses and public author attribution. Describe tested rendering paths and limitations accurately.
