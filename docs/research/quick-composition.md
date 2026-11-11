# Linear text composition in Qt Quick

## Question

How can eligible Qt Quick GPU text match the selected linear blend without changing ordinary interface colors?

## Repository constraints

The accepted KWin and native-widget paths already match the reference. FR-014 confines their A8 profile to eligible text. The remaining OpenGL path uses the desired glyph masks but composes their edges in encoded RGB. The [KDE checks](../experiments/kde-paths.md) also show that the real Plasma component path needs a per-run renderer selection.

The first prototype keeps the existing opaque reference targets, Noto Sans 15px at 100% and 125%, three palettes, and explicit linear/encoded controls. Existing arbitrary-transform and transparent-intermediate guarantees remain deferred. This is a private Qt 6.10.2 experiment, not desktop activation or certification of every backend.

## Options

| Option | Result | Limit |
| --- | --- | --- |
| Change glyph alpha or encode the fragment output | Can approximate a selected foreground/background pair | Cannot compute the required blend for arbitrary opaque background colors without destination decoding |
| Enable sRGB conversion for the whole scene | Supplies native destination decoding and encoding | Changes existing encoded UI colors and texture behavior unless the whole renderer changes |
| Enable native sRGB writes for eligible text draws | Supplies the required destination operation while other draws retain encoded behavior | Needs compatible target storage, scoped pipeline state, and preserved texture reads |

## Evidence

Qt's native glyph fragment multiplies a premultiplied color by coverage. Its A8 uniform update does not consult the raster font engine's blend preference. Therefore changing the QtGui A8 table alone cannot fix this path. [Qt native glyph material](https://raw.githubusercontent.com/qt/qtdeclarative/v6.10.2/src/quick/scenegraph/qsgdefaultglyphnode_p.cpp), [fragment shader](https://raw.githubusercontent.com/qt/qtdeclarative/v6.10.2/src/quick/scenegraph/shaders_ng/8bittextmask.frag).

OpenGL's sRGB framebuffer mode decodes destination RGB before blending, then encodes the result. It requires sRGB-capable target storage and a separate enable state. EGL can request that storage for a window surface. These specifications define a native operation that matches the required color-space sequence. [Framebuffer sRGB](https://registry.khronos.org/OpenGL/extensions/EXT/EXT_framebuffer_sRGB.txt), [EGL colorspace](https://registry.khronos.org/EGL/extensions/KHR/EGL_KHR_gl_colorspace.txt).

The inspected Qt RHI OpenGL backend controls that enable at framebuffer bind. The scene graph exposes other per-material blend state but no sRGB-write choice. The prototype needs a draw-local distinction through those existing owners. [Qt RHI OpenGL](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/rhi/qrhigles2.cpp), [material state](https://raw.githubusercontent.com/qt/qtdeclarative/v6.10.2/src/quick/scenegraph/coreapi/qsgmaterialshader.h).

sRGB texture sampling normally decodes stored colors. A write-only sRGB view over a linear RGBA8 texture can retain encoded reads through the original texture. OpenGL texture views require immutable storage and compatible view formats. Reuse Qt's existing write-view description for the controlled render textures. [Texture views](https://registry.khronos.org/OpenGL/extensions/ARB/ARB_texture_view.txt), [texture storage](https://registry.khronos.org/OpenGL/extensions/ARB/ARB_texture_storage.txt), [Qt texture interface](https://raw.githubusercontent.com/qt/qtbase/v6.10.2/src/gui/rhi/qrhi.h).

An arXiv API search on 2026-11-11 fetched two abstracts in each of `cs.GR`, `cs.CV`, and `cs.HC`. Terms were alpha blending, gamma correction, and text rendering. Six isolated abstract reads found no direct Qt Quick composition mechanism. The result is thin for this question. The native specifications and actual Qt source provide the implementation evidence.

| Paper and cluster | Relevant takeaway | Relevance / practicality / abstract evidence |
| --- | --- | --- |
| [Alpha Blending with No Division Operations](https://arxiv.org/abs/2202.02864v2), arithmetic | Exact integer blend arithmetic does not supply transfer-function integration or destination access | 3 / 8 / 6 |
| [Ultra-fast Neural Inference for Stochastic Gaussian Splatting Denoising](https://arxiv.org/abs/2609.25604v1), stochastic reconstruction | Noise reconstruction is unrelated to exact deterministic glyph pixels | 0 / 1 / 5 |
| [Gaussian Blending](https://arxiv.org/abs/2511.15102v1), spatial coverage | Sampling-dependent coverage is a different owner from the measured blend gap | 2 / 3 / 5 |
| [The Alpha Blending Hypothesis](https://arxiv.org/abs/2605.10334v2), learned monitoring | Detecting compositing artifacts does not implement the required composition | 0 / 1 / 6 |
| [An AI-Resilient Text Rendering Technique](https://arxiv.org/abs/2401.10873v1), semantic presentation | Intentional gray text must remain meaningful, but this work does not define GPU blending | 1 / 2 / 5 |
| [Learning-Based Error Detection for Instrument Clusters](https://arxiv.org/abs/2409.02647v1), learned monitoring | Perceptual monitoring cannot replace the independent exact-pixel oracle | 1 / 2 / 5 |

These scores describe fit to this task, not the quality of the papers. Only abstracts were read. Their reported results do not validate a Fontreal implementation.

## Decision

Prototype native OpenGL sRGB composition scoped to eligible linear glyph draws. Decode the foreground before premultiplying its effective alpha. Let the native blend operation decode the opaque destination and encode the result. Keep encoded text, CFF/color glyphs, and ordinary drawing on their existing paths.

Use sRGB-capable window storage and controlled write views for single-sample RGBA8/BGRA8 render textures. Keep ordinary texture reads on the original linear-format view so existing encoded colors remain unchanged. Test both a window and a sampled opaque layer. Verify the actual target before selecting linear foreground data. An unsupported or external target retains encoded composition and must be identified as unsupported, rather than receiving linear values in a linear-format target.

Use the existing per-glyph-run selection owner so eligible Plasma text reaches native glyphs even when its requested default renderer differs. Keep requested and effective renderers distinct in evidence. Explicit coordinate checks expose fractional half-pixel stretching after batch merging. Retain fitted quads and the vertex shader, preserve the shared origin through the existing full-matrix material flag, and snap that origin once. This disables merged batches for eligible materials. Desktop performance remains a separate pilot measurement.

The first step is a private Qt Quick build and an opaque three-color GPU comparison with ordinary-color controls. Do not activate the desktop until target handling, state restoration, actual Plasma output, and the independent pixel checks pass. Native API reuse wins over a replacement renderer or a foreground-only approximation.

## Rejected options

Do not use a foreground-only gamma conversion as an arbitrary-background blend. Do not enable sRGB writes for every UI draw. Do not sample an sRGB write view as though it were unchanged encoded texture data. Do not replace GPU rendering with the software diagnostic. The fetched neural and Gaussian methods solve different problems and add no justified dependency here.

## Revisit when

Revisit the mechanism if the tested targets cannot expose compatible native storage, or if preserving ordinary colors needs a broader renderer change. Other GPU APIs, multisample targets, transparent intermediate surfaces, and physical driver coverage need separate evidence. The remaining question is whether the smallest native integration preserves all tested color and target transitions without adding unnecessary render passes.

## Sources

Version-pinned Qt 6.10.2 source, Khronos specifications, real arXiv Atom responses, and the repository's independent captures support this proposal. Local checks confirm framebuffer-sRGB, texture-view, and texture-storage support in the tested Mesa environment. This is a prototype decision, not an upstream support claim.
