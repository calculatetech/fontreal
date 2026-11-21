#include <QDebug>
#include <QCache>
#include <QFile>
#include <QCryptographicHash>
#include <dlfcn.h>
#include <QGlyphRun>
#include <QGenericPlugin>
#include <sys/mman.h>
#include <unistd.h>
#include <link.h>
#include <QScopeGuard>
#include <QScopedValueRollback>
#include <rhi/qrhi.h>
#include <ft2build.h>
#include FT_GLYPH_H
#include FT_SYNTHESIS_H
#include FT_TRUETYPE_TABLES_H
#include FT_FONT_FORMATS_H
#include FT_MODULE_H
#include <QtGui/private/qfontengine_ft_p.h>
#include <QSGFlatColorMaterial>
#include <QtGui/private/qrawfont_p.h>
#include <QtQuick/private/qsgcontextplugin_p.h>
#include <QtQuick/private/qsgdefaultcontext_p.h>
#include <QtQuick/private/qsgdefaultrendercontext_p.h>
#include <QtQuick/private/qsgrenderer_p.h>
#include <QGuiApplication>
#include <QtQuick/private/qsginternaltextnode_p.h>
#include <cmath>
#include <rhi/qshader.h>
#include "coverage_qsb.h"
#include <atomic>
#include "font-engine.h"
#include "wayland-output.h"
#include "fontreal_v3_outline.h"
#include "white-text.h"



struct Sample
{
    Frame frame{};
    QImage mask;
};

