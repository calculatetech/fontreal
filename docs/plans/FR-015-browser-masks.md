# Firefox working-profile integration

## Working-profile delivery (FR-015-B)

Use the approved rendering in the existing working Firefox and Floorp profiles through ordinary commands and desktop launches. Keep account data, bookmarks, history, sessions, and unrelated preferences in place. Provide reversible enable, disable, and status commands. The disposable comparison described below remains a diagnostic tool.

Prior plan reconciliation: FR-015-A is the immutable accepted mask checkpoint `a3128b87a7ec09b319a5a3c8226db6cc99ebdbb4`. The user approved its samples and explicitly rejected separate browser data. The unfinished requirement to keep FR-015 active until full Mozilla composition is superseded. Complete working-profile activation with the approved sRGB preblend. Do not reopen rendering selection or claim actual-background linear blending. The unimplemented separate-profile proposal is rejected.

FR-015-B has base `9acdba8a24192e3a7746891f345b190d4bd623b3` on `feature/gtk-rendering`, with one writable worktree and no pending Plan capture. The diagnostic constraints below still govern FR-015-A. The user overrides their normal-profile preservation rule only for necessary rendering preferences and ordinary launch integration. Their account-data, Qt, sandbox, and no-migration constraints remain.

### Product boundary and smallest implementation

One user and one writer use normal local filesystems. Retain the exact browser and FreeType versions below. Existing working data stays in its native location. Build and verification data use configured build/result storage. Small activation records and launch hooks use normal per-user directories.

Add `tools/browser.py` with `enable`, `disable`, `status`, and `run`, each taking `firefox` or `floorp`. Reuse the verified release builder. Discover a unique ordinary Install-section default and require any active parent profile to agree. Ignore misleading legacy profile-level defaults. Reject missing, conflicting, or ambiguous targets before writes. Do not expose an arbitrary activation profile override or create a browser profile.

Append a marked `user.js` block for exactly four rendering preferences: whole-pixel positioning, disabled subpixel antialiasing, gamma `0`, and enhanced contrast `0`. Save the original selected `prefs.js` lines or their absence once. Repeated enable retains that baseline. Preserve all bytes outside the owned block.

Install per-user command wrappers and desktop copies under the existing desktop IDs. Preserve every native argument and desktop action. Leave XDG browser directories, scale, startup, font family, remoting identity, and normal Fontconfig unchanged. Firefox's packaged `firefox-bin` is distinct from its small launcher; scope treatment to the actual browser executable.

Add optional `FONTREAL_FT_EXECUTABLE` eligibility to the FreeType patch. With no selector, preserve the approved experiment. With a selector, compare the kernel's immutable execution name against exact colon-separated browser launch paths. Include the installed command, its resolved launcher, and actual browser executable. Use glibc `getauxval(AT_EXECFN)`, which reads startup data without filesystem access inside the browser sandbox. An unrelated executable inheriting the environment must use the normal mask path. Do not change mask math or cache mutable process decisions.

Enable can safely append `user.js` while the browser runs, but activation requires a full normal restart. Status distinguishes configured launches from a treated running parent. Disable requires a closed profile before writing preferences. Remove only the owned block, restore only the original selected `prefs.js` lines, preserve unrelated changes, and remove unchanged owned hooks. Never delete browser data.

Replace preference files atomically and retain their permissions and unrelated bytes. A parent remains live when a package update unlinks its old executable. Interpret Linux's deleted-executable suffix when identifying that parent so disable still requires its normal exit. The [Linux process-executable contract](https://man7.org/linux/man-pages/man5/proc_pid_exe.5.html) defines this suffix. The [auxiliary-vector contract](https://man7.org/linux/man-pages/man3/getauxval.3.html) defines the immutable execution name used by the raster selector.

Ordinary launches do not build or download. Verify the recorded browser version, installed FreeType revision, and library identity. After an incompatible update, warn and launch the installed browser without the private override. Retained rendering preferences remain until disable or rebuild. This fallback does not restore every original preference.

