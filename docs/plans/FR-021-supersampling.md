# V2 native rendering


## Outcome and reconciliation


Publish an installable V2 with O NORMAL as the general profile and K3 NORMAL as the per-user alternative. Preserve the approved formulas while further optical experiments use a separate line. The user accepts the current appearance: stock is competitive and sometimes preferred on light backgrounds, while the prototype is clearly preferred on dark backgrounds. Do not claim universal improvement or add background-dependent tuning.

Base: 3f07596aa0707f8d647c299ec8d2c88eff481e7e. Task branch: feature/fontreal-v2, an isolated writable branch in the existing checkout. Local main and origin/main match at task start. Prior plan reconciliation: completed SS-12 and its exact comparison contract remain at that base commit in this path. This revision replaces only its unfinished optical assessment and next work. Historical producers, commands, numerical meanings and installed V1 remain unchanged during the first checkpoint.

V2 names the accepted rendering generation. The source version is 2.0.0 in VERSION, with immutable release tag v2.0.0. This matches the user's requested V2 publication. Native package versions retain their separate running-system build identities. A numerical checkpoint alone is not a V2 release. This specification remains the current compatibility baseline for V2 integration maintenance and the user's subsequent optical experiments.

## Subtasks and owners


SS-13 ports the accepted numerical kernel to native C++. New owners are src/fontreal_v2_coverage.cpp and src/fontreal_v2_coverage.h, with tests/v2_coverage_probe.cpp and tests/v2_coverage_test.py providing direct proof. The experiment guide owns usage, this plan owns decisions, and docs/roadmap.md alone owns lifecycle state. The checkpoint contains these sources and their affected prose. Its review and local commit boundary is the complete new kernel and proof since the task base.

SS-14 connects the proven kernel to the private FreeType renderer and its existing private builder. Its boundary is defined below. O and K3 must ultimately work through ordinary application launches, with the existing stock escape and working data preserved. Each actual renderer must supply its own aligned outline reference. A host library mapping alone is not application coverage.

SS-15 prepares the versioned release, repeatable instructions, accurate comparisons and release notes. Preserve the light/dark tradeoff. Complete cumulative final review and publication gates before a release. These later subtasks require their own accepted preflight within this same plan. No installed change or release follows SS-13 alone.

SS-16 carries the native integration through the existing Debian and Ubuntu package owners. It retains the complete package prerequisite: selected-input identity, source copying, object rules, shared and static linkage, corresponding source, notices, declared i386 counterparts and retained bundle verification. Qualify actual package outputs before SS-15 publication. A private-library check does not satisfy this obligation.

SS-14 and SS-16 form one package-capable checkpoint. Their shared render patch is also an input to the existing native worker. That consumer must receive every required source and object before a coherent checkpoint is committed. This refines only unfinished integration order. It does not change the frozen numerical kernel or add another rendering policy.

SS-17 connects the frozen profiles to the supported Teams and Bitwarden Skia engines. SS-18 supplies one per-user preference and ordinary launch propagation. Both require their bounded preflights and must finish before SS-15. The scope split changes only unfinished work. SS-13 remains unchanged in commit 64f7148084c7fc715b9377f46991b87e4c7ba151.

## SS-13 product boundary and model


The supported model is one synchronous native call, ordinary owned grayscale buffers, a supplied FT_Memory allocator, and genuine retained native NORMAL source data. The source policy is native hints, grayscale, interpreter 40, darkening off and no automatic hints or bitmap strikes. The same numerical rule applies to every font and character.

The accepted Python owners remain opaque and byte-unchanged: tools/native_stems.py::treatments, tests/stem_core_test.py::concentrate, tests/stroke_profiles.py::refine, tests/pixel_reference_profiles.py, tools/pixel_references.py::process and tools/arial_coherence.py::local_coherence. Their reference rasters, source capture and shaping owners remain opaque. The new composition from registered numerical inputs through D, references, O/K3 and returned bytes is in scope. Keep src/fontreal_coverage.cpp and its header, existing producers, patches, builders and activations byte-exact to the base.

Do not port unused weight fitting, compact F/G, K5 or diagnostic branches. Do not add a runtime subprocess, Python dependency inside applications, cache, service, font exception, new hinting rule, polarity heuristic, package change or settings interface in SS-13. Do not run unrelated application qualification. CONTRIBUTING.md owns test policy.

## SS-13 interface and numerical contract


Add a hidden C entry with FT_Memory, a mutable FT_Bitmap raw mask, a const registered FT_Bitmap four-times raster and an explicit O/K3 enum. Both inputs are grayscale with 256 levels. The four-times source has dimensions 4*(raw.width+6) by 4*(raw.rows+6). Its origin is three native pixels outside the original raw left/top. Raw and high inputs independently support the ordinary signed pitch representation. Preserve both bitmap metadata records, high input bytes, raw row padding and external positions, bearings and advance.

Calculate D on the original raw frame using concentrate(raw, raw, near_ties=True), then refine with connected=True and select corners. Internally use the accepted two-pixel native padding and three-pixel high-source padding. Use all 25 phase footprints, eight-connected components, squared-sum scores, exact integer rounding and deterministic distance/dy/dx phase ties. O changes only accepted primary pixels through max(D,C). K3 uses the same-component radius-one neighborhood and axis restrictions, then adds the accepted rounded half of S-minus-L fringe coverage.

Write only the original raw pixel area, after the entire calculation succeeds. Prove that zero-registering this result into the accepted padded frame equals every reference byte. Frozen support rules leave padding zero. Empty raw input is a no-op whose normalized reference remains the four-by-four zero frame. The harness preserves the positive space advance outside the kernel.

Return zero for success, one for allocation failure and two for invalid arguments. Use checked dimensions and pitch arithmetic, valid format/mode and required pointers. Reject malformed registration without changing either input or metadata. Temporary storage belongs to the supplied FT_Memory owner and is released before return. No per-glyph state survives a call. Do not add injected allocation-failure or environment-failure matrices.

Exact native D observation is mandatory from the same real native-entry call that produces the checked final output. A passive compile-time test observer can copy D through const access. It must not recompute D separately or change numerical behavior. Compile the ordinary kernel too and compare its real final outputs with the observed build. Do not add a public D mode.

## Decision Log


The user accepts O NORMAL for the general V2 choice and K3 for personal use. Existing stock rendering remains a useful comparison and recovery choice. Further tuning must not silently alter the accepted release target.

This is a port of fixed numerical definitions and an existing raster mechanism. No open algorithm selection or new prior-art study is needed for SS-13. A registered four-times bitmap is the explicit opaque source seam; no numerical stage inside the new kernel is replaced by Python or a test callback.

The two-phase independent challenge identified two proof requirements. First, final maxima can hide a wrong D value, so the same-call D observer is mandatory. Second, positive packed inputs cannot prove signed pitch behavior. Use a small successful representation set with negative/padded raw and high inputs independently, rather than a corpus-wide product.

## Boundary inventory and source dispositions