Sample outlineMask(QFontEngine *source, glyph_t glyph, QFixedPoint phase, qreal scale, QColor color, fontreal_v3::StripeLayout layout)
{
    using namespace fontreal_v3;
    const qreal pixels = source->fontDef.pixelSize * scale;
    if (pixels < 8 || pixels > 32)
        return {};
    std::unique_ptr<QFontEngine> resized;
    if (!qFuzzyCompare(scale, 1.0)) {
        resized.reset(source->cloneWithSize(pixels));
        if (!resized)
            return {};
        source = resized.get();
    }
    auto *engine = static_cast<QFontEngineFT *>(source);
    if (!engine->drawAntialiased() || engine->isBitmapFont())
        return {};
    auto face = engine->lockFace();
    auto unlock = qScopeGuard([&] { engine->unlockFace(); });
    if (!face || !FT_IS_SCALABLE(face) || FT_HAS_COLOR(face))
        return {};
    FT_Matrix oldMatrix;
    FT_Vector oldShift;
    FT_Get_Transform(face, &oldMatrix, &oldShift);
    auto restore = qScopeGuard([&] { FT_Set_Transform(face, &oldMatrix, &oldShift); });
    FT_Vector shift{phase.x.value(), -phase.y.value()};
    FT_Set_Transform(face, &oldMatrix, &shift);
    const auto library = face->glyph->library;
    FT_Bool oldDarkening = true;
    const FT_Bool noDarkening = true;
    const bool changedDarkening = qstrcmp(FT_Get_Font_Format(face), "CFF") == 0
            && !FT_Property_Get(library, "cff", "no-stem-darkening", &oldDarkening)
            && !oldDarkening && !FT_Property_Set(library, "cff", "no-stem-darkening", &noDarkening);
    auto restoreDarkening = qScopeGuard([&] {
        if (changedDarkening)
            FT_Property_Set(library, "cff", "no-stem-darkening", &oldDarkening);
    });
    constexpr int flags = FT_LOAD_TARGET_NORMAL | FT_LOAD_NO_BITMAP | FT_LOAD_NO_AUTOHINT;
    const auto load = [&](int extra) {
        if (FT_Load_Glyph(face, glyph, flags | extra) || face->glyph->format != FT_GLYPH_FORMAT_OUTLINE)
            return false;
        if ((engine->synthesized() & QFontEngine::SynthesizedBold))
            FT_GlyphSlot_Embolden(face->glyph);
        if ((engine->synthesized() & QFontEngine::SynthesizedItalic))
            FT_GlyphSlot_Oblique(face->glyph);
        return true;
    };
    if (!load(0))
        return {};
    FT_Glyph outline = nullptr;
    if (FT_Get_Glyph(face->glyph, &outline))
        return {};
    auto release = qScopeGuard([&] { FT_Done_Glyph(outline); });
    const FT_GlyphSlot slot = face->glyph;
    if (FT_Render_Glyph(slot, FT_RENDER_MODE_NORMAL) || slot->bitmap.pixel_mode != FT_PIXEL_MODE_GRAY
            || slot->bitmap.width > 255 || slot->bitmap.rows > 255)
        return {};
    Sample result;
    result.frame = {slot->bitmap_left, slot->bitmap_top, int(slot->bitmap.width), int(slot->bitmap.rows)};
    const auto hinted = sampleOutline(slot->library, reinterpret_cast<FT_OutlineGlyph>(outline)->outline, result.frame);
    if (hinted.pixels.empty())
        return {};
    const bool lightFace = fontreal_qt::lightFace(*engine, face);
    OutlineSamples unhinted;
    if (lightFace && load(FT_LOAD_NO_HINTING))
        unhinted = sampleOutline(slot->library, slot->outline, result.frame);
    const auto ink = qGray(color.rgb()) < 128 ? Ink::Dark : Ink::Light;
    const bool italic = (engine->synthesized() & QFontEngine::SynthesizedItalic) || (face->style_flags & FT_STYLE_FLAG_ITALIC);
    const auto values = glyphCoverage(hinted, &unhinted, toneCurve(pixels, ink), pixels, ink, italic);
    if (layout == StripeLayout::None) {
        result.mask = QImage(result.frame.width, result.frame.height, QImage::Format_Alpha8);
        for (int y = 0; y < result.frame.height; ++y)
            std::copy_n(values.data() + y * result.frame.width, result.frame.width, result.mask.scanLine(y));
    } else {
        const auto tone = toneCurve(pixels, ink);
        auto &contour = reinterpret_cast<FT_OutlineGlyph>(outline)->outline;
        const auto white = ink == Ink::Light
            ? whiteTextStripes(engine, face, contour, hinted, values, pixels, layout, load) : QImage{};
        result.mask = QImage(result.frame.width, result.frame.height, QImage::Format_ARGB32_Premultiplied);
        for (int y = 0; y < result.frame.height; ++y) {
            auto *row = reinterpret_cast<QRgb *>(result.mask.scanLine(y));
            for (int x = 0; x < result.frame.width; ++x) {
                if (!white.isNull()) {
                    const auto rgb = reinterpret_cast<const QRgb *>(white.constScanLine(y))[x];
                    row[x] = (rgb & RGB_MASK) | (QRgb(values[y * result.frame.width + x]) << 24);
                    continue;
                }
                auto channels = hinted.stripes(x, y, layout);
                for (auto &channel : channels)
                    channel = tone[channel];
                const auto rgb = projectChannels(values[y * result.frame.width + x], channels, ink);
                // Qt's color-glyph atlas carries the four coverage bytes unchanged.
                row[x] = qRgba(rgb[0], rgb[1], rgb[2], values[y * result.frame.width + x]);
            }
        }
    }
    return result;
}