| Owner | Classification | Required relationship |
| --- | --- | --- |
| Working-profile activation, preferences, wrappers, desktop entries | composes | Apply and reverse only owned rendering changes |
| Optional FreeType process selector | composes | Contain treatment across inherited child environments |
| Existing builder and approved rendering algorithm | opaque | Preserve provenance, ABI, features, notices, and accepted pixels |
| Mozilla profile selection, remoting, storage, and composition | opaque | Retain native behavior and measure actual startup |
| Account data, unrelated preferences, host packages, accepted Qt | opaque | Preserve their existing owners |
| Full Mozilla blending, toolbar-font equality, other engines, Debian browser certification | deferred | Require separate evidence before broader claims |

The behavior floor is reversible treatment of ordinary working data. The ceiling excludes profile copying, alternate data, forced termination, forced profile arguments, changed remoting identity, global loader changes, system-library installation, sandbox relaxation, new dependencies, and new rendering algorithms. Faults, concurrent writers, hostile changes, and recovery do not add requirements.

### Source-clause inventory

| Clause and authority | Disposition | Boundary |
| --- | --- | --- |
| Approved samples and existing working profile, latest user instructions | mapped | B10 |
| Preserve account data, sessions, unrelated preferences, scale, and startup behavior | mapped | B10, B12 |
| Actual Install default differs from legacy defaults, installed profile metadata | mapped | B10 |
| Preserve ordinary commands and every desktop action, installed desktop entries | mapped | B11 |
| Remoting precedes new startup, Mozilla `nsAppRunner.cpp` | mapped | B11 |
| Retain first restoration baseline across repeated enable and actual persistence | mapped | B12 |
| Live preference edits are overwritten at exit, Mozilla `Preferences.cpp` | mapped | B12 |
| Preserve accepted Qt and external helper output | mapped | B13 |
| Exact matching build and verified artifacts, existing builder contract | mapped | B14 |
| Keep browser use available after an incompatible update without unsafe override | mapped | B14 |
| Generated build and verification data use configured storage | mapped | B15 |
| Portable, accurate public instructions and approval status | mapped | B16 |
| Preserve all diagnostic modes, independent masks, styles, and scales | mapped | B17 |
| Approved eligibility, mask algorithm, slot ordering, single mild ramp | opaque | FR-015-A |
| Full composition, toolbar-font equality, other engines | deferred | Separate scope |
| Incremental commit and branch push | non-boundary | Delivery |

### Boundary inventory and Scenario Proof

The named executable check is `python3 tests/browser_delivery_test.py`, except D9. Its profiles are synthetic existing working profiles, not copies of accounts. Controlled inputs can replace only opaque OS-home, process-inventory, installed-index, version, and native-executable observations. Production preference edits, wrappers, desktop parsing, remoting, and rendering remain real.

| Boundary | Discriminator and minimal contrast | Production path and terminal oracle | Scenarios |
| --- | --- | --- | --- |
| B10 | Install default versus misleading legacy references; owned keys versus adjacent settings | Enable discovery → verified build → exact working-profile edits → actual startup; same profile and approved settings, unrelated data unchanged | D1, D2 |
| B11 | Cold startup versus URL remoting; each native desktop action | Command/GIO action → wrapper → native browser; intact arguments, original profile, pending status before restart, candidate mapping/output after restart | D2, D3 |
| B12 | Original absence versus explicit value; repeated enable after actual persistence | Enable → treated session → normal exit → repeat enable → disable → stock startup; original rendering state and unrelated data retained | D4 |
| B13 | Browser executable versus unrelated inherited-environment helper | Wrapper → FreeType process gate → public raster/Qt draw; approved browser masks and unchanged eligible/CFF helper pixels | D5 |
| B14 | Matching version/artifact versus later incompatible revision | Enable or wrapper → compatibility gate → native executable; unsafe enable rejects before writes, updated browser launches without override | D6 |
| B15 | Generated verification data versus existing browser data | Builder/check → resolved output roots; generated files stay on configured storage, working data is neither copied nor moved | D7 |
| B16 | Portable working-profile instructions versus stale or excessive claims | Documentation checks and source comparison; accurate commands, restart, reversal, versions, and compositor limits | D8 |
| B17 | Existing diagnostic modes and native raster restrictions | Existing full comparison → independent masks and actual windows → normal cleanup | D9 |