| Boundary | Source and required contrast | Entry and scenarios |
| --- | --- | --- |
| B-V2-1 | Accepted native D versus legacy gain/winner/weighted processing, omitted near ties or omitted connected refinement. Native treatment, concentrate and refine owners. | Native entry; S-V2-1. |
| B-V2-2 | Complete eight-connected component scoring and primary O overlay versus local/prefix/four-connected selection or changed ties/rounding. Pixel reference owners. | Native O entry; S-V2-2. |
| B-V2-3 | Same-component radius-one K3 with allowed axes and ceil-half fringe versus O/K5, forbidden phases or omitted/floor-half fringe. Coherence and overlay owners. | Native K3 entry; S-V2-3. |
| B-V2-4 | Original NORMAL frame, aligned four-times source, actual Qt raster and padded equivalence versus MONO/union/nominal-size substitution, stale empty output or shifted geometry. Native and Qt reference owners. | Both modes; S-V2-4/5. |
| B-V2-5 | Numerical-only generic processing and explicit profile choice versus identity exceptions or a selector that always uses one profile. User requirement and README. | Both modes; S-V2-5/6. |
| B-V2-6 | Supplied allocation ownership, independent signed strides, unchanged guards/metadata and atomic output versus stale state, unowned storage or incorrect row interpretation. Existing native ABI pattern and this interface. | Both modes; S-V2-5. |
| B-V2-7 | Isolated new kernel and truthful acceptance versus activation, retuning, old-source changes or a claimed installed V2. Current scope and user feedback. | Proof CLI; S-V2-6. |
| B-V2-8 | Complete source-bound corpus/profile obligations versus correct-prefix or borrowed output. Retained NORMAL and native Qt owners. | Proof CLI; S-V2-6. |

All near-tie, run-vote, protection, connected-anchor, proposal-conflict, interrupted-channel, step and corner clauses map to B-V2-1. Component membership, full phase collection, footprint rounding and primary selection map to B-V2-2. Local axis restrictions, phase ties, donor eligibility and odd half-edge rounding map to B-V2-3. Native source policy, source raster equality, own-frame registration, CFF distinctions, real Qt sizing, empty geometry and both stride signs map to B-V2-4/6. Generic identity handling maps to B-V2-5. Ordinary allocation balance, input validation and repeated-call independence map to B-V2-6. Preservation and accurate optical acceptance map to B-V2-7. Complete conditions, glyph identities, repeated values, spaces and shaped Qt glyphs map to B-V2-8.

Unused diagnostics, K5, installed integration, release and future tuning are deferred. Old numerical/reference implementations, source capture, shaping and deployed V1 are opaque. Human optical acceptance and test-policy procedures are non-boundary obligations. No unresolved contract gap remains for this checkpoint.

## Scenario Proof


Use one exact named command:

    python3 -B tests/v2_coverage_test.py --record FREETYPE_BUILD_JSON --normal-manifest NORMAL_MANIFEST --qt-manifest QT_MANIFEST

Use the complete retained 20-condition, 1900-row NORMAL corpus and the eight-condition, 784-row native Qt source set. Keep duplicate polarity rows and their identities. Qualify the supplied stock provider against both sources for independent 1x/4x raster checks. Load original raw masks, hinted outlines and registered high sources, rather than historical display unions. The proof CLI compiles the new ordinary and observed native entries and calls them for every source row and both profiles. No in-scope numerical hop is replaced.

A tiny, explicitly labeled numerical fixture can supplement a local arithmetic contrast absent from the genuine corpus. It does not establish font geometry or provider compatibility and cannot replace any genuine source proof. In particular, diagonal support must expose an incorrect four-connected O selector even when genuine final bytes happen to match.

| Scenario | Discriminator and minimal contrast | Complete path and required terminal oracle |
| --- | --- | --- |
| S-V2-1 | D eligibility/votes and connected refinement. Include active near-tie and refinement witnesses, zero-vote/strong protection and rejected proposals. Final max can hide D errors. | Real native entry to passive same-call D observation to final O/K3. Compare every observed D byte with the frozen independent reference and its padded equivalence. Require output witnesses exposing legacy or omitted-stage alternatives. |
| S-V2-2 | O component completeness, connectivity, deterministic phase ties, rounding and primary membership versus local, truncated or four-connected choices. | Real raw/high inputs to native D, complete component scoring and O overlay to actual returned bitmap. Compare full padded O with independent scalar references. Retain non-vacuous terminal-byte contrasts, including a prefix whose later pixels alter the result. |
| S-V2-3 | K3 radius, component and axis restrictions, plus odd half-fringe rounding, versus O/K5, forbidden phases and omitted/floor-half fringe. | Real native D through references, local scoring and fringe addition to returned K3. Compare all bytes with the independent scalar K3 oracle. Record active/protected and odd-delta terminal witnesses. |
| S-V2-4 | Own NORMAL source geometry, CFF distinction and Qt 10pt resolved to 13 pixels versus historical MONO/union or nominal fractional points. Empty versus intervening nonempty calls. | Source qualification to independent 1x/raw and 4x registration to both native modes. Exact original bitmap, padded result, zero support and preserved metadata/advance. Space stays empty and normalized to the accepted four-by-four zero frame. |
| S-V2-5 | Explicit O/K3 choice, ordinary buffer ownership, signed stride and previous-call state. | Same real native entry on packed inputs, one asymmetric genuine glyph with padded negative raw/positive high and positive raw/padded negative high, both modes. Hold numerical pixels constant. Exact output, same-call D, metadata, row guards, immutable high source and balanced FT_Memory counts. Repeat a glyph after another profile/glyph and space. Invalid mode/format/pitch/high dimensions reject with status two and no input mutation. No injected allocation failure. |
| S-V2-6 | Complete declared input/profile set and generic rules versus borrowed prefix data, identity dispatch or changed historical state. | Real proof CLI to actual ordinary/observed native calls to per-row results and isolated output. Check independent condition/glyph/profile inventories through the last case, source hashes, all expected calls and source/input preservation. Relabel identical numerical input and require identical bytes. Compare ordinary and observed output. Inspect the bounded write graph and truthful V2 acceptance docs. |

Reuse exact source-bound retained receipts only for opaque compatibility. New numerical composition and all current output require this named check. The kernel and proof are synchronous with no retained-work reopening event. Do not invent a new corpus import API to test accounting.

## Checks and checkpoint boundary


Keep compiled output below build/v2-coverage and scientific records below results/v2-coverage. Use the existing storage-backed roots. Finalize affected prose, then run the named check and the documentation checks required by CONTRIBUTING.md:

    python3 -B tests/docs_test.py --self-test
    python3 -B tests/docs_test.py

Before the SS-13 checkpoint commit, complete fresh boundary trace closure and native review of its complete candidate since 3f07596. Current results belong in the ignored task evidence. Keep FR-021 active while native integration and release remain. This checkpoint changes no installed app and makes no application coverage or performance claim.

## SS-14 private FreeType integration

### Goal, owners and supported model

An ordinary private FreeType library must render the frozen O or K3 result through its public load and render calls. Preserve the existing activation authority and V1 behavior when no valid V2 preference is present. The model is a synchronous library, face and glyph slot, with a startup preference and ordinary full application restart for changes.

| Owner | Classification | Product fact |
| --- | --- | --- |
| FreeType rendering patch, private library state and tools/build-freetype.py | Composes | Own activation, normalized load policy, actual native mask, support raster, numerical dispatch and real artifact construction. |
| SS-13 kernel and frozen scalar references | Opaque | Exact accepted numerical definitions and source-bound proof remain unchanged. |
| Pinned native FreeType driver and outline rasterizer | Opaque | Actual public rendering owns raw footprint, outline flags, metrics, advances and native errors. |
| Existing Qt adapters and legacy core | Opaque | Preserve their Boolean activation request, native geometry policy and V1 formulas. |
| System package owners | Deferred, SS-16 | Require actual shared/static/corresponding-source and declared architecture qualification before release. |
| Skia, launchers and persistent user preference | Deferred | Require separate integration preflights and reached application proof before release. |

