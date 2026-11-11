# Isolated KDE rendering-path tests

## Outcome and authority


Finish the separate KWin title and Qt Quick tests before a KDE package pilot. Capture real rendered pixels and show comparison samples for human judgment. A measured mismatch is a release gap, not a passing integration result.

The user requests this testing after the [deployment decision](../research/distribution.md). The accepted reference remains automatic monochrome hints with grayscale rasterization, integral origins, mild contrast, and manual blending. Noto Sans UI and Inconsolata Nerd Font Regular at 15px are preferred local conditions. Preserve stock controls and normal desktop configuration.

Base: `50a02b34e53dfe242a9f92d8fa131a2e1bd2c1c7`, main. Branch: `test/kde-rendering-paths`, one writer in the existing checkout. Prior plan reconciliation preserves [FR-002](FR-002-qt-native.md) and [FR-010](FR-010-native-mild.md). This task promotes their deferred KWin and Qt Quick paths into isolated testing. Installation and session activation remain FR-011. No pending Plan records exist in the sole worktree.

## Product boundary and operating model


The new test probe, QML fixture, and test runner compose the task. They launch the existing process selector and installed KWin/Breeze/Qt Quick, capture output, and report comparison evidence. Existing renderer and launchers remain opaque supporting owners. This task does not change their rendering contract. The existing independent native probe remains an oracle reference, not a substitute for the new paths.

Support the installed Ubuntu 26.04 amd64, Qt 6.10.2, Plasma/KWin 6.6.6 environment. Use one local user, normal files, private XDG configuration, and a separate D-Bus session. A nested KWin on an owned Xvfb display keeps the live compositor untouched. Preserve already-open comparisons. Build optional test targets with the installed Qt Quick development files.

The floor is an honest result for each tested path and condition, including a mismatch or an unavailable result with its error. Require actual output and loaded-library identity. Do not infer success from environment variables or FreeType flags. Every launched test child must reach normal completion or owned termination and cleanup.

The ceiling excludes system installation, desktop-session restart, persistent configuration, automatic size policies, new blending algorithms, GTK, Wine, Windows, bundled runtimes, and a general screenshot-analysis product. A rendering correction requires its own explicit scope and preflight. Source inspection and test fixture corrections remain inside this task.

## Smallest implementation


Add an optional `qt-kde-probe` test target. Use a QML fixture with explicit native Text, explicit Qt Text, implicit Text, Breeze Label, and Breeze Button content. Compare individual stem, curve, and diagonal glyphs in isolated cells. Keep fonts, sizes, colors, and positions fixed between selectors. Include light, dark, and nonendpoint colors, cached repaint/recolor, 15px at scale 1, and a fractional-scale condition.

Generate independent automatic-MONO FreeType masks with and without the mild ramp. Compose reference RGB with independent encoded and piecewise-sRGB math. Search only each known glyph cell, with a background border and one-channel rounding tolerance. Record matches to each hypothesis and reject ambiguous fixtures as evidence for selecting a treatment. Preserve the captures and font identities. Layout remains Qt's owner. An unmatched image is reported explicitly rather than relabeled as the preferred result. Contrast origin phases 0 and 0.5 device pixels at fixed font and scale in the diagnostic fixture. Do not infer a snapping result for actual KWin or Plasma unless their measured placement exercises that distinction.

Exercise the GPU renderer and a software-renderer control separately. The latter is diagnostic, not a proposed desktop-wide setting. Record the actual graphics API and selected render types. Test the default and candidate native override where Breeze selects rendering. Include explicit render types to expose components that override the default.

Launch installed KWin on a private D-Bus session and Xvfb display. Give only this KWin the selected Qt libraries and rendering settings. Launch a bounded client with known title text. Set the title font and solid colors in private configuration, disable decorative animation/gradient effects for the pixel fixture, and capture the nested output. Compare title glyphs with independent predictions. Repeat at integral and fractional output scale. Apply and read back the private output scale with `kscreen-doctor`, then check actual buffer dimensions. Keep client pixels separate from title evidence.

Also launch the installed `plasmawindowed` applet host with a controlled test plasmoid using the actual Plasma Components Label. Reuse the glyph fixture inside that real Plasma owner. Identify the host's mapped Qt and rendered component types, then capture its output at integral and fractional scale. This proves the tested applet-host path only. Full plasmashell and D-Bus/systemd session activation remain later pilot gates.

Characterize non-TrueType spillover with an installed CFF face and a color-font control where available. Compare stock, private inactive, and private enabled widget captures. Report any wider transfer-profile effect. Do not claim unchanged noneligible fonts without equal output evidence.