| Scenario | Complete sequence and required oracle |
| --- | --- |
| D1 | Duplicate legacy references precede a different Install target. Real enable selects only the ordinary profile for both browsers. Missing/conflicting targets reject before writes. Require unchanged unused profiles and indexes, with no new profile. |
| D2 | Start the ordinary stock parent. Enable, remote a URL through the wrapper, and observe the same stock parent with restart pending. Quit normally and cold-launch through the wrapper. Require the original profile, actual candidate mapping, effective settings, and independent white-background pixels. |
| D3 | Run both command wrappers and every GIO desktop action through an opaque recording native executable. Compare all original arguments, including a URL with spaces and shell characters. Require results for the entire declared action set. |
| D4 | Cover absent/explicit original keys and absent/present `user.js`. After an actual treated session persists preferences, repeat enable, add an unrelated `user.js` line, disable, and start stock. Require original key values/absence, retained cookies/storage and unrelated settings, same profile, and stock mapping. Live disable rejects before writes. Repeat disable is a no-op. |
| D5 | Compare public FreeType masks with process scope absent, matching, and mismatching. Browser output matches the independent approved reference. In the same native lifecycle, launch a real Qt helper from the stock parent and then from the wrapper-started treated parent through Mozilla's native process interface. Require the actual inherited loader/FreeType environment, identical eligible/CFF masks and images, and unchanged Fontconfig identity. Retain the unscoped control that exposes double treatment. |
| D6 | Change only the opaque observed browser revision. Unsafe enable rejects before writes. A later wrapper launch reaches the installed executable without private loader/FreeType injection, with a warning and unchanged profile data. |
| D7 | Inspect actual child identity and resolved generated destinations. Include the modern Firefox index in protected checks. Caller environment, Qt activation, installed libraries, unused profiles, and profile indexes remain unchanged. |
| D8 | Run `python3 tests/docs_test.py --self-test`, `python3 tests/docs_test.py`, and focused command/link comparison. Keep machine-specific references out of public instructions. |
| D9 | Run `python3 tests/browser_delivery_test.py --case diagnostic`. It installs real normal-launch hooks in test-owned user directories and invokes `python3 tests/browser_masks_test.py --case all` with those hooks first on PATH and an inherited browser process selector. Require every original component/window result and disposable cleanup. The diagnostic launcher selects the installed native binary and clears the inherited selector, so ordinary activation cannot override its explicit modes. Run scratch-file-sharing checks sequentially. |

Include both browsers, every action, and repeated early values followed by a changed storage marker. Missing targets reject rather than create profiles. No grouping limit or partial result can establish success.

### Implementation and decisions

FR-015-B owns the activation tool, small FreeType eligibility gate, focused test support, and authoritative documentation as one coherent delivery. It depends on the accepted FR-015-A renderer. Complete the named checks, substantive documentation, fresh read-only trace closure, and native correctness review from the stated base before its local commit. Keep operational results in the ignored task record and carry the existing branch-push authorization forward.

- Use working data because the user explicitly rejects separate data.
- Omit arbitrary profile overrides because they can disagree with ordinary Mozilla startup.
- Leave normal Fontconfig unchanged because inherited forced configuration can alter external Qt helpers.
- Scope only the optional FreeType treatment by the actual browser executable.
- Restore persisted preferences while the browser is closed because Mozilla writes them on exit.
- Keep the approved preblend limitation explicit without reopening visual selection.
- The algorithm is fixed. Research is limited to official startup, preference, desktop-entry, and process contracts.

## Observable outcome

Open the installed Firefox and Floorp in separate disposable profiles with a private FreeType library. Compare their existing full/auto/grayscale controls with automatic monochrome hinting, grayscale masks, and the accepted mild contrast ramp. Regular Noto Sans at 15px on white is the main problem case. Retain regular, bold, italic, and bold italic on light and dark backgrounds as controls.

This is a mask experiment. Browser layout, glyph placement, and final composition remain Mozilla owners and must be measured separately. The encoded and Mozilla sRGB-preblend choices must keep their actual names. Neither establishes a complete background-aware linear-blending implementation.

## Context and prior plan reconciliation

The user accepts the current Qt result and prioritizes Firefox-based browsers, followed by Electron and Flatpak applications such as Teams for Linux. Existing native-control comparisons favor full/auto hints, grayscale, and whole-pixel positioning, but regular remains blurry and the result suffers on white. No existing Qt implementation decision changes.

The source and native-control evidence is described in [the rendering investigation](../research/non-qt-rendering.md). There is no earlier Firefox implementation plan or pending Plan capture. Other completed engine plans remain outside this prototype.