The existing entry points are FT_Load_Glyph, FT_Load_Char and FT_Render_Glyph. The FreeType patch owns their selected path. FT_LibraryRec owns the startup preference. The glyph slot retains the current outline until rendering advances it to a bitmap. Native and caller outline transforms preserve eligibility but change the support source. A new load clears previous slot work. Size and variation changes affect the next load. A repeated render of a bitmap preserves its once-treated bytes. No high raster survives a call.

Do not change either numerical core/header, old Python references, Qt patches, system packages, launchers or working application data in SS-14. Do not add a service, live cache invalidation, runtime Python, font or character exception, background heuristic, optical tuning or allocation-failure matrix. No installed V2 or application coverage claim follows this checkpoint.

### Selection and native input policy

Read FONTREAL_PROFILE once at FT_New_Library. Exact lowercase o and k3 mean private values one and two. Absence and every unsupported token mean no V2 preference. Store the value in FT_LibraryRec so supported removal of the automatic hinter cannot erase it. An optional private typed getter through the existing module property mechanism can expose the library value. It adds no public FreeType export or profile setter.

A preference is not activation. Keep the existing selected-v1 typed Boolean or FONTREAL_FT_RENDERING=1 with its exact executable scope as the authority. A valid preference selects the V2 numerical branch only inside that eligible path. Keep the old Boolean Set/Get, default, string rejection and library isolation unchanged. When both are present, run V2 once. Without a V2 preference, keep V1. Browser disable must remain effective even when a process inherits a session preference.

Eligible V2 loads use native NORMAL hints, grayscale, no automatic hints and no bitmap strikes. Retain the existing scalable, format, color and load-flag exclusions. Render eligibility also requires the actual stored normalized load flags. Keep native rendering independent of automatic-hinter execution or continued module presence under the existing environment activation path.

The accepted source policy has CFF stem darkening off. A face override can beat the driver default. Save the face setting, force darkening off for the eligible V2 load, then restore the original setting through every native success or error exit. Do not rewrite module-wide policy. Ineligible work and later caller operations retain their original face and driver settings. Keep the existing interpreter policy.

Use actual native FT_Render_Glyph for the raw bitmap and its footprint. Copy the render-time hinted and transformed outline, preserving points, tags, contours and flags. Rasterize that copy directly through FT_Outline_Get_Bitmap at four-times coordinates into the kernel's registered high frame. Do not reload the font at four-times size or recursively call the selected renderer. Preserve the source outline, raw metadata, bearings, metrics and advance. Check dimension and coordinate arithmetic. Native zero-area results, including one-zero-dimension bitmaps, bypass the numerical kernel without introducing an error.

Release temporary storage on every exit. Preserve native errors and the existing mapping of kernel allocation/argument statuses to FreeType errors. Do not silently substitute V1 or stock on a selected processing error.

The private builder must hash and copy both V2 source files, compile and link the new object alongside the legacy object, retain stock controls and upstream/MIT notices, and preserve public exports. A receipt missing or staling only a V2 source cannot qualify a new build. Reuse the existing recipe and artifact owner.

### SS-14 boundaries and Scenario Proof

The Phase 1 source clauses map to the following inventory. All selection, library lifetime, activation, exact-scope and typed-property clauses map to B-FT2/3/10. Native source eligibility and retained-slot transitions map to B-FT4/5/8/9. Outline identity, flags and registration map to B-FT6/7. Native errors, resource ownership, builder identity and notices map to B-FT11/12/14. Frozen numerical arithmetic is opaque under B-FT1. Package propagation is deferred under B-FT13, not waived. Human optical acceptance and test policy are non-boundary obligations. No unresolved contract gap remains.

Use this one composed named integration check, with per-scenario evidence rather than an aggregate pass alone:

    python3 -B tests/v2_freetype_test.py --record V2_BUILD_JSON

Its public callers must load the actual candidate from the ordinary private builder. Independent stock native calls supply raw/source-policy oracles. Frozen scalar definitions supply numerical expectations. A passive compile-time observer can copy raw/high/mode from the same actual adapter call, but cannot supply a numerical result. The ordinary candidate must independently produce the same final bytes. Do not replace an in-scope adapter or builder hop with a separately linked test implementation.

| Boundary and source | Discriminator and contrast | Production path, terminal oracle and scenario |
| --- | --- | --- |
| B-FT1: accepted O/K3 and SS-13 ABI | Frozen generic O/K3 versus V1, retuning or a selector that always returns one mode. | S-FT1: actual public deferred and immediate calls on TT and CFF sources through native mask, current-outline support and frozen core. Compare complete independent expected bytes and metadata. Require a profile-difference witness. |
| B-FT2: startup preference and existing activation | Absent/invalid/o/k3, valid preference without activation, fresh versus existing library, surviving module removal. | S-FT2: fresh processes and libraries through real initialization, activation gate, public load/render and returned bytes. Observe mode where available. Mutate the environment after initialization and prove the old library stays fixed while a new library changes. Remove autofitter under matching environment activation and prove exact O rather than V1 output. |
| B-FT3: old selected-v1 property contract | Typed Boolean true/false, fresh-library default and string rejection, with and without valid V2 preference. | S-FT2/10: actual property Set/Get and defaults through eligible calls to full output. The Boolean stays Boolean and library-local. Valid V2 preference overrides numerical dispatch once. |
| B-FT4: existing load gate and stored render provenance | Eligible outline versus each distinct exclusion, including NO_HINTING, NO_SCALE, NO_RECURSE, ADVANCE_ONLY, BITMAP_METRICS_ONLY, non-scalable/color/non-outline and mismatched stored target. | S-FT3: actual public requests to native driver and render gate. Compare complete stock status, flags, outline/bitmap, metadata, metrics and advances for bypasses. Use minimal predicate witnesses without a Cartesian product. |
| B-FT5: CFF driver and face precedence | Selected darkening off versus driver ON and explicit face ON, followed by ineligible work. | S-FT4: real properties and selected native loading through actual CFF masks to frozen expected output. Observe restored caller state and later stock-equivalent ON output. Module-only changes cannot pass the explicit face counterexample. |
| B-FT6: kernel registration and render-time source | Current transformed outline versus stale/pre-transform source, four-times rehinting or incorrect top registration. | S-FT5: actual load, native/caller phase or transform, render, owned copy, direct high raster and V2 output. Compare same-call high observation with an independent flags-preserving stock raster and complete final bytes. Preserve source outline. Each wrong meaning needs a differing witness. |
| B-FT7: native footprint and outline flags | Actual native raw renderer versus control-box or flags-zero reconstruction. | S-FT6: eligible loaded outlines with separately discriminating overlap and fill-rule cases through actual stock/candidate FT_Render_Glyph and high support. Compare raw, support, metadata and final bytes. A single nondiscriminating glyph cannot prove both flags. |
| B-FT8: valid native empty output | Space and singular-transform zero extent versus nonempty work. | S-FT7: public load/render of each empty representation followed by nonempty work in the same slot. Match stock empty metadata, advance and status, then the proper selected nonempty result. Never pass a one-zero-dimension bitmap to the kernel. |
| B-FT9: slot lifecycle and complete current-call results | Once versus twice processing, duplicate prefix followed by changed glyph/phase/size and return to original. | S-FT8: load/render/render/new immediate load, using a fixture where twice-treatment differs, must return once-treated bytes. S-FT9: complete ordered n,n,later-counterexample, size/variation, ineligible and eligible-return sequence. Every call gets its own oracle, including space. No result or support deduplication. |
| B-FT10: existing diagnostic and scope meanings | V2 absent with weighted/raw/ramp217/mild/none/nearest, exact/later colon match versus prefix or wrong scope. | S-FT10: actual old activation/property/load/render to independent legacy or stock results. Reuse retained checks only for exact unchanged opaque contributors. Changed adapter composition must execute. |
| B-FT11: native errors and temporary ownership | Failed native load versus success while CFF scoped policy is active. | S-FT11: invalid glyph index at the actual face boundary, then valid and ineligible calls. Match native error, restored state and later own pixels. Inspect cleanup and unchanged status mapping. No injected resource faults. |
| B-FT12: production private builder | Exact V2 objects/inputs versus an old or missing/stale-only-V2 receipt. | S-FT12: real tools/build-freetype.py source/key/copy/compiler/link path to the actual loaded candidate and public V2 output. Verify source hashes, object inclusion, artifact identities, stock control and stale-input rejection. |
| B-FT13: system package owners | Private artifact versus actual distro package delivery. | Deferred to SS-16: real worker, shared/static/i386 callers, corresponding source, identities, notices and retained-bundle verification before release. SS-14 makes no package claim. |
| B-FT14: existing export and attribution contract | Hidden implementation and complete notices versus a public ABI change or lost license. | S-FT12: actual stock/candidate public export equality and complete source/license inventory from the production build. |

