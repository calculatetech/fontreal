# Fontreal Roadmap

Task identifiers are permanent. Keep at most one task active. Git preserves the details of completed experiments.

Status legend:

- 🎯 **Active** — implementation or required review is in progress
- ⏭ **Planned next** — accepted and ordered for near-term delivery
- ◻ **Planned later** — accepted but not yet scheduled
- ⚠️ **Accepted residual risk** — bounded work is complete, but a documented limitation remains accepted
- ❌ **Declined** — considered and intentionally not supported
- ✅ **Completed** — implemented and validated

Compare new rendering at whole point sizes from 8pt through 16pt. Keep the font, size, style, background, and display scale fixed in each comparison. Judge the result at native display resolution. Keep the renderer generic across fonts and characters.

## Active

No active task.

## Planned next

- **FR-016: Support Chromium-based browsers and Electron applications.** Deliver rendering through ordinary app launches. Keep it enabled across app updates without repeating qualification for each update. Preserve accounts, application data, native launch and security paths, official updates and a stock launch. Verify rendering inside each app.
- **FR-017: Deliver treatment inside Flatpak sandboxes.** Prioritize Teams, Bitwarden and Telegram. Build for each app's runtime or bundled engine, record the tested versions and run separate opt-in comparisons. Check Qt, GTK and embedded browser paths. Preserve accounts, application data, sandboxes, ordinary updates and a stock launch.
- **FR-005: GNOME application support.** Identify the GTK 3 and GTK 4 text paths, including Pango, Cairo and GPU composition. Compare isolated tests in existing apps against the V3 reference before changing the desktop.
- **FR-003: Calibrate native application text.** Compare Noto Sans menus and Inconsolata Nerd Font terminal text across sizes, display scales and light and dark colors. Keep other fonts as controls. Use visual feedback to choose the blend and retain the controls until comparisons support changing it.
- **FR-012: Make the KDE packages distributable.** Maintain portable docs, matching source and binaries, build provenance, licenses, supported versions and recovery instructions. Supply signed APT metadata and establish the rebuild process for Qt security updates.

## Planned later

- **FR-006: Wine application support.** Trace GDI and DirectWrite separately. Test existing Windows apps in an isolated Wine prefix. Compare glyph coverage, placement and blending.
- **FR-007: Windows 11 feasibility.** Check GDI, DirectWrite and application-owned renderers. Begin with an ordinary app and documented Windows APIs. Evaluate hinting, grayscale edges, placement and blending separately. Prototype when the required behavior is possible and a Windows test system is available.

## Accepted residual risk

None recorded.

## Declined

Non-native LCD resolution remains outside the project scope.

## Completed

- **FR-023: Enable RGB Breeze captions on Debian 13.** Qualified the stock OpenGL and software paths. Verified the shared 3.0.1 DEB on Debian 13 and Ubuntu 26.04.
- **FR-022: Deliver Fontreal V3 for Qt and KDE with stock Qt packages.** Published a shared DEB, a shared RPM, an Arch package and a KDE Linux system extension. Validated rendering and removal on nine Plasma Wayland systems. Retired the V1 and V2 source paths and kept the archived rollback guides.
- **FR-021: Deliver accepted V2 rendering.** Released the O and K3 profiles with native packages and selected application integrations.
- **FR-020: Simplify browser launch activation.** Qualified ordinary Firefox and Floorp launches with the selected profile.
- **FR-019: Carry the selected profile into native KDE packages.** Validated the earlier Debian and Ubuntu packages and rollback.
- **FR-018: Deliver the selected native rendering profile.** Qualified weighted stem rendering and compared stock Qt with the selected profile at KDE defaults.
- **FR-015: Support Firefox-based browsers.** Qualified reversible activation in working Firefox and Floorp profiles.
- **FR-014: Confine the A8 text transfer profile.** Qualified mixed-font raster draws without affecting stock fallback glyphs.
- **FR-013: Match Qt Quick composition and placement.** Qualified the earlier Qt Quick OpenGL treatment at two display scales.
- **FR-011: Package a KDE desktop pilot.** Qualified matching distro packages, session activation and rollback.
- **FR-010: Test native mild contrast with the preferred fonts.** Compared menu and terminal text in an isolated Qt build.
- **FR-009: Compare crisper diagonal edges.** Compared grayscale transition and binary treatments.
- **FR-008: Correct the Konsole menu font control.** Qualified the independent KDE menu font role.
- **FR-004: Measure KDE rendering paths.** Traced Widgets, Qt Quick, Plasma applets and KWin titles.
- **FR-002: First KDE application test.** Compared matching Konsole launches with stock and two blend choices.
- **FR-001: Controlled FreeType comparison.** Qualified the native pixel viewer and its rendering controls.
