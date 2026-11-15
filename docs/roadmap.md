# Fontreal Roadmap

This is the source of truth for project work. Task identifiers are permanent. An `FR-NNN` number is never reused or changed. Move tasks between sections when their status changes. Never mark more than one task active.

Status legend:

- 🎯 **Active** — implementation or required review is in progress
- ⏭ **Planned next** — accepted and ordered for near-term delivery
- ◻ **Planned later** — accepted but not yet scheduled
- ⚠️ **Accepted residual risk** — bounded work is complete, but a documented limitation remains accepted
- ❌ **Declined** — considered and intentionally not supported
- ✅ **Completed** — implemented and validated

Preserve the accepted Qt baseline for Noto Sans and Inconsolata Nerd Font. New comparisons use requested integer point sizes from 8pt through 16pt. Font, point size, style, blend, and polarity form one comparison condition. Resolved device units belong in diagnostic metadata, not comparison size labels. Human judgment at native display resolution remains the acceptance criterion.

The user now requests the validated raw browser profile for KDE too. Weighted stems only, after B's profile/join and native corner-fringe treatment, is the selected optical benchmark. The user reports improved readability throughout the samples. Extend the chart to every integer size from 8–16pt in regular and bold, covering the KDE font group, Inconsolata Nerd Font, the decorative and earlier Nimbus regression cases, Arial, Segoe UI and Nimbus Sans. Keep the previous B treatment as an explicit comparison. Do not include the optional curve extension or synthesize missing bold faces. No font, character or coordinate exceptions are allowed in the renderer. These remain optical diagnostics, not an installed policy. Keep one folder for arrow browsing and preserve the installed raw preset. Earlier broad-gallery and application controls remain available. Teams for Linux and other Flatpak applications also need support.

## Active

- **FR-018: Apply the validated raw rendering profile.** Apply the complete selected profile to KDE and retain it in ordinary Firefox and Floorp. Force nearest-50% geometry, raw grayscale coverage, whole-pixel placement and encoded blending for eligible TrueType and CFF fonts, with no contrast ramp or dropout floor. Keep earlier diagnostic modes. Preserve browser accounts, sessions, sandboxing, chosen fonts and sizes, and unrelated preferences, with the user's additional Helvetica → Noto Sans substitution. Explicit CFF requests still receive the profile, including CFF2 variations and CID-keyed collections. KDE needs a matching native FreeType capability and coherent Qt/FreeType package bundle, including coinstalled architectures. Retain package/update/rollback and disposable full-session checks before host deployment. Native authorization and normal user logout/login follow the reviewed bundle. Keep integer 8–16pt comparisons and broader real-world optical qualification. Avoid website-specific rules. Resume through the [portable handoff](research/handoff.md). See the [browser activation guide](experiments/browser-masks.md), [geometry and contrast analysis](research/16pt-geometry.md), and [native studies](plans/FR-018-axis-study.md).

## Planned next