Use source-bound SS-13 results only for unchanged numerical arithmetic. Run the new adapter and actual builder paths. Keep builds below build/v2-freetype and existing builder output, and records below results/v2-freetype. Finalize affected prose and both CONTRIBUTING.md documentation checks before fresh checkpoint trace and native review. Detailed execution and lifecycle evidence belongs only in the ignored task result.

The two-phase challenge accepted preference-only activation and the split package prerequisite. Its one supported correction moved preference ownership from the removable autofitter to FT_LibraryRec and added the removal witness. This preserves the existing native path without adding an activation authority. No new prior-art choice is open: the fixed kernel uses FreeType's existing direct outline rasterizer.

## SS-16 native package integration

### Outcome, owners and scope

The existing full native worker must produce V2-capable FreeType, QtBase and Declarative packages for Debian 13 and Ubuntu 26.04. Both numerical objects must reach shared libraries, static archives and every declared i386 counterpart. The bundle must retain exact corresponding source, notices, originals and verification. A private build is not a substitute.

The composing owners are tools/system-build.py, packaging/freetype-capability.patch, their generated quilt source addition, and the existing preparation and transaction consumers in tools/system_install.py. Native APT/dpkg and configured distro toolchains are opaque providers. The qualified SS-14 adapter, both frozen kernels, scalar references, Qt patches and capability bridges are opaque unchanged inputs. Persistent profile selection and fresh-login V2 inheritance remain separate activation work. Host installation and publication follow review.

Use existing source pins and the full three-family worker. Do not add an FT-only command, partial bundle, new cache framework, platform, renderer policy, service or optical change. Keep build and compiler data on the existing storage-backed output volume. Builds do not install packages or change the user's enabled marker. Do not repeat unrelated Plasma, browser or independent-update matrices.

### Identity, source and linker contract

Current selected inputs use the distinct identity native-normal-o-k3-v2. Keep the legacy render, processor, declaration and license hashes, and add v2_processor and v2_declaration hashes. Current construction requires the full current shape and values before destination creation. Recorded verification uses the recognized generation's own key set. Literal historical native-normal-weighted-stems-v1 records keep their original four-hash shape. Retain the existing raw and Qt-only verification/rollback cases. Reject unknown profiles and incomplete known shapes. Do not impose current source hashes on retained records.

selected_plan remains a capability classifier for known selected V1 and V2 integrations with their capability patch. Preserve V1 preparation and installation compatibility. Raw and Qt-only records do not gain selected capability. A V2-capable artifact does not enable treatment by itself. Explicit o/k3 remains a process preference behind the unchanged Boolean or scoped environment activation. Absence and unsupported tokens retain V1.

Copy all four numerical source/header files into the existing generated quilt addition. Include each file in corresponding source and the complete MIT copyright stanza. Preserve upstream notices. Add the V2 object beside the legacy object through existing configured target CXX/CXXFLAGS, C++17, PIC, hidden visibility and libtool CXX rules. Preserve native CC_BUILD, hardening, SONAME, export list and static dependency metadata. The existing conditional i386 worker must compile the emitted corresponding source with its target compiler.

Every package counterpart, original rollback package, source descriptor and descriptor archive owes an inventory result. Unpack source and compare all four files and integration patches with recorded hashes. Check every emitted FreeType binary's upstream and complete MIT notices, and every shared architecture's public exports against official controls. Test static amd64 linkage regardless of whether i386 is present. Qualify declared i386 with a real ELF32 caller. No dynamic FreeType borrowing can establish static success.

### SS-16 boundary inventory and proof

The independent two-phase package challenge has no unresolved finding or contract gap. Source clauses for supported profiles, native worker and storage map to B-PKG1. Input schemas and stale construction map to B-PKG2/5. Compiler, objects, link forms and ABI map to B-PKG3. Source and attribution map to B-PKG4. Preference versus activation and unchanged Qt composition map to B-PKG6. Complete artifacts map to B-PKG7. Preparation, transaction selection, versions and user state map to B-PKG8. Frozen renderer semantics and native providers are opaque. Persistent choice, host application and publication are deferred. Test policy is a non-boundary obligation.

Use the following named checks. Keep per-scenario oracles and exact commands in the ignored result record.

    python3 -B tests/system_build_test.py --originals DISTRO_BUNDLE/original
    python3 -B tools/system-build.py verify RETAINED_QT_ONLY_BUNDLE
    python3 -B tests/system_install_test.py

For each distro, SS16-PACKAGE-DEBIAN or SS16-PACKAGE-UBUNTU is the complete causal sequence: obtain a production plan from the actual matching system or disposable container's installed package identities, run tools/system-build.py build with a new output directory, verify and prepare that output, then run tests/system_package_test.py on the same bundle with the documented independent matching-provider references. Use i386-bearing plans for both declared target checks. The ordinary worker, actual source queues, native compilers, package installation and public callers must execute. Keep supported parallelism within the existing command's limits. Do not manufacture a plan from representative fixture metadata and claim an actual installed target.

| Boundary | Discriminator and minimal contrast | Production path and required oracle |
| --- | --- | --- |
| B-PKG1 | Exact supported distro and full worker versus private/manual or partial output. | S-PKG3: each named distro sequence traverses production plan, Docker worker, all three native builds, complete output and actual checker. Exact versions, source and package identities establish each provider. |
| B-PKG2 | Complete current identity versus a missing/stale V2 source or header alone, with old hashes held constant. | S-PKG1/3: real plan/build CLI rejects each invalid current input before output creation. Actual bundles bind both source/header pairs, patch, license and recipe. |
| B-PKG3 | Real shared/static/declared-i386 output versus missing objects, wrong targets, missing dependencies or borrowed dynamic implementation. | S-PKG4/5/6: actual package installation and ordinary C callers return exact independent O/K3 bytes and metadata. Static linkage uses pkg-config dependencies and has no libfreetype.so dependency. ELF32 uses its own actual counterpart and source version. |
| B-PKG4 | Complete corresponding source and all binary notices versus omitted/stale V2 files or a two-file copyright stanza. | S-PKG3/9: unpack every modified source, reconstruct its quilt queue, compare four core/header hashes and exact patches, and inspect every FreeType binary's complete upstream/MIT text. |
| B-PKG5 | Historical own-record verification versus checkout-default promotion or current-construction acceptance. | S-PKG2: verify the actual retained Qt-only bundle unchanged. Independently labeled raw-three-family and literal installed-V1 schema fixtures prove metadata compatibility only. Current build rejects historical, unknown and incomplete current shapes. No synthetic historical rendering claim. |
| B-PKG6 | Explicit o/k3 plus activation versus preference alone, absence/invalid or always-one-profile dispatch. | S-PKG4/7: real packaged public TT/CFF calls and actual Widget/Quick Boolean activation return independent O/K3 results with a differing witness. Preserve stock inactive output, no-preference V1 and existing readiness meaning. A V1 oracle cannot establish V2. |
| B-PKG7 | Complete expected collections versus empty, partial, duplicate or later-missing records. | S-PKG3/8: actual complete artifacts plus labeled metadata contrasts cover every source family, package, original and descriptor archive. Include late i386/source obligations. Exact verification errors and restored success establish full-set accounting. |
| B-PKG8 | Known selected V1/V2 consumer compatibility versus accidental current-string rejection or raw/Qt-only promotion. | S-PKG10: real prepare/verify and existing install/rollback selection checks preserve immutable native manifests, exact deployment/runtime/source identities, official originals, local version ordering and the enabled-file contract. Synthetic APT fixtures establish pre-transaction selection only. Actual package application comes from each distro checker. |

