# Chromium and Flatpak rendering


## Outcome and current boundary


The user requests Chromium-based browser support and Flatpak coverage, especially Teams, Bitwarden and Telegram. Keep the selected generic method and existing working data. The [roadmap](../roadmap.md) owns task state. The [browser guide](../experiments/browser-masks.md) owns the completed Mozilla integration.

Git base: `main` at `e8303f596998d6231b2d5bbd8c8b273d541c9b01`. Use the single implementation branch `feature/chromium-flatpak` in the existing checkout. All source downloads, toolchains, caches, builds, temporary profiles and results belong below the configured storage-backed `build` and `results` roots. Do not add Docker build layers to an unrelated Docker data root.

The first checkpoint, C1, identifies the exact four targets and establishes a stock local fixture in the exact Teams Electron engine. It adds passive raster observation and compares final pixels with a separate unmodified build. It does not claim selected rendering or daily application support. The selected processor, current Mozilla delivery, ordinary application accounts, authentication services and host KDE installation are opaque at this checkpoint.

Teams is the first engine because its installed package declares Electron 44.9.0 and Chromium 152.0.7977.167. Chromium pins Skia `747cf654ed6f864f4402e7d6eb54a6ede60141e5`. The exact [Chromium FreeType configuration](https://github.com/chromium/chromium/blob/152.0.7977.167/build/config/freetype/freetype.gni) excludes Blink text from its FreeType requirement. Fontations delegates path rasterization to the base Skia scaler. A loaded FreeType library or a PDF result cannot establish page-text coverage.

Keep separate records for Edge, Teams, Bitwarden and Telegram. Edge's installed package revision differs from this Chromium source packet. Bitwarden has its own embedded engine and process-isolation preload before Zypak. Telegram builds static Qt 6.11.2 with desktop-app patches and dynamically links runtime FreeType. These are distinct composing owners. Retain an explicit unknown result where causal engine evidence is missing.

## Prior decisions and owners


The completed FR-018 selection replaces the older monochrome-hint and mild-contrast research preset. Native-normal geometry, the generic selected coverage chain and weighted stems only remain fixed. No new font, character or coordinate exceptions are allowed. The existing processor and immutable references remain unchanged in C1.

`src/fontreal_coverage.cpp` owns coverage processing. It does not own hinting, placement, engine selection or composition. The new engine builder owns exact source identities, upstream build recipes, private artifacts and passive instrumentation. A comparison launcher owns test-only application state and normal sandbox startup. Each installed package retains its own ordinary launcher, data and security chain.

Follow the exact upstream [Electron build workflow](https://www.electronjs.org/docs/latest/development/build-instructions-gn) and its versioned dependency graph. Use matching stock and instrumented builds. Reuse the build tree for an incremental instrumentation rebuild, while retaining the identified stock artifact. Include all instrumentation and build inputs in artifact identity. Keep source notices and upstream licenses with generated artifacts. Do not weaken sandboxing to force a test to run.

Keep the upstream checkout unchanged. For the instrumented compile, give the build process read-only views of private copies of the two affected Skia source directories. Reuse its output tree only after retaining the identified stock distribution. The stock cache is tied to the exact upstream inputs and GN arguments. A changed GN configuration uses a different output tree. An absent or altered retained stock artifact stops reuse of an instrumented output tree. Run one build at a time per private checkout.

This is a fixed rendering integration, not a new rasterization algorithm or protocol. Primary source and upstream build contracts decide the implementation. A new algorithm prior-art search is not required for C1.

## Boundary inventory and Scenario Proof


The Phase 1 source inventory is reconciled here. The generic method clause B2 and later application/delivery paths remain required, but their implementation is deferred until C1 establishes the reached owner. They are not evidence supplied by a stock fixture. General GTK desktop support and native KDE package deployment remain separate roadmap tasks.

| Boundary | Source clause and disposition | Discriminator and minimal contrast | Production path and terminal oracle | Check |
| --- | --- | --- | --- | --- |
| B1 / S1, mapped | Every named target needs its own exact package, engine and rendering-owner evidence | Four application identities, including two that share a runtime but differ in engine or wrapper. Unknown ownership stays unknown | Installed metadata and wrappers → exact source/build identities → four distinct inventory records. Require the exact target set and evidence status for each | `python3 tests/chromium_flatpak_test.py --case owners` |
| B1,B5 / S2, mapped | The exact engine fixture must reach the observed text owner | A real document glyph versus a non-text control and a merely loaded unrelated library | Real exact-Teams-engine launch → renderer → Fontations/base scaler or another observed owner → final window. Passive trace identifies actual fixture glyph work. Stock and instrumented output remain pixel-identical | `python3 tests/chromium_flatpak_test.py --target teams --case stock-fixture` |
| B3 / S2, mapped for C1 | Comparisons preserve ordinary accounts and normal sandboxing | Separate test data versus each existing ordinary data location | Real comparison launcher → native sandbox and test-only data → window capture. Observe renderer sandbox and actual selected data path. Do not launch account-bearing Teams code or change normal hooks/overrides | Same complete `stock-fixture` check |
| B4 / S2, mapped | Generated build and comparison state stays on the configured volume | Resolved configured roots versus default build/cache/profile directories | Actual builder and comparison launcher → identified artifacts, toolchain/cache locations and test state. Assert containment in resolved build/results roots. Normal operating-system IPC sockets retain their native location | Same complete `stock-fixture` check |
| B2 / S3–S4, deferred | Apply the unchanged selected method exactly once to eligible native-normal grayscale masks, preserving excluded color/bitmap drawing and cache/repaint behavior | Disabled/native/selected masks, repeated glyph prefix followed by a distinct glyph and excluded drawing | Requires the reached engine owner from C1 and a new focused implementation card. Independent raw geometry/coverage and selected-mask references precede final-pixel comparison | Define the exact selected-fixture and mixed-glyph checks before C2 implementation |
| B5 / S5, deferred | An engine fixture does not establish actual application text or controls | Fixture output versus each actual application text/control owner | Target-specific package launcher → actual application renderer/compositor → separate final-pixel oracle for each claimed path | Define application checks before C3 implementation |
| B3 / S6, deferred | Daily use keeps existing accounts, data, ordinary launches, package security chains, updates and stock fallback | Existing durable data versus empty comparison data, then activation/use/reversal | Target-specific ordinary launch → original security/data owners → selected application output → stock reversal. Check durable markers before final working-data observation | Define complete delivery checks before any daily-use activation |

Build/provider or source incompatibility stops the comparison with a concrete diagnostic. Missing source or backend evidence blocks a support claim, not read-only inventory. Do not substitute another browser, clone working data for delivery, drop Bitwarden's isolation preload, replace host Qt to claim Telegram coverage, or disable the normal sandbox.

## C1 trace sender identity

The required outcome is causal attribution to the fixture's observed renderer under its normal Linux sandbox. Different PID namespaces can both contain process 1. The trace payload's `getpid()` value must not serve as a globally unique sender identity. This refines the measurement for existing B1, B3 and B5 / S2 without changing their required outcomes.

The fixture launcher and trace reader in `tests/chromium_flatpak_test.py` compose this correction. The compiled trace header, rendering, build artifacts, fixture page, normal sandbox and working application data remain opaque. The existing artifact and cache checks retain B4. Selected processing and daily application delivery remain deferred to C2 and C3.

Use an inherited unnamed `AF_UNIX` datagram socket for stderr. Enable `SO_PASSCRED` on the receiving endpoint before launch. Each message supplies kernel sender credentials. Linux translates that PID into the receiver's namespace. Require that sender PID to equal the observed renderer host PID, then check the payload PID against its `NSpid` tail. Keep renderer ancestry and all existing sandbox checks. Remove only the false requirement that inner PIDs be unique across namespaces. [Linux sender credentials](https://man7.org/linux/man-pages/man7/unix.7.html), [PID namespace translation](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html).

The receiver drains messages during launch, painting, capture and normal quit. Preserve raw stderr plus a minimal credential index below the result root. Assemble trace lines separately for each kernel sender so interleaved writers cannot create one attributed record. Accept final evidence only after the collector drains and closes. Missing credentials, truncated payload or ancillary data, incomplete trace records and collector errors fail the condition. Keep bounded cleanup for test-owned children, sockets and threads on failure. [Python ancillary-message interface](https://docs.python.org/3/library/socket.html#socket.socket.recvmsg).

The smallest change is the existing Python launcher, collection and attribution owner. Use the standard library. Add no renderer hook, engine rebuild, filesystem socket endpoint, external service, generic logging framework, recovery mechanism or sandbox workaround. A one-time `SO_PEERCRED` query is insufficient because it describes connection-time credentials rather than each descendant writer.

The normal sandbox oracle requires seccomp mode 2, `NoNewPrivs=1`, and zero inherited, permitted, effective and ambient capabilities. Record `CapBnd` separately as an execution-time capability ceiling. It is not a granted capability set and need not be zero. This corrects the observer, not the application's security configuration. [Capability sets](https://man7.org/linux/man-pages/man7/capabilities.7.html), [NoNewPrivs](https://docs.kernel.org/userspace-api/no_new_privs.html).

| Scenario | Existing boundary | Discriminator and contrast | Complete path and required oracle | Check |
| --- | --- | --- | --- | --- |
| S2a, sender identity | B1,B3 / S2 | Two real owned child processes have known host PIDs and identical synthetic trace payloads claiming PID 1. Matching payload values from the foreign sender must not satisfy the selected sender's evidence | The same stderr collector receives actual kernel credentials, keeps sender-separated record assembly across interleaved fragments and selects only the intended host PID. Compare credentials with independently known child PIDs. This primitive check does not claim real engine namespace behavior | A focused collector self-check runs inside the existing `--case stock-fixture` command |
| S2b, engine composition | B1,B3,B4,B5 / S2 | Actual renderer work versus an incidental matching record from another process, including a normal inner-PID collision | The unchanged exact engines launch normally, paint the prefix and later glyph, report their renderer and test data, emit passive trace, reach real window capture, quit and finish collection. Kernel credentials must bind every accepted glyph record to that renderer. Preserve all font/palette pairs, stock trace absence, full glyph-owner chains, sandbox, controls, storage containment and stock/instrumented pixel identity | The complete `--target teams --case stock-fixture` check |

The inventory check and every existing C1 requirement remain required. The focused transport check supplements the actual engine test. It cannot replace it or establish application coverage. There is no new public rendering policy or unresolved contract decision.

## C1 capture domains

The required B5 outcome is exact stock/instrumented final-window equality. Electron's `capturePage` copies a render surface into `NativeImage`; `toPNG` and the OS-root screenshot are separate representation owners. The inspected contracts do not promise equal RGB bytes across those domains. Replace the cross-domain equality assumption in `window_pixels` with exact comparisons within each domain. Keep the native PNG and its color metadata unchanged. [Electron capture API](https://www.electronjs.org/docs/latest/api/web-contents#contentscapturepagerect-opts), [NativeImage representations](https://www.electronjs.org/docs/latest/api/native-image).

Only Python window measurement and pair comparison compose this correction. The fixture page, capture API, engine flags, compiled artifacts, passive trace, normal sandbox and working application data remain opaque. Preserve B1 sender/glyph attribution, B3 security/data checks and B4 containment. No image normalization, color conversion, tolerance, replacement pixels, renderer adjustment or additional capture framework is allowed.

Locate the OS content crop with the independent fixture marker and control, using their CSS source colors and DOM geometry in the controlled nested display. Require the unique solid marker, complete control rectangle, valid crop bounds, expected content dimensions and painted prefix and later-g regions. Check native controls and painted regions separately in the native domain, using its observed background and control values. A marker alone or an empty text region must not complete the window observation. Retain the unmodified root image and full content crop.

| Scenario | Existing boundary | Discriminator and contrast | Complete path and required oracle | Check |
| --- | --- | --- | --- | --- |
| S2c, capture domain | B5 / S2 | A valid stock native PNG and its real OS window can encode colors differently. Equal native PNGs must not substitute for equal final windows | The actual ready fixture reaches the existing OS screenshot helper, a validated full content crop and normal quit. Compare the entire stock/instrumented crop RGB arrays exactly. Also retain exact native PNG byte equality within its own representation. Preserve separate control, text-presence, glyph-owner, credential, sandbox, data and containment checks for every condition | The complete `--target teams --case stock-fixture` command. A focused check against retained real capture inputs can support crop extraction but cannot replace the full twelve real-engine executions |

The OS-window comparison is the final display oracle. Native-PNG equality is a second same-domain oracle. Do not infer the precise color-conversion cause or a rendering defect from a cross-domain difference. This corrects the unfinished C1 measurement and does not change the fixed boundary inventory or the selected rendering method.

## Checkpoints


C1 owns the exact target inventory, engine build recipe, passive instrumentation, isolated launcher and stock-fixture proof. Native checkpoint review includes their full interaction and all current documentation. Commit only after its checks and boundary trace pass.

C2 depends on C1. It carries the unchanged selected mask method into the confirmed engine owner and independently proves hinting, placement, eligibility, caches and final encoded composition. Write its focused preflight before implementation.

C3 depends on C2. It qualifies actual Teams text and then the other named engines/packages. Daily-use integration needs its own complete existing-data and stock-reversal proof. Do not mark FR-016 or FR-017 complete from C1 or C2 alone.

## Decision Log


The first implementation follows the exact Teams engine before changing application launchers. This makes the actual raster and compositor observable without using an account-bearing application as a test harness. Keep Bitwarden, Edge and Telegram in the inventory with their own evidence gaps. Preserve their launch chains until the relevant owner is proven.

The generic selected processor remains opaque in C1. This prevents an engine investigation from reopening accepted optical tuning. Later ports must use independent raw inputs from their actual backend and preserve the selected generic processing semantics.