class ProbeEngine final : public QFontEngine {
public:
    ProbeEngine(QFontEngine *source, QColor color, fontreal_v3::StripeLayout stripes)
        : QFontEngine(Freetype), engine(source), ink(color), layout(stripes)
    {
        fontDef = engine->fontDef;
        glyphFormat = layout == fontreal_v3::StripeLayout::None ? Format_A8 : Format_ARGB;
    }
    glyph_t glyphIndex(uint c) const override { return engine->glyphIndex(c); }
    int stringToCMap(const QChar *s, int n, QGlyphLayout *glyphs, int *count, ShaperFlags flags) const override
    { return engine->stringToCMap(s, n, glyphs, count, flags); }
    glyph_metrics_t boundingBox(glyph_t glyph) override { return engine->boundingBox(glyph); }
    QFixed capHeight() const override { return engine->capHeight(); }
    qreal maxCharWidth() const override { return engine->maxCharWidth(); }
    QFixed ascent() const override { return engine->ascent(); }
    QFixed descent() const override { return engine->descent(); }
    QFixed leading() const override { return engine->leading(); }
    bool supportsHorizontalSubPixelPositions() const override
    { return engine->supportsHorizontalSubPixelPositions(); }
    bool supportsTransformation(const QTransform &transform) const override
    { return engine->supportsTransformation(transform); }
    void addGlyphsToPath(glyph_t *glyphs, QFixedPoint *positions, int count,
                         QPainterPath *path, QTextItem::RenderFlags flags) override
    { engine->addGlyphsToPath(glyphs, positions, count, path, flags); }
    glyph_metrics_t alphaMapBoundingBox(glyph_t glyph, const QFixedPoint &phase,
                                        const QTransform &transform, GlyphFormat) override
    {
        const auto sample = outlineMask(engine.data(), glyph, phase, transform.m22(), ink,
                                        fontreal_v3::StripeLayout::None);
        if (sample.mask.isNull())
            return engine->alphaMapBoundingBox(glyph, phase, transform, Format_A8);
        glyph_metrics_t result;
        result.x = sample.frame.left;
        result.y = -sample.frame.top;
        result.width = sample.frame.width;
        result.height = sample.frame.height;
        return result;
    }
    QImage alphaMapForGlyph(glyph_t glyph, const QFixedPoint &phase, const QTransform &transform) override
    {
        auto sample = outlineMask(engine.data(), glyph, phase, transform.m22(), ink, layout);
        if (sample.mask.isNull())
            return engine->alphaMapForGlyph(glyph, phase, transform).convertToFormat(QImage::Format_Alpha8);
        return sample.mask;
    }
    QImage bitmapForGlyph(glyph_t glyph, const QFixedPoint &phase,
                          const QTransform &transform, const QColor &) override
    {
        auto sample = outlineMask(engine.data(), glyph, phase, transform.m22(), ink, layout);
        if (!sample.mask.isNull())
            return sample.mask;

        const auto gray = engine->alphaMapForGlyph(glyph, phase, transform).convertToFormat(QImage::Format_Alpha8);
        QImage packed(gray.size(), QImage::Format_ARGB32_Premultiplied);
        for (int y = 0; y < gray.height(); ++y) {
            const auto *in = gray.constScanLine(y);
            auto *row = reinterpret_cast<QRgb *>(packed.scanLine(y));
            for (int x = 0; x < gray.width(); ++x)
                row[x] = qRgba(in[x], in[x], in[x], in[x]);
        }
        return packed;
    }
private:
    QExplicitlySharedDataPointer<QFontEngine> engine;
    QColor ink;
    fontreal_v3::StripeLayout layout;
};

namespace {
thread_local QSGRenderer *currentRenderer = nullptr;
enum class OutputGrid { MultipleOrMissing, Single, SingleUnrotated };
std::atomic<OutputGrid> outputGrid = OutputGrid::MultipleOrMissing;

std::atomic_bool nativeWayland = false;
QShader coverageShader;

bool supportsTreatment(QSGRenderContext *render)
{
    return qEnvironmentVariableIntValue("FONTREAL_QUAL_TONE") == 1
            && render->rhi() && render->rhi()->backend() == QRhi::OpenGLES2;
}

struct EngineKey {
    QFontEngine *font;
    fontreal_v3::StripeLayout layout;
    bool lightInk;

    bool operator==(const EngineKey &other) const
    {
        return font == other.font && layout == other.layout && lightInk == other.lightInk;
    }
};

size_t qHash(const EngineKey &key, size_t seed = 0)
{
    return qHashMulti(seed, key.font, static_cast<int>(key.layout), key.lightInk);
}

class GlyphEngines final : public QObject {
    Q_OBJECT
public:
    explicit GlyphEngines(QSGRenderContext *render) : QObject(render)
    {
        connect(render, &QSGRenderContext::invalidated, this, [this] { fonts.clear(); },
                Qt::DirectConnection);
    }