S-PKG4 includes independent TT and CFF expectations and a real O/K3 difference. S-PKG5 runs static linkage unconditionally. S-PKG6 qualifies every declared foreign counterpart, with i386 static checks when that development payload is delivered. S-PKG7 holds the font, size and native Qt activation fixed while changing only profile or disabling activation. S-PKG8 includes duplicate agreeing prefixes with a later missing record. S-PKG9 checks the entire source, notice and export sets. S-PKG10 preserves existing V1 consumers while the separate activation card supplies the persistent V2 choice.

Keep Qt patches, both kernels and the SS-14 adapter unchanged. Reuse their source-bound qualified behavior only at those opaque seams. All new package, object, source, identity and consumer hops execute through these named checks. Finish the authoritative native guide and CONTRIBUTING.md documentation checks before fresh boundary trace and a new full native review of the coherent candidate. No commit follows an incomplete shared-patch build consumer.

## SS-17 Skia and Fontations integration

### Outcome, owners and model

Both supported private Electron families must supply frozen O NORMAL and K3 NORMAL coverage from their own actual aligned Fontations outlines. Use the existing Teams and Bitwarden selected engines and ordinary builders. Absence or any unsupported FONTREAL_PROFILE token preserves V1. Exact lowercase o/k3 selects V2 for the rendering process lifetime. This preference is not a new application activation authority. A full ordinary restart applies a change.

The composing owners are both versioned selected Skia patches, integrations/chromium/fontreal_selected.h and fontreal_bridge.cpp, both selected GN patches, tools/build-electron-selected.py, its direct private source/package owners and the existing independent provider/fixture checks. Upstream decoding, Fontations path generation, mask filters, compositor and frozen numerical cores are opaque. Native application resources, working data, fuses, isolation, wrappers and transport remain opaque unchanged consumers. Persistent choice and launch migration are SS-18. Do not claim complete daily application coverage from this renderer checkpoint.

Keep the existing face/request eligibility, upstream filter order, PATH/A8 gate, normal hint target, whole-pixel placement and no-preblend behavior. Keep the provider-required Mono branch for hinting-reliant faces. Preserve actual supported bitmap capabilities and native excluded work. Do not add a font, glyph, size, coordinate or background exception. Do not add a runtime Python path, service, engine manager, live cache invalidation, decoder backport, new renderer or optical change.

### Source and completion contract

Both the member and direct completion sites must supply the actual devPath, destination bounds and hairline semantics used by the preceding raw raster. The member route uses glyph.path(). The direct route uses origGlyph.path() while storage can belong to unfilteredGlyph. Do not substitute the storage glyph's path. The base hook remains a no-op for other contexts.

Generate separate owned high coverage with Skia's existing callback-free raster capability. Scale the same already hinted, aligned and effect-applied path by four. Use bounds equal to four times the native bounds expanded by three native pixels. Dimensions are 4*(raw.width+6) by 4*(raw.height+6), with Skia's downward y-axis. Preserve raw geometry, stride, path, bearings and advances. Do not reload at four-times font size, upscale the raw bitmap or use FreeType geometry as a Fontations oracle.

V1 skips high generation. Empty native area bypasses the kernel. Both eligible routes process a new image once before native mask filtering. Cached image reuse adds no pass. Preserve the existing abort-on-processing-error meaning, exception containment and call-local temporary ownership. No silent stock fallback or retained numerical state is added.

True hairlines retain one native pixel of physical width after scaling. Reuse native Skia stroke/path capability with the actual raw cap/join semantics. A one-high-pixel hairline is incorrect. Canvas lineWidth=0 is ignored, and the current fixture's false stroke predicate selects fillText. Therefore canvas stroke:0 is not hairline evidence. A native Fontations SkFont/SkPaint stroke-zero request through real selected SkStrikeSpec and SkGlyph::setImage supplies the hairline proof. Its objects and link graph must come from the selected source view. The pristine provider independently supplies true-source raw/high expectations. Keep the ordinary nonzero canvas stroke as the separate direct-route-to-window proof.

Add the V2 source/header to runtime input hashes, copied views and both GN source lists. Keep the original cached upstream files and baseline distributions unchanged. Actual normal and trace engines must link both cores. The independent exact-provider probe must remain pristine and exclude candidate processing. Preserve release/source/tool/package/notice identities, exact unchanged reuse and the existing notice-only envelope distinction. Diagnostic fields must describe the actual source, profile, raw/high frame and final mask. Instrumentation cannot be the sole oracle.

### SS-17 boundaries and proof

The same independent challenger completed both phases. Its one accepted correction replaces the unreachable canvas-zero hairline assumption with the native production API proof above. No public contract gap remains.

Use the existing complete target commands, extended to cover absence/V1, o, k3 and a focused unsupported-token contrast:

    python3 -B tests/chromium_selected_test.py --target teams --build-record TEAMS_V2_RECORD
    python3 -B tests/chromium_selected_test.py --target bitwarden --build-record BITWARDEN_V2_RECORD

Each exact command must traverse its ordinary target builder, actual generated engine, source/target and both raster routes, frozen processing, cache lifecycle and final pixels. Opaque expectations can be shared for equal complete source inputs, but actual production work or terminal observations cannot be borrowed. Reuse the unchanged SS-13 receipt only for numerical arithmetic. FreeType cannot supply independent Fontations geometry.