Git base: `ab206c61228c1f1106284ec904062533a3d55687`. Task branch: `feature/gtk-rendering`, one writable worktree. Local `main` equals `origin/main` at `c481f7980905f92e10c361cc42e72ee7a326e6a2`.

## Product boundary and operating model

One user and one writer use normal local filesystems. All generated sources, builds, profiles, and captures belong under the configured build and result directories. The initial runtime target is Ubuntu 26.04 FreeType `2.14.2+dfsg-1ubuntu0.2`, Firefox 160, and Floorp 12.21.1/Gecko 159.0.1. Preserve the distro's security patches and dynamic HarfBuzz configuration. Debian 13 remains a later delivery target; this prototype must not claim a Debian build that has not been checked.

| Owner | Classification | Required relationship |
| --- | --- | --- |
| Private FreeType load/render code and glyph-slot state | composes | Produce the experimental masks only when explicitly enabled |
| Private build and browser launch tools | composes | Select verified matching sources, libraries, and disposable profiles |
| Local browser fixture, capture, and analysis | composes | Reach actual browser output and distinguish mask, placement, and blending |
| Mozilla shaping, layout, caches, outline translation, and composition | opaque | Keep their behavior; measure results without replacing their decisions |
| Noneligible fonts, normal profiles, host packages, accepted Qt | opaque | Preserve stock behavior and normal launch resolution |
| Full Mozilla GPU blending, Electron, GTK-wide support, Flatpak delivery | deferred | Require separate implementation evidence before promotion |

The normal-use floor is an opt-in comparison that leaves normal applications untouched and supplies independent results for each declared condition. The ceiling excludes system installation, profile migration, global loader changes, sandbox relaxation, browser rebuilds, new automatic blend heuristics, and universal font/renderer claims. I/O faults, hostile changes, concurrent writers, and interrupted-build recovery do not add product behavior.

## Existing owners and smallest implementation

The authenticated distro source has `FT_Load_Glyph`, `FT_Render_Glyph_Internal`, and `FT_Render_Glyph` in `src/base/ftobjs.c`. `FT_Load_Glyph` retains flags in the slot, can render immediately, or can leave an outline for its caller. WebRender translates that outline before its separate render call. Keep this ordering. Do not eagerly render delayed requests or add a second authoritative glyph-state owner.

Add a separate opt-in environment selector for the private FreeType experiment so it cannot apply the Qt profile twice. Select scalable, non-color TrueType faces. Preserve unscaled, no-recurse, no-hinting, advance-only, and bitmap-metrics-only requests. For eligible raster loads, clear incompatible hint-target/monochrome flags and `FT_LOAD_NO_AUTOHINT`, then request forced automatic monochrome hinting without embedded bitmaps. The opt-in profile overrides the caller's auto-hinter preference. Preserve FreeType's existing face and transform restrictions on the hinter.

For an eligible outline render, use grayscale output and apply the optional mild ramp to the new gray bitmap once. Repeated rendering of an existing bitmap must not apply contrast again. Immediate `FT_LOAD_RENDER` and delayed public render calls must both work. Use existing retained load flags and outline/bitmap state rather than adding persistent slot state.

The private builder produces an unchanged-source control and a patched library with identical features and source identity. Pin and verify the source archives authenticated through the distro index. Record source, patch, configuration, library hashes, ABI identity, and notices. The launcher uses explicit separate profiles and private library paths only in its child environment. It must not change normal browser profiles, installed packages, or persistent Flatpak overrides.

The browser fixture includes the problem regular face, actual bold/italic combinations, a small set of independent size/scale/origin contrasts, CFF/color controls, and ordinary shapes. Keep Mozilla enhanced contrast disabled. Measure gamma-disabled encoded output and gamma-0 Mozilla preblend independently. Actual raw browser glyph evidence is required; the earlier pass-through load trace alone is insufficient. Test-only instrumentation may observe the final private-library bitmap without replacing load, outline translation, render, or composition.

## Authoritative source-clause inventory

The local source packet is the exact Ubuntu FreeType source, exact Firefox source stamp, accepted Qt patch/reference tests, the user requirements above, and the rendering investigation. Direct composing-owner expansions are limited to glyph-slot clearing and the called font/render owners. Each clause below has one disposition.

