# Fontreal Roadmap

This is the source of truth for project work. Task identifiers are permanent. An `FR-NNN` number is never reused or changed. Move tasks between sections when their status changes. Never mark more than one task active.

Status legend:

- 🎯 **Active** — implementation or required review is in progress
- ⏭ **Planned next** — accepted and ordered for near-term delivery
- ◻ **Planned later** — accepted but not yet scheduled
- ⚠️ **Accepted residual risk** — bounded work is complete, but a documented limitation remains accepted
- ❌ **Declined** — considered and intentionally not supported
- ✅ **Completed** — implemented and validated

The visual reference is automatic monochrome hinting with grayscale edges and integral glyph origins. Blend preference changes with effective size and font. Human judgment at native display resolution remains the acceptance criterion.

## Active

No task is active.

## Planned next

- **FR-003: Calibrate native application text.** Compare Noto Sans and DejaVu Sans across sizes, display scales, and light/dark colors. Use the user's visual feedback to choose a blend policy. Preserve explicit controls until the transition is supported by evidence.
- **FR-004: Cover KDE rendering paths.** Test KWin decoration text and Plasma Qt Quick separately from native widgets. Trace actual paths at integral and fractional scales. Define installation and rollback only after isolated tests succeed.

## Planned later

- **FR-005: GNOME application support.** Identify the actual GTK 3 and GTK 4 text paths, including Pango, Cairo, and GPU composition. Build isolated tests in existing applications. Match the reference before proposing desktop configuration or library changes. [PangoCairo documentation](https://docs.gtk.org/PangoCairo/) identifies one relevant path, without establishing coverage of every GTK renderer.
- **FR-006: Wine application support.** Trace GDI and DirectWrite separately. Test a private Wine prefix and existing Windows applications without changing the user's prefixes. Compare glyph masks, placement, and composition. Wine's [FreeType integration](https://github.com/wine-mirror/wine/blob/master/dlls/win32u/freetype.c) is a starting point for investigation.
- **FR-007: Windows 11 feasibility.** Determine which GDI, DirectWrite, and application-owned paths expose enough control. First test a normal application using documented APIs. Evaluate crisp hinting, grayscale edges, pixel placement, and blending separately. Microsoft's [custom DirectWrite rendering parameters](https://learn.microsoft.com/en-us/windows/win32/api/dwrite/nf-dwrite-idwritefactory-createcustomrenderingparams) expose some controls, but do not prove system-wide feasibility. Proceed to a Windows 11 prototype only if the required behavior is achievable and a Windows test environment is available.

## Accepted residual risk

No residual risk is accepted.

## Declined

No task is declined. Non-native LCD resolution remains outside the project scope.

## Completed

- **FR-008: Correct the Konsole menu font control.** Apply the selected family and pixel size to KDE's separate menu font role. Check the private configuration and rendered menus. Keep the remaining visual calibration in FR-003.
- **FR-001: Controlled FreeType comparison.** Native viewer and repeatable exports compare seven treatments. Independent checks cover glyph masks, blending, placement, and native-pixel presentation. The user selected automatic mono hints with gray edges and identified a size-dependent blend preference. See the [experiment](experiments/freetype-comparison.md) and [KDE investigation](research/kde-integration.md).
- **FR-002: First KDE application test.** The isolated Qt build and stock/linear/encoded Konsole launches reproduce the selected treatment. Native widget and real-application checks pass. Visual calibration remains FR-003. See the [test guide](experiments/kde-preview.md) and [specification](plans/FR-002-qt-native.md).