| Boundary | Discriminator and contrast | Production path, scenario and terminal oracle |
| --- | --- | --- |
| B-SK1 | One process preference versus V1 fallback or always-one-profile dispatch. | S-SK1: separate real starts with absence/invalid/o/k3, multiple scaler contexts and later work. Hold source/glyph/size fixed and require exact independent V1/O/K3 bytes with differing witnesses. No live switching. |
| B-SK2 | Existing upstream-filtered face/request/representation eligibility versus widened or missing selection. | S-SK2: real named outline/color/bitmap/unhinted/transform controls, followed by eligible work. Preserve primary-face attribution and native excluded geometry/pixels. Retain positive 152 grayscale-strike evidence and the explicit 142 negative decoder capability. |
| B-SK3 | Coverage choice versus native target, geometry and placement authority. | S-SK3: real requests through upstream filtering and Fontations to raw paths/masks and placed pixels. Independent exact-provider paths, bounds, bearings, advances and actual target arguments must agree. Retain .49/.51 origin contrast and hinting-reliant Mono qualification. |
| B-SK4 | Exact current source and registered high frame versus stale/shifted/bitmap-upscaled/four-times-rehinted input. | S-SK4/5: member and direct raw raster through actual source handoff, separate high raster, kernel and image. Compare independent raw/high bytes and frames, exact final mask and unchanged metadata. Include empty results and native hairline width discrimination. |
| B-SK5 | Both real completion routes once before filtering versus omitted/double/late processing or wrong source glyph. | S-SK4/5: actual member and nonzero stroke/direct canvas paths reach independent final window pixels. Native stroke-zero SkGlyph::setImage separately proves true hairline source/high/final masks and metadata. Preserve default no-op, filter order, temporary cleanup and error meaning. |
| B-SK6 | New image work versus cache repaint, duplicate prefix or omitted later identity. | S-SK6: empty, one, duplicate m8W prefix, repaint, later g, later repaint and full matrix through normal quit/drain. Require per-stage transition counts, descriptor/image identities and every final occurrence's own expected pixels. Spaces keep empty output and advance. |
| B-SK7 | Independent provider and actual composition versus candidate-derived expectations or trace-only success. | S-SK7: real normal/trace fixtures on both palettes. Each independently matches OS pixels. Native PNG equality is a separate domain. Preserve layout/non-text controls and useful actual source/profile diagnostics. |
| B-SK8 | Relevant runtime inputs versus exact reuse or notice-only envelope changes. | S-SK8: both ordinary source/GN/Ninja/link/package paths include the new core/header and all direct inputs. Verify pristine provider independence, original source/baseline equality, complete notices, exact unchanged reuse and unchanged runtime bytes for notice-only changes. No new cache architecture. |

Map all source clauses explicitly: profile and V1 preservation to B-SK1, generic eligibility/filter/decoder boundaries to B-SK2, existing target/phase/metrics to B-SK3, high ABI and actual source authority to B-SK4, route/order/status/no-op clauses to B-SK5, all new-image/cache obligations to B-SK6, independent provider and display domains to B-SK7, and build/source/package/reuse/notices to B-SK8. Frozen arithmetic is opaque. Application activation and release are deferred. Test-policy and human acceptance procedures are non-boundary obligations.

The actual cached Teams and Bitwarden source packets are available. Keep versioned patches separate, preserve their source identities, and use storage-backed build roots. Finalize the authoritative Chromium guide and affected experiment prose, then run both CONTRIBUTING.md documentation checks before fresh trace and native review. All native package inputs remain frozen while the independent SS-16 build/check jobs run.

## SS-15a README and V2 captures

The user prioritizes replacing the README's V1 pictures and explaining the project's system impact at the start. This changes only unfinished release order. Publish genuine stock Qt versus O NORMAL V2 at the six supplied KDE defaults, in light and dark palettes. Keep the accepted light/dark tradeoff and the optional K3 choice clear. A comparison does not establish installed application coverage or a completed release.

The composing owners are README.md, a separate tests/kde_v2_comparison_test.py runner and docs/images/kde-v2. The existing Qt specimen, V1 runner and docs/images/kde-selected remain byte-unchanged. Frozen FreeType, Qt adapters, numerical formulas and their exact source-bound qualification are opaque. Package workers, launch integration and publication retain their separate owners. Use one authorized writer, normal local storage and the installed named fonts. No new renderer, profile, font exception, capture GUI, service or broad qualification matrix is added.

Reuse the real Fusion Qt Widgets specimen at 96 DPI and device pixel ratio one. Capture General, Toolbar, Menu and the window-title font specimen with Noto Sans 10pt, Fixed width with Hack 10pt and Small with Noto Sans 8pt. The title row is not a KWin decoration capture. Keep stock on the left and O on the right. Preserve all source pixels without resizing, sharpening or retouching.

The same independent challenger completed both preflight phases. Its accepted proof correction removes a proposed preincluded header: macros in the specimen cannot observe Qt's internal FreeType calls. Instead use the existing passive FreeType observation build, qualified with the ordinary build by the current SS-14 check. Bind both exact libraries and their frozen core/source hashes to that receipt. Actual observed Qt captures must produce the existing profile/raw/high callback with profile one and a nonempty correctly registered frame. Complete ordinary O and observed O capture pixels must match. Separate ordinary K3 and stock captures must supply differing pixel witnesses. Reuse independent numerical and source assertions only for those exact qualified opaque libraries. Do not claim that every screenshot glyph was independently replayed.

| Boundary | Source clause and contrast | Scenario, path and required oracle |
| --- | --- | --- |
| B-IMG1 | User requests V2; the accepted general profile is activated O, not V1, inactive stock or K3. | S-IMG1: the new runner invokes the native specimen with qualified ordinary/observed O, ordinary K3 and official stock libraries. Check actual mappings, the capture-linked profile-one callback, whole ordinary/observed equality and O/stock/K3 pixel witnesses. Use the exact current SS-14 receipt at the opaque arithmetic seam. |
| B-IMG2 | All six requested roles, actual font files, sizes, both palettes, DPI 96 and ratio one are required. Repeated Noto Sans 10pt rows cannot conceal missing Hack or Small rows. | S-IMG2: assert the complete ordered role/family/size inventory, actual font-table/file identity and nonempty in-bounds crops in every native capture. |
| B-IMG3 | Published stock-left/O-right sheets and provenance must preserve their actual sources. | S-IMG3: save and reopen each sheet, compare complete halves and every recorded crop with the original RGB bytes, and check all image/font/library/specimen hashes and README links. |
| B-IMG4 | Existing V1 assets, specimen, runner and numerical references retain their original meaning. | S-IMG4: hash the complete retained asset set before and after generation. Require an empty focused Git diff for V1 assets, specimen and runner. Write V2 to its separate directory. |
| B-IMG5 | CONTRIBUTING.md requires portable public prose, metadata and visible pixels. Intermediates belong in ignored output on the build volume. | S-IMG5: retain raw maps, logs and private paths only in ignored build/results. Public records use filenames or descriptive source identities while preserving hashes, versions and crop coordinates. Inspect both final images and run both documentation checks on the intended tracked additions. |
| B-IMG6 | Name O V2, optional K3, the light/dark tradeoff and the Fusion specimen accurately. | S-IMG6: compare README captions and manifest scope against the accepted facts. Do not infer a release, installed treatment, KWin capture, universal improvement or new app coverage from these pictures. |
| B-IMG7 | The user's added opening requirement asks what Fontreal patches, touches and leaves untouched. | S-IMG7: review the opening against the existing native, Mozilla and selected Electron guides. Briefly distinguish native replacement packages from private app libraries/engines and launch preferences. Explain that font files and website styles are not rewritten. Keep existing accounts/data and unsupported coverage truthful. Building alone does not install packages. |

Every screenshot-generation clause maps to B-IMG1 through B-IMG6: profile/activation to B-IMG1; requested conditions and complete role collection to B-IMG2; pixel preservation, order and provenance to B-IMG3; retained evidence to B-IMG4; public hygiene and output storage to B-IMG5; optical and deployment scope to B-IMG6. The added introductory summary maps to B-IMG7. Frozen formulas and existing support recipes are opaque. Native builds, activation and release publication are deferred to their named subtasks. Test policy, licenses and attribution are non-boundary obligations.