Use a Python runner for the finite condition list, process ownership, private roots, captures, and JSON report. Snapshot normal KDE/KWin configuration and tested font hashes before and after. Use process-owned handles and private services only. Do not act on the user's existing windows. Preserve every requested condition in the final report, including later mismatches after repeated passing cases.

## Boundary inventory and Scenario Proof


| ID | Source clause and disposition | Discriminator and contrast | Terminal oracle and command |
| --- | --- | --- | --- |
| B1 | FR-004 requires separate Qt Quick and actual Plasma output evidence. Mapped. | Native versus explicit Qt/default rendering, same glyph/font/size/color. GPU versus software is a separate path. | Real QML/Breeze diagnostics and installed plasmawindowed/Plasma Components captures, loaded library/API/type evidence, independent masks and both blends. `python3 tests/kde_paths_test.py` (S1). |
| B2 | Effective size, snapped presentation, and manual blend must remain explicit. Mapped. | Integral versus fractional device scale at fixed logical size. Device origin phase 0 versus 0.5 at fixed scale. Linear versus encoded at the same mask. Repaint/recolor without changing the glyph. | Captures classified independently, actual device scale and origin phase recorded, and cache/recolor frames retained. Actual KWin/Plasma snapping is unproven without an exercised fractional origin. Same runner (S2). |
| B3 | FR-004 requires real KWin title output distinct from clients. Mapped. | Installed stock versus enabled private KWin. Integral versus fractional nested output scale. | Composited nested output contains the known title. Title cells match independent hypotheses or are marked unmatched. Actual KWin library/config identity recorded. Same runner (S3). |
| B4 | Shared transfer profile affects fonts outside the tested TrueType path. Mapped as characterization. | Stock/private-inactive/private-enabled for the same CFF and available color face. | Actual widget captures establish equal or changed output, independently of eligible text. Same runner (S4). |
| B5 | Preserve normal desktop configuration, live compositor, and previews. Mapped. | Before tests versus owned process completion and private-state cleanup. | Normal configuration/font hashes and original compositor PID remain equal. Every owned child exits and private roots disappear. Same runner (S5). |
| B6 | Human judgment remains the acceptance criterion and controls remain honest. Mapped. | Actual native-size capture samples versus enlarged inspection views. Matching versus unmatched output labels. | Visible comparison identifies path, font, device size, selector, and measured status. Documented probe viewing command (S6). |

The deployment source's package builds, update ordering, signed repository, licenses, installation, and recovery are deferred FR-011/FR-012 requirements. The completed widget/experiment scenarios are opaque and unchanged. Private progress publication is non-boundary delivery authority. Non-native LCD resolution is excluded. No unknown rendering result becomes an invented implementation policy.

Each capture follows launch, expose, render, repaint/recolor where selected, capture, report, child exit, and cleanup. Cached frames retain their glyph state until the test process exits. The runner owns the finite case collection and reports every member. Empty case collections are not an interface. Repeated glyphs followed by a different curve/diagonal preserve later results. External graphics and layout owners remain real, not mocked.

## Atomic subtask and checks


T1 owns the probe, QML fixture, orchestration, optional CMake target, and test instructions as one proof boundary. Configure and build with `cmake -S . -B build -G Ninja` and `cmake --build build --target qt-kde-probe`. Run `python3 tests/kde_paths_test.py`. Inspect actual captures and provide the native-size human comparison. A diagnostic harness pass does not declare rendering acceptance when it reports unmatched paths.

Finalize the maintained test guide and research conclusions before native review against the base. This testing-only candidate needs no executable production trace closure. If the task adds a production renderer or launcher change, revise this boundary and obtain trace closure before review. A clean complete review permits a coherent commit and the previously authorized progress push. The roadmap owns task state.

## Decision Log


Reuse the installed Qt Quick and KWin capabilities. No new rasterizer or systems mechanism is selected. Versioned Qt source shows a separate native glyph shader, while Breeze's decoration source uses QPainter. Therefore final output comparison is necessary for both paths. Use Xvfb and nested KWin rather than replacing the running compositor. Treat the software renderer as a control only.

The two-phase challenge requires an actual Plasma host and an explicit fractional-origin contrast. Accept both. A standalone Breeze fixture cannot establish the applet-host result, and scale changes alone cannot establish snapping.

The installed KWin binary carries `cap_sys_nice`, so ordinary library overrides do not reach it. Use the system loader and upstream `KWIN_FORCE_OWN_QPA` for the isolated test, without changing the installed capability. Record loader-resolved Qt identity. A D-Bus configuration without service directories prevents desktop helper activation. Use separate short state paths for each nested condition and keep Unix socket paths within their native length limit.

Plasma buffer dimensions prove effective device scale. Record Wayland's integer screen scale separately. Compare final composited glyph cells as well as the applet's own capture, because their byte rounding can differ. Report both errors without changing the independent matching threshold.
