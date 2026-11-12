# Portable public documentation

## Outcome and authority

Documentation must work for a public checkout without exposing a contributor's filesystem or private work records. The public-documents requirement supersedes the earlier private-repository wording. It does not change renderer behavior or publish the GitHub repository.

Base: `a3128b87a7ec09b319a5a3c8226db6cc99ebdbb4`. Branch: `feature/gtk-rendering`. This is the documentation portion of FR-012. Package publication and remaining application coverage retain their roadmap owners.

## Owners and scope

The composing owners are project documentation, comparison metadata, contributor guidance, and the documentation check. Existing screenshots, licenses, renderer code, and installed application state are preserved. Git history and repository visibility are outside this change.

Replace personal filesystem locations and private artifact references with repository-relative paths, descriptive source identifiers, or configurable locations. Retain generic operating-system paths where a procedure requires them. Keep supported versions, font identities, hashes, crop rectangles, and technical limitations accurate.

The reference images must retain their original bytes. Public metadata can normalize source labels, but every region must still identify the same source hash and coordinates. Do not claim that untracked capture sources are downloadable repository files.

## Implementation boundary

One atomic subtask, FR-012-DOCS, owns the documentation edits, metadata normalization, contributor policy, and standard-library guard. The guard checks all tracked project prose, documentation metadata, and PNG text metadata. License texts retain their upstream bytes. It rejects personal or mount-specific paths, local file URLs, local network links, private work references, and absolute metadata locations.

CI runs the same guard for ready pull requests and pushes to the default branch. Draft pull requests and task-branch pushes must not start this workflow. This adds no renderer dependency, installer behavior, external publication, or history rewrite.

## Proof

| Requirement | Contrast and oracle | Check |
| --- | --- | --- |
| Remove existing local references | Complete tracked-document scan succeeds after the edits | `python3 tests/docs_test.py` |
| Prevent recurrence | Synthetic home, mount, Windows, file-URL, local-link, private-work and encoded metadata cases fail; portable paths and upstream URLs pass | `python3 tests/docs_test.py --self-test` |
| Preserve the images | Every tracked PNG hash equals the task base | Compare tracked PNG bytes against the base commit |
| Preserve provenance | Every normalized region source resolves to the same original source hash; rectangles and pixel hashes stay equal | Compare manifest relationships against the base commit |
| Keep future checks automatic | Workflow calls the guard and its self-check, with explicit ready-PR/default-branch triggers | Inspect the workflow and run its exact commands locally |

This is a static documentation and test change. There is no runtime composition boundary requiring trace closure. Complete native correctness review before the documentation commit and authorized progress push.

## Decision Log

- Normalize capture source names rather than deleting scientific provenance.
- Keep actual build locations in generated, ignored records. Public instructions describe configurable output directories.
- Keep immutable upstream license texts and public authorship attribution.
- Check image metadata automatically and inspect visible capture text separately. A text scan cannot certify every pixel in an image.