Run python3 -B tests/kde_v2_comparison_test.py --record V2_FREETYPE_RECORD --observed-record OBSERVED_FREETYPE_RECORD --qt-bundle MATCHING_QT_BUNDLE. Output is fixed at docs/images/kde-v2. The capture recipe uses the matching Ubuntu Qt 6.10.2 provider. Its qualification receipt must bind the actual supplied libraries and current renderer/test sources. Prose-only changes do not invalidate an unchanged renderer proof. This one command owns S-IMG1 through S-IMG5 and preserves private command/artifact bindings in the ignored result. Supporting checks are git diff --exit-code -- docs/images/kde-selected tests/kde_selected_comparison.cpp tests/kde_selected_comparison_test.py, python3 tests/docs_test.py --self-test and python3 tests/docs_test.py. Review the final PNGs at original size and review README prose for S-IMG6/7. No new executable production behavior is introduced by this capture/documentation subtask, so its deterministic checks and native review apply without a production trace-closure claim.

## SS-18 persistent user preference and launch integration

### Outcome, owners and implementation ceiling

One per-user persistent choice supplies O NORMAL by default or K3 NORMAL to fresh ordinary launches of enabled native Qt/KDE, Firefox, Floorp, Teams and Bitwarden. Preference is separate from activation. Preserve original working profiles and data, native security, exact arguments, application updates and stock escape. Full application restart applies a change; the native desktop uses the next login. The supported model is one personal user and authorized writer, normal local filesystems and ordinary explicit commands, launches, restarts and supported native updates.

Compose the existing session command/hook and package payload, tools/browser.py, tools/chromium_delivery.py, the existing transport producer/input identities and Zypak child-environment patch. The FT/Skia interfaces and formulas are opaque. Existing profile discovery/restoration, provider parsing/installations, app resources/wrappers/modules/fuses, Bitwarden isolation, portal handoff and session ownership are opaque preserved consumers. Native compiler/package proof remains SS-16. Chromium browsers, Telegram and other uncovered engines remain deferred. Add no GUI, service, watcher, engine manager, new cache, per-app preference copy, version gate, daily qualification, automatic restart, forced termination or protected Bitwarden reads.

Extend the existing packaging/session/fontreal-session command with profile getter and profile o|k3 setter. Store the exact token plus newline in $XDG_CONFIG_HOME/fontreal/profile, with HOME/.config fallback and umask 077. Unsupported values or extra arguments must not mutate state. From the checkout use sh packaging/session/fontreal-session profile k3; the installed command is the same payload. Missing preference means o. Safely avoid propagating externally malformed tokens without a new recovery policy.

Add rendering_profile() to tools/browser.py and reuse the existing browser import seam in chromium_delivery.py. The persisted current choice overrides stale inherited FONTREAL_PROFILE. Native startup clears that variable with other inactive values and exports the choice only behind the existing enabled-marker/exact-runtime gate. Status distinguishes configured next-login choice from inherited current choice and does not claim that either proves V2 loaded.

Browser run clears inherited profile with controlled FT variables, then injects the configured choice only in the existing enabled/compatible-library branch. Preserve saved library, scope, arguments and unrelated loader entries. Extend the existing process-environment expectation for restart status, without new introspection or a version qualification. Configuration does not upgrade an older saved library.

Only selected Flatpak routes add --env=FONTREAL_PROFILE=CHOICE with existing view/FD options. Preserve full selector parsing, native argv, current resources, cache identity, canonical read-only O_PATH/O_NOFOLLOW directory-FD validation and stock passthrough. Zypak forwards exact valid parent o/k3 into its explicit child environment, replacing a stale child-map value. Preserve direct absent/unsupported legacy behavior, aliases, original flags, trace forwarding and portal FD serialization. The changed transport patch enters existing source/transport/view identity once; a preference-only change does not rebuild an engine or view.

Explicit reviewed enable/re-enable validates the entire ownership set and rebinds all surviving hooks to the candidate controller. Preserve both saved engine identities, independent enabled states and truthful tool identity metadata. Ordinary launch/status never migrate hooks. Complete selected-V1 bundles retain recorded prepare/install compatibility; raw/Qt-only remain ineligible. A configured choice alone is not an applied-V2 claim. Later reviewed deployment uses the new records and both explicit re-enables.

### Source clauses and boundary inventory

The same independent activation challenger completed both phases. Accept its one proof correction: the old direct comparison argv contains options the real selector rejects. Use the private native Flatpak installation/override path described below, not direct view substitution. No contract gap remains.

| Clause | Authoritative source and requirement | Disposition |
| --- | --- | --- |
| CL1 | User accepts one persistent O-default/K3 choice. | mapped B-ACT1 |
| CL2 | Frozen SS-14/17 exact startup o/k3 dispatch; unsupported direct tokens retain V1. | opaque |
| CL3 | Existing session/browser/Flatpak configuration roots follow active XDG_CONFIG_HOME or HOME fallback. | mapped B-ACT1 |
| CL4 | Existing native/browser activation and executable scope remain separate authority. | mapped B-ACT2 |
| CL5 | README and integration guides require a full ordinary restart. | mapped B-ACT3 |
| CL6 | Existing browser status distinguishes a parent needing restart. | mapped B-ACT3 |
| CL7 | Native guide/session command separate next-login and current inherited values. | mapped B-ACT4 |
| CL8 | Existing native startup clears inactive values and requires enabled marker plus exact runtime trio. | mapped B-ACT4 |
| CL9 | system_install and native guide require complete source/artifact identity and preserve recorded selected-V1 compatibility. | mapped B-ACT5 |
| CL10 | Session NOTICE and activation owner retain notices and corresponding source. | mapped B-ACT5 |
| CL11 | Existing complete transaction and rollback contract in system_install/native guide. | opaque |
| CL12 | Actual native V2 generation and package qualification. | deferred SS-16 |
| CL13 | Browser run/written command/GIO actions preserve library, scope, argv and loader entries. | mapped B-ACT6 |
| CL14 | Browser enable/disable and guide preserve working profiles, snapshots, accounts and unrelated preferences. | mapped B-ACT7 |
| CL15 | Browser compatibility gate preserves diagnostic/native fallback for missing or changed artifacts. | mapped B-ACT7 |
| CL16 | Shared Flatpak hooks and guide cover commands, app-ID commands, desktop and eligible native autostart. | mapped B-ACT8 |
| CL17 | Real selector retains complete native argv on unknown, conflicting or disabled selection. | mapped B-ACT9 |
| CL18 | Existing view_options/run/Zypak patch own actual selected FD and child startup. | mapped B-ACT10 |
| CL19 | Existing Zypak aliases, original flags, trace and portal serialization remain valid. | mapped B-ACT10 |
| CL20 | Existing transport producer owns changed input identity; preference alone is not a view/engine input. | mapped B-ACT11 |
| CL21 | FR-016 and Chromium guide preserve current resources and cached reopening with the saved coherent engine. | mapped B-ACT11 |
| CL22 | CONTRIBUTING.md requires tests for Fontreal changes, not ordinary app releases/deployment. | mapped B-ACT11 |
| CL23 | Chromium/Bitwarden guides preserve data, identity, wrappers, fuses, isolation and native startup eligibility. | mapped B-ACT12 |
| CL24 | Absolute native Flatpak and disabled routes remain stock with original data. | mapped B-ACT13 |
| CL25 | Shared registry validates all hooks, neither/either/both states and independent reversal. | mapped B-ACT14 |
| CL26 | Explicit setup may rebind previous-controller hooks; ordinary run/status cannot migrate them. | mapped B-ACT14 |
| CL27 | App scenarios and Chromium guide exclude generic Chromium browsers, Telegram and other unreached engines. | deferred |
| CL28 | User scope and this card exclude new UI/service/cache/runtime policies. | non-boundary |