    QRawFont replacement(QFontEngine *font, fontreal_v3::StripeLayout layout, QColor ink)
    {
        const EngineKey key{font, layout, qGray(ink.rgb()) >= 128};
        if (auto *existing = fonts.object(key))
            return *existing;
        QRawFont result;
        QRawFontPrivate::get(result)->setFontEngine(fontreal_qt::fontconfigAllowsAntialiasing(*font)
                ? new ProbeEngine(font, key.lightInk ? Qt::white : Qt::black, layout) : font);
        fonts.insert(key, new QRawFont(result));
        return result;
    }
private:
    QCache<EngineKey, QRawFont> fonts{128};
};

bool snapOutputMatrix(const QSGMaterialShader::RenderState &state, qreal atlasDpr, QMatrix4x4 &matrix)
{
    const auto *renderer = currentRenderer;
    const auto grid = outputGrid.load(std::memory_order_relaxed);
    if (!renderer || grid == OutputGrid::MultipleOrMissing
            || !nativeWayland.load(std::memory_order_relaxed)
            || !qFuzzyCompare(state.devicePixelRatio(), float(atlasDpr))
            || renderer->clearColor().alpha() != 255)
        return false;

    const auto *target = renderer->renderTarget().rt;
    if (!target || target->resourceType() != QRhiResource::SwapChainRenderTarget
            || state.viewportRect() != QRect(QPoint(), target->pixelSize()))
        return false;
    matrix = state.modelViewMatrix();
    const float logicalX = matrix(0, 3);
    const float logicalY = matrix(1, 3);
    matrix(0, 3) = matrix(1, 3) = 0;
    if (!matrix.isIdentity() || !qIsFinite(logicalX) || !qIsFinite(logicalY))
        return false;
    const float dpr = state.devicePixelRatio();
    const auto aligned = [dpr](double logical) {
        const double physical = logical * dpr;
        return qAbs(physical - std::round(physical)) < 0.0001;
    };
    if (aligned(logicalX) && aligned(logicalY)) {
        matrix = state.modelViewMatrix();
        return true;
    }
    if (grid != OutputGrid::SingleUnrotated)
        return false;

    // Use shader precision for the product, then compare to halfway without rounding again.
    matrix(0, 3) = std::floor(double(logicalX * dpr) + 0.5) / dpr;
    matrix(1, 3) = std::floor(double(logicalY * dpr) + 0.5) / dpr;
    return true;
}

class CoverageMaterial;

class CoverageShader final : public QSGMaterialShader {
public:
    explicit CoverageShader(QSGMaterialShader *stockShader) : stock(stockShader)
    {
        setShaderFileName(VertexStage, QStringLiteral(":/qt-project.org/scenegraph/shaders_ng/textmask.vert.qsb"));
        setShader(FragmentStage, coverageShader);
        setFlag(UpdatesGraphicsPipelineState);
    }

    bool updateUniformData(RenderState &, QSGMaterial *, QSGMaterial *) override;
    void updateSampledImage(RenderState &, int, QSGTexture **, QSGMaterial *, QSGMaterial *) override;
    bool updateGraphicsPipelineState(RenderState &, GraphicsPipelineState *, QSGMaterial *, QSGMaterial *) override;

private:
    std::unique_ptr<QSGMaterialShader> stock;
};

class CoverageMaterial final : public QSGMaterial {
public:
    CoverageMaterial(QSGMaterial *material, QColor color, qreal devicePixelRatio)
        : stock(material), ink(color.toRgb()), atlasDpr(devicePixelRatio)
    {
        setFlag(Blending | RequiresFullMatrix);
    }

    QSGMaterialType *type() const override
    {
        static QSGMaterialType identity;
        return &identity;
    }

    QSGMaterialShader *createShader(QSGRendererInterface::RenderMode mode) const override
    {
        return new CoverageShader(stock->createShader(mode));
    }