| Clause | Disposition | Boundary |
| --- | --- | --- |
| Preserve accepted Qt and record font, size, scale, polarity, placement, and blend | mapped | B1 |
| Private profiles/libraries and generated data in configured output directories; preserve normal host state | mapped | B1 |
| Opt-in scalable non-color TrueType eligibility; preserve CFF/color/bitmap-only faces | mapped | B2 |
| Forced auto-hinter, monochrome hint target, no embedded bitmap | mapped | B3 |
| Normal grayscale raster output and optional 32..223 mild ramp | mapped | B3 |
| Independent unmodified-FreeType masks and analytic blend reference | mapped | B3 |
| Immediate and delayed render entry points | mapped | B4 |
| Caller outline translation must occur before delayed rasterization | mapped | B4 |
| Retained slot flags and slot reuse must not leak or double-apply treatment | mapped | B4 |
| Preserve non-raster request classes and FreeType hinter restrictions | mapped | B5 |
| Actual Firefox and Floorp output, not only component or sampled-load results | mapped | B6 |
| Page text and browser controls are separate observations | mapped | B6 |
| Measure device placement separately and preserve later ineligible/ordinary drawing | mapped | B7 |
| Compare encoded and Mozilla preblend against the actual-background linear oracle | mapped | B8 |
| Mozilla enhanced contrast differs from the mild ramp; keep it disabled | mapped | B8 |
| Exact-source paired build, dynamic HarfBuzz, source/modification/license notices | mapped | B9 |
| FreeType warns that mono hints plus grayscale can look unattractive | non-boundary | Human evaluation remains necessary |
| Full Mozilla background-aware GPU blend implementation | deferred | Separate engine work |
| Electron, Teams, GTK-wide support, Flatpak, and Debian delivery certification | deferred | Separate roadmap owners |

## Boundary inventory and Scenario Proof

| Boundary | Condition and contrast | Entry points and required oracle | Scenarios |
| --- | --- | --- | --- |
| B1 | Private stock/control/candidate launch versus normal launch resolution | Real launcher through process exit; library/profile identity and protected-state fingerprints | S1 |
| B2 | Enabled eligible TrueType versus off, CFF, color, bitmap-only | Public FreeType load/render; stock-equivalent bytes, format, bearings, and advances for excluded cases | S2, S3 |
| B3 | Auto-mono grayscale/mild versus normal-hinted gray and binary output | Public FreeType load/render; exact independent masks, gray intermediate pixels, and one mild ramp | S2, S4 |
| B4 | Immediate versus delayed rendering, translated outline, repeat render, then next load | One causal slot sequence; independent translated mask, stable repeat, independent next glyph | S4, S5 |
| B5 | Raster request versus preserved non-raster flag classes | Public load entry; stock-equivalent non-raster state and render suppression | S6 |
| B6 | Candidate versus native controls in each installed browser; page versus chrome | Real launcher, actual private raster and final captures; separate results for page and headed controls | S7, S8 |
| B7 | Integral versus fractional origin with other factors fixed | Actual page, raster, and final capture; independently located origin and unchanged neighbor regions | S9 |
| B8 | Same foreground over complementary versus other background; each gamma mode separately | Actual browser captures; independent encoded/actual-background-linear predictions and residual errors | S10 |
| B9 | Unmodified and patched exact-source builds with same features | Real build entry; hashes, configuration, public ABI, dependencies, license and modification acknowledgement | S11 |