| Boundary | Invariant and minimal contrast | Scenario and terminal oracle |
| --- | --- | --- |
| B-ACT1 | One choice, correct root and O default versus absent/opposite/inactive-root values. | S1/2/5/7: exact persisted/read/forwarded token; invalid CLI leaves full state unchanged. |
| B-ACT2 | Preference is not activation or wider scope. | S1/3/5/8: same choice with enabled eligible versus disabled/unmatched route; existing gate retains authority. |
| B-ACT3 | Startup choice and truthful restart status. | S4/6: configured k3 with old o parent is pending; fresh matching parent satisfies existing observations without an applied-V2 assertion. |
| B-ACT4 | Native enabled/runtime/next-login gate. | S3/4: matching enabled trio versus disabled and each independent runtime mismatch; fresh child exports exact choice or clears stale values. |
| B-ACT5 | Complete source-bound generation/payload/notices. | S3: actual extracted payload works; selected-V1 remains compatible, Qt-only/raw reject, no false V2 claim. |
| B-ACT6 | Both browsers' ordinary routes preserve launch semantics. | S5: stored k3/inherited o and converse reach exact native exec with saved library, scope, argv and loader entries. |
| B-ACT7 | Browser original data/restoration/native fallback. | S5/6: enable, restart, disable and missing-artifact paths preserve original profile/index/snapshot and unrelated bytes. |
| B-ACT8 | Every covered Flatpak hook reaches the preference-aware owner. | S7/9/11: both targets' command/app-ID/desktop/shared/eligible-autostart routes select the right choice. |
| B-ACT9 | Complete selector/argument semantics. | S8: valid prefix versus later conflict/unrelated/disabled route; native passthrough injects no profile/view query/FD. |
| B-ACT10 | Real child receives the choice through the preserved chain. | S9: actual generated hook through Flatpak/Zypak/portal supplies O/K3 child witnesses and valid FD/trace/flags; no main-env-only proof. |
| B-ACT11 | Transport identity, current resources, cache reuse and no daily qualification. | S7/10: changed transport identity versus preference-only same view; A/cached-A/current-B and nondefault installation preserve current resources and saved engine. |
| B-ACT12 | Original data, security and native startup. | S9/11: same original data owner/marker, wrappers/modules/fuses/isolation/startup facts across selected and stock stages; no daily debug/data overrides. |
| B-ACT13 | Absolute stock escape and disabled routes. | S8/11: same stored k3 with selected, absolute native and disabled launch; native deployment/original data, no inserted profile/view. |
| B-ACT14 | Complete ownership, explicit rebinding and independent reversal. | S12: neither/single/both/legacy/old-controller states, all surviving hooks and both disable orders; foreign last hook refuses without any mutation. |

### Runnable scenarios

C1 is python3 -B tests/profile_activation_test.py. C2 is python3 -B tests/system_install_test.py. C3/C4/C5 are python3 -B tests/browser_delivery_test.py --case desktop/process/lifecycle respectively. C6 is python3 -B tests/chromium_launch_test.py. C7 is python3 -B tests/chromium_delivery_test.py --target TARGET --case actual-app --build-record TARGET_ENGINE_JSON, separately for teams and bitwarden. C8 uses the same entry with --case lifecycle for each target. Replace placeholders with actual records in private evidence. Run both CONTRIBUTING.md documentation commands after final substantive prose.

| Scenario | Discriminator and contrast | Complete path, required result and check |
| --- | --- | --- |
| S1 | Absent, k3, o, uppercase-invalid and extra arguments, with independent seeded enable states. | Real command to file and fresh getter: exact default/persistence and unchanged integration state; C1. |
| S2 | Custom-root k3 versus inactive HOME-root o, then unset XDG_CONFIG_HOME. | Each distinct production reader/launch reaches exact active-root value while inactive file stays unchanged; C1/C3/C6 keep separate per-path observations. |
| S3 | Complete enabled matching generation versus disabled, each independent runtime mismatch, raw/Qt-only, retained selected-V1. | Real prepare/verify, package extraction, payload command/hook and fresh child: exact activation/profile or cleared stale values plus full manifests/source/notices; C2. Only external dpkg-query is a seam; V2 generation binds SS-16. |
| S4 | Current enabled inherited o versus configured next-login k3. | Real writer/status then actual startup hook/fresh child/status: separate truthful current/configured facts, no parent/marker mutation or loaded-renderer claim; C1. |
| S5 | Persisted choice opposite inherited choice for both browsers and every route. | Enable, actual written command/GIO main/every action, shared reader and native exec seam: exact env/argv/library/scope/loader plus preserved profile/index/snapshot bytes; C3. |
| S6 | Existing observed o parent versus normal fresh k3 parent under same stored choice. | Set, status, full normal quit/reopen, status, closed disable/restoration and restored native launch; retain missing-artifact fallback. C4/C5 each prove their own path and original data continuity. |
| S7 | o then k3 through unchanged hooks, deployment and engine. | Both targets' commands/app-ID/GIO/shared routes through selector/current_view/FD/native exec: exact choice, same cached view and ownership, no build/test/qualification; C6. |
| S8 | Supported selectors and payload with spaces/option-like arguments versus valid prefix followed by conflict, split unsupported option, unrelated or disabled target. | Actual full written-adapter parser to selected or native exec: whole ordered argv, native installation and no injected profile/query/FD on passthrough; C6. |
| S9 | Actual O/K3 child startup/output witness versus host/main-env-only observation and direct absent/unsupported transport. | Real preference command/generated hook/selector/view-FD/native Flatpak/rebuilt Zypak/portal child to opaque adapter witness. Prove pre-start private-data value, actual selection/FD/data owner and per-child differing profile witness; C7 both targets. |
| S10 | Changed transport input versus preference-only launch; A/cached-A/current-B and nondefault installation. | Actual transport producer/assembler/setup/written hook/current_view/native handoff: correct transport identity, same preference-only view, current resources and saved engine without daily qualification. C7 binds real rebuilt transport; C6 independently proves resource/cache routes. |
| S11 | Original working data fixed while selected o/k3 versus absolute/native/post-disable stock. | Normal quit, enable, ordinary reopening and eligible autostart, absolute escape, disable and stock reopening: original data/marker/security/startup and other target remain correct; C8 both targets. |
| S12 | Neither/each/both/legacy/previous-controller ownership, first/final disable in both orders, valid hook prefix plus foreign last hook. | Choice alone changes no ownership; explicit setup validates/rebinds all nine hooks, launches every survivor, disables first, launches remaining and disables last. Preserve saved target/controller identities and truthful metadata; foreign refusal changes nothing; C6. |

S9 uses a private native Flatpak user installation selected with FLATPAK_USER_DIR and exact actual app/runtime identities. Before intercepted launch, its own native override configures required filesystem access and Teams E2E_USER_DATA_DIR or Bitwarden BITWARDEN_APPDATA_DIR plus observation environment. Absolute native printenv proves the intended early private-data value. Then invoke the actual generated hook with supported ordinary arguments and --user where applicable. Assert actual selection, selected view/inherited directory FD, actual private data and child-specific profile witness. Preserve host override hashes, startup state and working instances. Remove the private override with native CLI in finally. Reuse an exact cached fixture or prepare it with existing standard native installation/bundle mechanics. Do not rewrite ASAR, original data, production selectors or engines; do not replace the hook with direct view_options or use rejected comparison-only options in intercepted argv. Preserve Bitwarden's existing no-protected-reads/no-RunAsNode constraints.

Each scenario's complete production path executes in its one named check; opaque source/artifact proof is reusable only for exact unchanged bindings. New launch hops cannot borrow another path's terminal observation. Keep exact commands, exit/results and per-boundary evidence in the current ignored task result. Finalize the native/Mozilla/Chromium/app-scenario guides and README before fresh boundary trace and native review. No new numerical or per-app-release qualification is required.