    int compare(const QSGMaterial *other) const override
    {
        const auto *material = static_cast<const CoverageMaterial *>(other);
        const quint64 currentInk = ink.rgba64();
        const quint64 nextInk = material->ink.rgba64();
        if (currentInk != nextInk)
            return currentInk < nextInk ? -1 : 1;
        return stock->compare(material->stock);
    }

    QSGMaterial *const stock;
    const QColor ink;
    const qreal atlasDpr;
};

QSGMaterial *stockMaterial(QSGMaterial *material)
{
    return material ? static_cast<CoverageMaterial *>(material)->stock : nullptr;
}

bool CoverageShader::updateUniformData(RenderState &state, QSGMaterial *material, QSGMaterial *old)
{
    stock->updateUniformData(state, stockMaterial(material), stockMaterial(old));
    // The stock color glyph shader leaves color.x unused in its uniform block.
    constexpr qsizetype selectorOffset = 144;
    const auto *coverage = static_cast<CoverageMaterial *>(material);
    QMatrix4x4 matrix;
    const bool rgb = snapOutputMatrix(state, coverage->atlasDpr, matrix);
    if (!rgb)
        matrix = state.modelViewMatrix();
    const float colorData[4] = {
        rgb ? 1.0f : 0.0f, 0, 0,
        float(coverage->ink.alphaF() * state.opacity())
    };
    Q_ASSERT(state.uniformData()->size() >= selectorOffset + sizeof(colorData));
    memcpy(state.uniformData()->data(), matrix.constData(), 16 * sizeof(float));
    memcpy(state.uniformData()->data() + selectorOffset, colorData, sizeof(colorData));
    return true;
}

void CoverageShader::updateSampledImage(RenderState &state, int binding, QSGTexture **texture,
                                        QSGMaterial *material, QSGMaterial *old)
{
    stock->updateSampledImage(state, binding, texture, stockMaterial(material), stockMaterial(old));
}

bool CoverageShader::updateGraphicsPipelineState(RenderState &, GraphicsPipelineState *pipeline,
                                                  QSGMaterial *material, QSGMaterial *)
{
    using State = GraphicsPipelineState;
    pipeline->blendEnable = true;
    pipeline->blendConstant = static_cast<CoverageMaterial *>(material)->ink;
    pipeline->srcColor = State::ConstantColor;
    pipeline->dstColor = State::OneMinusSrcColor;
    pipeline->separateBlendFactors = true;
    pipeline->srcAlpha = State::One;
    pipeline->dstAlpha = State::OneMinusSrcAlpha;
    return true;
}
}

class ProbeGlyphNode final : public QSGGlyphNode {
public:
    ProbeGlyphNode(QSGDefaultContext *context, QSGRenderContext *renderContext, QSGTextNode::RenderType type, int quality)
        : context(context), renderContext(renderContext), type(type), quality(quality),
          stubGeometry(QSGGeometry::defaultAttributes_Point2D(), 0)
    {
        setGeometry(&stubGeometry);
        setMaterial(&stubMaterial);
    }
    void setGlyphs(const QPointF &pos, const QGlyphRun &run) override { position = pos; glyphs = run; }
    void setColor(const QColor &next) override
    {
        if (color == next)
            return;
        color = next;
        if (firstChild())
            update();
    }
    void setStyle(QQuickText::TextStyle next) override { style = next; }
    void setStyleColor(const QColor &next) override { styleColor = next; }
    void setPreferredAntialiasingMode(AntialiasingMode next) override { aa = next; explicitAa = true; }
    void setRenderTypeQuality(int next) override { quality = next; }
    QPointF baseLine() const override
    {
        const auto *child = static_cast<QSGGlyphNode *>(firstChild());
        return child ? child->baseLine() : QPointF();
    }
    void update() override;

private:
    QSGDefaultContext *context;
    QSGRenderContext *renderContext;
    QSGTextNode::RenderType type;
    int quality;
    QSGGeometry stubGeometry;
    QSGFlatColorMaterial stubMaterial;
    QGlyphRun glyphs;
    QPointF position;
    QColor color, styleColor;
    AntialiasingMode aa = DefaultAntialiasing;
    bool explicitAa = false;
    QQuickText::TextStyle style = QQuickText::Normal;
};