| Scenario | Discriminator and minimal contrast | Complete production path and terminal oracle | Planned command |
| --- | --- | --- | --- |
| S1 | Launch mode/profile identity; same executable and local page | Launcher → loader/profile selection → actual browser output → exit; private identity and unchanged protected state | `python3 tests/browser_masks_test.py --case all` |
| S2 | Opt-in then mild state independently; glyph with different mono/normal gray masks; an otherwise identical `NO_AUTOHINT` request must still select the forced-auto reference | Load → retained outline → render → bitmap; independent exact mask, mode, bearings, metrics | `python3 tests/browser_masks_test.py --case freetype` |
| S3 | Actual face format/color/scalability; each exclusion against its own stock result | Load → original format owner → render/result; bytes, format, metrics unchanged | `python3 tests/browser_masks_test.py --case freetype` |
| S4 | Only immediate-render flag changes | Public load with `FT_LOAD_RENDER` → internal render → bitmap; gray result equals explicit independent delayed reference | `python3 tests/browser_masks_test.py --case freetype` |
| S5 | Outline translation, second render, then next glyph in one slot | Load → caller translate → render → repeat render → next load/render; translated reference, stable repeat, fresh next-glyph reference | `python3 tests/browser_masks_test.py --case freetype` |
| S6 | Only load-purpose flags change | Public load → dependency normalization/hinter gate → returned slot; preserved requests equal stock | `python3 tests/browser_masks_test.py --case freetype` |
| S7 | Candidate versus native-control library with scene fixed, in each browser | Launcher → actual font/load → browser outline processing → final private render → browser composition → page capture; raw mask oracle plus separate final-pixel result | `python3 tests/browser_masks_test.py --case all` |
| S8 | Known browser-control label, distinct from page text | Headed disposable launch → actual chrome text/raster → native window capture; control-specific result or explicit unresolved coverage | `python3 tests/browser_masks_test.py --case all` |
| S9 | Minimal integral/fractional origin pair; fixed geometric markers | Page layout → browser placement → candidate raster → final capture; measured origin/mask and stock-equivalent later CFF/color/solid regions | `python3 tests/browser_masks_test.py --case all` |
| S10 | Same foreground on two backgrounds; gamma mode changed in separate run | Actual page → private raw mask → optional Mozilla preblend → composition → capture; encoded and actual-background-linear errors reported separately | `python3 tests/browser_masks_test.py --case all` |
| S11 | Patch presence only, source/configuration fixed | Real builder → configure → compile/link → private artifacts; hashes, dynamic HarfBuzz, exports, identity, notices | `python3 tests/browser_masks_test.py --case build` |

Use a bounded independent condition set: Noto Sans regular 15px light is the baseline; change true style, dark polarity, one nearby effective size, and 125% scale independently. Include a no-ink space, repeated successful early rows followed by a changed style/background, and every declared browser/condition in the report. An empty capture set or missing raw-raster evidence cannot pass. Do not infer synthetic-italic equivalence from an actual italic face. No retry/deadline/recovery lifecycle is introduced; each draw closes at its bitmap or captured image, while repeated slot and browser repaint state must be exercised explicitly.

The browser scenarios share one actual-window capture run through `--case all`. Separate stock controls use each candidate's gamma mode. Gamma affects excluded fonts too, so an encoded stock control cannot isolate the mask change in a preblend candidate. This fixes the test contrast without changing B1..B9.

## Implementation and proof boundary

One atomic subtask, FR-015-A, owns the private mask experiment, builder/launcher, local fixture, independent probe, browser checks, documentation, and notices. It depends on the accepted Qt reference and authenticated unmodified FreeType baseline. Allowed production changes are the FreeType patch and focused private build/launch tools; accepted Qt code and system activation stay unchanged.

Complete the named checks and human-viewable comparisons before full native correctness review from the task base. Run a fresh read-only boundary trace closure before native review. Keep operational results in the ignored task record. A clean review permits a coherent progress commit and the previously authorized branch push. The working-profile delivery above replaces the former full-composition completion gate.

## Decision Log

- Use a private FreeType experiment before a full Mozilla rebuild because the installed `libxul` dynamically links system FreeType. Actual child mappings and final-raster evidence must confirm that opportunity.
- Preserve source-level security patches and distro features in both comparison builds; no host package replacement is part of the experiment.
- Preserve unhinted/design-metric requests and retain delayed outlines. A universal FreeType override would change owners beyond the intended raster experiment.
- Keep encoded and Mozilla preblend as explicit diagnostic choices. The user's white-background failure does not authorize a new background-guessing heuristic.
- Regular weight on white is the principal visual test. Clearer bold and italic results cannot conceal a failing regular row.
- Clear `NO_AUTOHINT` only for eligible opt-in raster loads. The two-phase challenge identified its precedence over `FORCE_AUTOHINT`; the explicit forced-auto requirement defines the result. A paired request must distinguish this preference from the preserved non-raster and face/transform restrictions.
- Prior-art algorithm selection is not reopened: the user already selected the rendering mechanism. Research checks exact framework/source behavior and its integration boundaries.