- **FR-016: Support Electron applications.** Use Teams for Linux as the first real application. Trace its exact Electron/Chromium build and font backend. Match the reference in a local test page before testing the application. Include its Flatpak package; preserve the user's account, application data, and normal sandbox.
- **FR-017: Deliver treatment inside Flatpak sandboxes.** Build against the application's actual runtime or bundled engine, with exact version records and a separate opt-in comparison. Check both Qt/GTK runtime libraries and bundled browser engines. Preserve normal application updates and a stock launch. A host library replacement alone is not coverage.
- **FR-005: GNOME application support.** Identify the actual GTK 3 and GTK 4 text paths, including Pango, Cairo, and GPU composition. Build isolated tests in existing applications. Match the reference before proposing desktop configuration or library changes. [PangoCairo documentation](https://docs.gtk.org/PangoCairo/) identifies one relevant path, without establishing coverage of every GTK renderer.
- **FR-003: Calibrate native application text.** Focus on Noto Sans menus and Inconsolata Nerd Font terminal text across sizes, display scales, and light/dark colors. Retain other fonts as comparison controls. Use the user's visual feedback to choose a blend policy. Preserve explicit controls until the transition is supported by evidence.
- **FR-012: Make the KDE packages distributable.** Prepare portable public documentation and maintain a check against machine-specific references. Supply matching source and binary packages, build provenance, required licenses and notices, signed APT metadata, supported versions, and recovery instructions. Establish the Qt security-update rebuild process. Fontreal's original code uses MIT, with upstream license exceptions for Qt-derived and FreeType-derived patches. See the [public documentation specification](plans/FR-012-public-docs.md).

## Planned later

- **FR-006: Wine application support.** Trace GDI and DirectWrite separately. Test a private Wine prefix and existing Windows applications without changing the user's prefixes. Compare glyph masks, placement, and composition. Wine's [FreeType integration](https://github.com/wine-mirror/wine/blob/master/dlls/win32u/freetype.c) is a starting point for investigation.
- **FR-007: Windows 11 feasibility.** Determine which GDI, DirectWrite, and application-owned paths expose enough control. First test a normal application using documented APIs. Evaluate crisp hinting, grayscale edges, pixel placement, and blending separately. Microsoft's [custom DirectWrite rendering parameters](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwritefactory-createcustomrenderingparams) expose some controls, but do not prove system-wide feasibility. Proceed to a Windows 11 prototype only if the required behavior is achievable and a Windows test environment is available.

## Accepted residual risk

No residual risk is accepted.

## Declined

No task is declined. Non-native LCD resolution remains outside the project scope.

## Completed

- **FR-015: Support Firefox-based browsers.** The approved automatic monochrome hints, grayscale masks, mild contrast, and Mozilla sRGB preblend work in existing Firefox and Floorp profiles. Reversible per-user activation preserves account data, unrelated preferences, native launches, and accepted Qt output. Normal browser startup and the disposable comparison are verified. Mozilla's background approximation and unverified toolbar-font equality remain stated limits. See the [browser specification](plans/FR-015-browser-masks.md) and [rendering investigation](research/non-qt-rendering.md).
- **FR-011: Package a KDE desktop pilot.** On-demand builds support Debian 13/Qt 6.8.2 and Ubuntu 26.04/Qt 6.10.2 amd64 using exact distro sources and rules. Separate per-user activation starts disabled. Native package and complete-session checks cover enabling, disabling, independent Qt updates, font preservation, guarded installation, and offline official-package rollback. The host-matching bundle passes installation simulation. See the [build and deployment guide](build-system.md) and [package specification](plans/FR-011-system-builds.md).
- **FR-013: Match Qt Quick composition and placement.** Eligible OpenGL text now uses the selected blend and stable fractional placement. Independent checks pass for real Qt Quick and Plasma output at 100% and 125%, including Intel GPU controls. Ordinary colors, noneligible fonts, and accepted native/KWin output remain correct. See the [GPU specification](plans/FR-013-quick-linear.md).
- **FR-014: Confine the A8 text transfer profile.** The selected profile now follows the current eligible TrueType raster draw. Ordinary and static mixed-font checks preserve stock CFF/color pixels, including grayscale CFF after TrueType. Existing independent widget, Konsole, and 100%/125% KWin title checks pass. See the [profile-scope specification](plans/FR-014-a8-profile-scope.md).
- **FR-004: Measure KDE rendering paths.** Isolated KWin title glyphs match mild/linear at 100% and 125%. Initial Plasma applet and Qt Quick checks exposed GPU blending and fractional renderer gaps. Grayscale CFF controls reproduced shared-profile spillover. Corrections are tracked under FR-013/FR-014, and full-session activation remains FR-011. See the [checks and comparison guide](experiments/kde-paths.md).
- **FR-010: Test native mild contrast with the preferred fonts.** Carry the selected coverage treatment into the isolated Qt preview. Compare Noto Sans menus and Inconsolata Nerd Font terminal text, with explicit blending and unadjusted controls. Preserve normal application configuration.
- **FR-009: Compare crisper diagonal edges.** Keep the preferred grayscale reference and compare two tighter gray transitions with automatic-hinted binary output in a separate native study. Preserve the ordinary experiment and leave desktop treatment selection to later visual calibration.
- **FR-008: Correct the Konsole menu font control.** Apply the selected family and pixel size to KDE's separate menu font role. Check the private configuration and rendered menus. Keep the remaining visual calibration in FR-003.
- **FR-001: Controlled FreeType comparison.** Native viewer and repeatable exports compare seven treatments. Independent checks cover glyph masks, blending, placement, and native-pixel presentation. The user selected automatic mono hints with gray edges and identified a size-dependent blend preference. See the [experiment](experiments/freetype-comparison.md) and [KDE investigation](research/kde-integration.md).
- **FR-002: First KDE application test.** The isolated Qt build and stock/linear/encoded Konsole launches reproduce the selected treatment. Native widget and real-application checks pass. Visual calibration remains FR-003. See the [test guide](experiments/kde-preview.md) and [specification](plans/FR-002-qt-native.md).