void ProbeGlyphNode::update()
{
    while (auto *child = firstChild()) {
        removeChildNode(child);
        delete child;
    }
    QRawFont font = glyphs.rawFont();
    QFontEngine *engine = QRawFontPrivate::get(font)->fontEngine;
    const qreal dpr = static_cast<QSGDefaultRenderContext *>(renderContext)->currentDevicePixelRatio();
    const qreal pixels = engine ? engine->fontDef.pixelSize * dpr : 0;
    bool treat = supportsTreatment(renderContext) && pixels >= 8 && pixels <= 32
            && style == QQuickText::Normal && aa == DefaultAntialiasing && color.isValid()
            && color.alphaF() > 0 && engine->type() == QFontEngine::Freetype
            && engine->glyphFormat != QFontEngine::Format_ARGB && engine->glyphFormat != QFontEngine::Format_Mono;
    auto layout = treat && nativeWayland.load(std::memory_order_relaxed) && engine->glyphFormat == QFontEngine::Format_A32
            ? fontreal_qt::effectiveLayout(*static_cast<const QFontEngineFT *>(engine)) : fontreal_v3::StripeLayout::None;
    QGlyphRun result = glyphs;
    if (treat) {
        auto *pool = renderContext->findChild<GlyphEngines *>(Qt::FindDirectChildrenOnly);
        if (!pool)
            pool = new GlyphEngines(renderContext);
        const auto replacement = pool->replacement(engine, layout, color);
        if (QRawFontPrivate::get(replacement)->fontEngine == engine) {
            treat = false;
            layout = fontreal_v3::StripeLayout::None;
        } else {
            result.setRawFont(replacement);
        }
    }
    const auto add = [&](const QGlyphRun &run) {
        auto *node = context->QSGDefaultContext::createGlyphNode(renderContext,
            treat ? QSGTextNode::NativeRendering : type, quality);
        node->setGlyphs(position, run);
        node->setStyle(style);
        node->setStyleColor(styleColor);
        if (explicitAa)
            node->setPreferredAntialiasingMode(aa);
        else if (treat && layout == fontreal_v3::StripeLayout::None)
            node->setPreferredAntialiasingMode(GrayAntialiasing);
        // The packed atlas carries coverage only, so different pen colors share it.
        node->setColor(layout == fontreal_v3::StripeLayout::None ? color : QColor(Qt::white));
        node->update();
        if (layout != fontreal_v3::StripeLayout::None) {
            node->setMaterial(new CoverageMaterial(node->material(), color, dpr));
            node->setFlag(OwnsMaterial);
        }
        appendChildNode(node);
        return node->boundingRect();
    };

    constexpr qsizetype maxGlyphs = (1u << 16) / 4;
    const auto indexes = result.glyphIndexes();
    if (treat && indexes.size() > maxGlyphs) {
        // Keep Qt's 16-bit geometry split in scene graph sync.
        const auto positions = result.positions();
        QRectF bounds;
        for (qsizetype first = 0; first < indexes.size(); first += maxGlyphs) {
            QGlyphRun chunk = result;
            chunk.setGlyphIndexes(indexes.mid(first, maxGlyphs));
            chunk.setPositions(positions.mid(first, maxGlyphs));
            bounds |= add(chunk);
        }
        setBoundingRect(bounds);
    } else {
        setBoundingRect(add(result));
    }
}

namespace {
void *shadow[51]{};
void *renderShadow[33]{};
using RenderFrame = void (*)(QSGDefaultRenderContext *, QSGRenderer *);
RenderFrame stockRenderFrame = nullptr;

void renderFrame(QSGDefaultRenderContext *context, QSGRenderer *renderer)
{
    QScopedValueRollback<QSGRenderer *> scope(currentRenderer, renderer);
    stockRenderFrame(context, renderer);
}

struct UnscalableGlyphs {
    using Member = bool QSGInternalTextNode::*;
    friend Member unscalableGlyphs(UnscalableGlyphs);
};

template<UnscalableGlyphs::Member member>
struct DprInvalidation {
    friend UnscalableGlyphs::Member unscalableGlyphs(UnscalableGlyphs) { return member; }
};

template struct DprInvalidation<&QSGInternalTextNode::m_containsUnscalableGlyphs>;

using CreateTextNode = QSGInternalTextNode *(*)(QSGDefaultContext *, QSGRenderContext *);
CreateTextNode stockTextNode;

QSGInternalTextNode *createTextNode(QSGDefaultContext *context, QSGRenderContext *render)
{
    auto *node = stockTextNode(context, render);
    // The factory can select native glyphs after Qt checks the requested render type.
    if (supportsTreatment(render))
        node->*unscalableGlyphs(UnscalableGlyphs{}) = true;
    return node;
}

using CreateNode = QSGGlyphNode *(*)(QSGDefaultContext *, QSGRenderContext *, QSGTextNode::RenderType, int);
CreateNode stockNode;

QSGGlyphNode *createNode(QSGDefaultContext *context, QSGRenderContext *render,
                        QSGTextNode::RenderType type, int quality)
{
    if (type == QSGTextNode::CurveRendering)
        return stockNode(context, render, type, quality);
    return new ProbeGlyphNode(context, render, type, quality);
}

bool enableDefaultQuick()
{
    auto *quick = dlopen("libQt6Quick.so.6", RTLD_NOLOAD | RTLD_NOW);
    if (!quick)
        return false;
    const auto close = qScopeGuard([&] { dlclose(quick); });
    auto **table = static_cast<void **>(dlsym(quick, "_ZTV17QSGDefaultContext"));
    auto *method = dlsym(quick, "_ZN17QSGDefaultContext15createGlyphNodeEP16QSGRenderContextN11QSGTextNode10RenderTypeEi");
    auto *textMethod = dlsym(quick, "_ZN17QSGDefaultContext22createInternalTextNodeEP16QSGRenderContext");
    Dl_info runtime{};
    void *symbol = nullptr;
    if (!table || !method || !textMethod || !dladdr1(table, &runtime, &symbol, RTLD_DL_SYMENT)
            || static_cast<const ElfW(Sym) *>(symbol)->st_size != sizeof(shadow))
        return false;
    QFile library(QString::fromLocal8Bit(runtime.dli_fname));
    QCryptographicHash sha(QCryptographicHash::Sha256);
    if (!library.open(QIODevice::ReadOnly) || !sha.addData(&library)
        || sha.result().toHex() != "36d8d5518e6479ab710c0ce4e378fcebb59b7bf7b0c277124aabcc8f7bd9c7d4")
        return false;
    auto **slot = reinterpret_cast<void **>(reinterpret_cast<uintptr_t>(runtime.dli_fbase) + 0x781400);
    if (*slot != table)
        return false;
    std::copy_n(table, std::size(shadow), shadow);
    unsigned hits = 0;
    unsigned textHits = 0;
    for (auto &entry : shadow) {
        if (entry == method) {
            entry = reinterpret_cast<void *>(createNode);
            ++hits;
        } else if (entry == textMethod) {
            entry = reinterpret_cast<void *>(createTextNode);
            ++textHits;
        }
    }
    if (hits != 1 || textHits != 1)
        return false;
    stockNode = reinterpret_cast<CreateNode>(method);
    stockTextNode = reinterpret_cast<CreateTextNode>(textMethod);
    auto **renderTable = static_cast<void **>(dlsym(quick, "_ZTV23QSGDefaultRenderContext"));
    auto *render = dlsym(quick, "_ZN23QSGDefaultRenderContext15renderNextFrameEP11QSGRenderer");
    Dl_info renderInfo{};
    void *renderSymbol = nullptr;
    auto **renderSlot = reinterpret_cast<void **>(reinterpret_cast<uintptr_t>(runtime.dli_fbase) + 0x784cf8);
    if (!renderTable || !render || *renderSlot != renderTable
            || !dladdr1(renderTable, &renderInfo, &renderSymbol, RTLD_DL_SYMENT)
            || static_cast<const ElfW(Sym) *>(renderSymbol)->st_size != sizeof(renderShadow))
        return false;
    std::copy_n(renderTable, std::size(renderShadow), renderShadow);
    unsigned renderHits = 0;
    for (auto &entry : renderShadow) {
        if (entry == render) {
            entry = reinterpret_cast<void *>(renderFrame);
            ++renderHits;
        }
    }
    if (renderHits != 1)
        return false;
    stockRenderFrame = reinterpret_cast<RenderFrame>(render);
    const auto pageSize = sysconf(_SC_PAGESIZE);
    if (pageSize <= 0)
        return false;
    const auto replace = [&](void **pointer, void *value) {
        auto *page = reinterpret_cast<void *>(reinterpret_cast<uintptr_t>(pointer) & ~(static_cast<size_t>(pageSize) - 1));
        if (mprotect(page, pageSize, PROT_READ | PROT_WRITE))
            return false;
        __atomic_store_n(pointer, value, __ATOMIC_RELEASE);
        return mprotect(page, pageSize, PROT_READ) == 0;
    };
    if (!replace(renderSlot, renderShadow))
        return false;
    if (!replace(slot, shadow)) {
        replace(renderSlot, renderTable);
        return false;
    }
    return true;
}
}

class FontrealQuickProbe final : public QGenericPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QGenericPluginFactoryInterface" FILE "scenegraph.json")
public:
    QObject *create(const QString &, const QString &) override
    {
        auto *state = new QObject;
        const auto platform = QGuiApplication::platformName();
        const auto scale = qEnvironmentVariable("QT_SCALE_FACTOR");
        const bool nativeScale = (scale.isEmpty() || scale.toDouble() == 1.0)
                && !qEnvironmentVariableIsSet("QT_SCREEN_SCALE_FACTORS")
                && !qEnvironmentVariableIsSet("QT_DEVICE_PIXEL_RATIO")
                && qEnvironmentVariable("QT_ENABLE_HIGHDPI_SCALING") != QStringLiteral("0")
                && QGuiApplication::highDpiScaleFactorRoundingPolicy() == Qt::HighDpiScaleFactorRoundingPolicy::PassThrough;
        nativeWayland.store(nativeScale && (platform == QStringLiteral("wayland")
                || platform == QStringLiteral("wayland-egl")), std::memory_order_relaxed);
        coverageShader = QShader::fromSerialized(QByteArray::fromRawData(
            reinterpret_cast<const char *>(coverage_qsb), coverage_qsb_len));
        const auto refresh = [] {
            const auto screens = QGuiApplication::screens();
            auto grid = OutputGrid::MultipleOrMissing;
            if (screens.size() == 1) {
                grid = fontreal_qt::unrotatedWaylandScreen(screens.first())
                    ? OutputGrid::SingleUnrotated : OutputGrid::Single;
            }
            outputGrid.store(grid, std::memory_order_relaxed);
        };
        const auto watchScreen = [state, refresh](QScreen *screen) {
            connect(screen, &QScreen::orientationChanged, state, refresh);
            connect(screen, &QScreen::geometryChanged, state, refresh);
        };
        for (auto *screen : QGuiApplication::screens())
            watchScreen(screen);
        refresh();
        connect(qGuiApp, &QGuiApplication::screenAdded, state, [watchScreen, refresh](QScreen *screen) {
            watchScreen(screen);
            refresh();
        });
        connect(qGuiApp, &QGuiApplication::screenRemoved, state, refresh);
        qInfo() << "Fontreal Quick default probe active:" << (coverageShader.isValid() && enableDefaultQuick());
        return state;
    }
};

#include "scenegraph.moc"
