#include <QPointF>
#include <execinfo.h>
#include <QFile>
#include <QFileInfo>
#include <QCryptographicHash>
#include <QScopeGuard>
#include <QGenericPlugin>
#include <QDebug>
#include <sys/mman.h>
#include <unistd.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_GLYPH_H
#include FT_SYNTHESIS_H
#include FT_TRUETYPE_TABLES_H
#include FT_FONT_FORMATS_H
#include FT_MODULE_H
#include <QBackingStore>
#include <QCache>
#include <QtGui/private/qfontengineglyphcache_p.h>
#include <QWidget>
#include <QtWidgets/private/qwidget_p.h>
#include <QGuiApplication>
#include <QScreen>
#include <QWindow>
#include <qpa/qplatformscreen.h>
#include <qpa/qplatformwindow.h>
#include <QtGui/private/qfontengine_ft_p.h>
#include "font-engine.h"
#include "fontreal_v3_outline.h"
#include "white-text.h"

extern decltype(&FT_Render_Glyph) probeStockRender;
FT_Error probeRenderGlyph(FT_GlyphSlot, FT_Render_Mode);
#include <QPaintEngine>
#include <QPainter>
#include <QtGui/private/qtextengine_p.h>
#include <QtGui/private/qpaintengine_raster_p.h>
#include <QtGui/private/qstatictext_p.h>
#include <array>
#include <mutex>
#include <unordered_map>
thread_local int fontrealDrawInk = -1;
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <link.h>

static void *fontrealRasterVtable[59] = {};
namespace {
using DrawCached = bool (*)(QRasterPaintEngine *, int, const glyph_t *, const QFixedPoint *, QFontEngine *);
DrawCached stockDrawCached = nullptr;

struct OutlineSample
{
    Frame frame{};
    QImage mask;
    QImage stripes;
    bool directWhite = false;
};

OutlineSample sampleForDraw(QFontEngine *source, glyph_t glyph, QFixedPoint phase, qreal scale, QColor color, fontreal_v3::StripeLayout layout)
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
    OutlineSample result;
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
    result.mask = QImage(result.frame.width, result.frame.height, QImage::Format_Alpha8);
    for (int y = 0; y < result.frame.height; ++y)
        std::copy_n(values.data() + y * result.frame.width, result.frame.width, result.mask.scanLine(y));
    if (layout != StripeLayout::None && ink == Ink::Light) {
        auto &contour = reinterpret_cast<FT_OutlineGlyph>(outline)->outline;
        result.stripes = whiteTextStripes(engine, face, contour, hinted, values, pixels, layout, load);
        result.directWhite = !result.stripes.isNull();
    }
    if (layout != StripeLayout::None && result.stripes.isNull()) {
        const auto tone = toneCurve(pixels, ink);
        result.stripes = QImage(result.frame.width, result.frame.height, QImage::Format_RGB32);
        for (int y = 0; y < result.frame.height; ++y) {
            auto *row = reinterpret_cast<QRgb *>(result.stripes.scanLine(y));
            for (int x = 0; x < result.frame.width; ++x) {
                auto samples = hinted.stripes(x,y,layout);
                for (auto &value : samples)
                    value = tone[value];
                const auto rgb = projectChannels(result.mask.constScanLine(y)[x], samples, ink);
                row[x] = qRgb(rgb[0], rgb[1], rgb[2]);
            }
        }
    }
    return result;
}

using StockStore = QBackingStore *(*)(const QWidget *);
using StockTopLevel = QWidget *(*)(const QWidget *);
using StockAttribute = bool (*)(const QWidget *, Qt::WidgetAttribute);

bool alignedWindow(QRasterPaintEngine *raster, const QWidget *widget)
{
    static const auto backingStore = reinterpret_cast<StockStore>(dlsym(RTLD_DEFAULT, "_ZNK7QWidget12backingStoreEv"));
    static const auto topLevel = reinterpret_cast<StockTopLevel>(dlsym(RTLD_DEFAULT, "_ZNK7QWidget6windowEv"));
    static const auto testAttribute = reinterpret_cast<StockAttribute>(
        dlsym(RTLD_DEFAULT, "_ZNK7QWidget20testAttribute_helperEN2Qt15WidgetAttributeE"));
    if (!backingStore || !topLevel || !testAttribute)
        return false;
    static const bool verifiedWidgets = [] {
        Dl_info info{};
        if (!dladdr(reinterpret_cast<void *>(topLevel), &info) || !info.dli_fname)
            return false;
        QFile file(QString::fromLocal8Bit(info.dli_fname));
        QCryptographicHash sha(QCryptographicHash::Sha256);
        return file.open(QIODevice::ReadOnly) && sha.addData(&file)
            && sha.result().toHex() == "655542813ae4a1a51f42d20930b70e8dda31a3b7873234cce4cf24879ae9a3a2";
    }();
    if (!verifiedWidgets)
        return false;
    auto *store = backingStore(widget);
    auto *top = topLevel(widget);
    auto *window = store ? store->window() : nullptr;
    auto *device = store ? store->paintDevice() : nullptr;
    if (!top || !window || !device || raster->paintDevice() != device || !window->screen()
            || QGuiApplication::screens().size() != 1 || !qFuzzyCompare(window->opacity(), 1.0)
            || testAttribute(top, Qt::WA_DontShowOnScreen))
        return false;
    auto *data = QWidgetPrivate::get(top);
    auto *extra = data->maybeTopData();
    if (!extra || data->usesRhiFlush || !extra->widgetTextures.empty())
        return false;
    const auto platform = QGuiApplication::platformName();
    if (platform == QStringLiteral("xcb")) {
        return qgetenv("XDG_SESSION_TYPE") == "x11"
            && !qEnvironmentVariableIsSet("WAYLAND_DISPLAY")
            && qFuzzyCompare(window->devicePixelRatio(), 1.0)
            && qFuzzyCompare(device->devicePixelRatioF(), 1.0)
            && window->screen()->geometry().contains(window->geometry());
    }
    return (platform == QStringLiteral("wayland") || platform == QStringLiteral("wayland-egl"))
        && window->handle() && window->contentOrientation() == Qt::PrimaryOrientation
        && QGuiApplication::highDpiScaleFactorRoundingPolicy() == Qt::HighDpiScaleFactorRoundingPolicy::PassThrough
        && qFuzzyCompare(window->devicePixelRatio(), window->handle()->devicePixelRatio())
        && qFuzzyCompare(window->devicePixelRatio(), device->devicePixelRatioF());
}

// A QImage does not tell Qt where it will be shown. Check who owns this paint.
enum class BreezeTarget { None, Image, Atlas };

BreezeTarget breezeDecorationTarget()
{
    static const bool isKWin = QCoreApplication::applicationFilePath().endsWith(QStringLiteral("/kwin_wayland"));
    if (!isKWin)
        return BreezeTarget::None;
    static auto *const atlas = dlsym(RTLD_DEFAULT,
        "_ZN4KWin18DecorationRenderer15renderToPainterEP8QPainterRKNS_5RectFE");
    static auto *const image = dlsym(RTLD_DEFAULT,
        "_ZNK4KWin20ItemRendererQPainter10renderItemEP8QPainterPNS_4ItemERKSt8functionIFbS4_EE");
    void *frames[24];
    const int count = backtrace(frames, std::size(frames));
    bool breeze = false;
    for (int i = 1; i < count; ++i) {
        Dl_info address{};
        if (!dladdr(frames[i], &address))
            continue;
        breeze |= address.dli_fname && QByteArrayView(address.dli_fname).endsWith("/org.kde.kdecoration3/org.kde.breeze.so");
        if (breeze && address.dli_saddr) {
            if (address.dli_saddr == atlas)
                return BreezeTarget::Atlas;
            if (address.dli_saddr == image)
                return BreezeTarget::Image;
        }
    }
    return BreezeTarget::None;
}

bool untransformedKWinOutput()
{
    using ActiveOutput = const void *(*)(const void *);
    // KWin 6.6.6 returns OutputTransform as one enum on this build's ABI.
    struct OutputTransform { unsigned kind; };
    using Transform = OutputTransform (*)(const void *);
    static auto *const workspace = static_cast<void *const *>(dlsym(RTLD_DEFAULT, "_ZN4KWin9Workspace5_selfE"));
    static const auto activeOutput = reinterpret_cast<ActiveOutput>(dlsym(RTLD_DEFAULT, "_ZNK4KWin9Workspace12activeOutputEv"));
    static const auto transform = reinterpret_cast<Transform>(dlsym(RTLD_DEFAULT, "_ZNK4KWin13LogicalOutput9transformEv"));
    static const bool knownAbi = [] {
        Dl_info info{};
        return transform && dladdr(reinterpret_cast<void *>(transform), &info)
            && info.dli_fname
            && QFileInfo(QString::fromLocal8Bit(info.dli_fname)).canonicalFilePath().endsWith(QStringLiteral("/libkwin.so.6.6.6"));
    }();
    const auto *output = knownAbi && workspace && *workspace && activeOutput ? activeOutput(*workspace) : nullptr;
    return output && transform(output).kind == 0;
}

QRgb capFringe(QRgb rgb)
{
    constexpr int limit = 32;
    const int red = qRed(rgb), green = qGreen(rgb), blue = qBlue(rgb);
    const int spread = std::max({red, green, blue}) - std::min({red, green, blue});
    if (spread <= limit)
        return rgb;
    const double neutral = .2126 * red + .7152 * green + .0722 * blue;
    const double ratio = double(limit) / spread;
    return qRgb(std::lround(neutral + ratio * (red - neutral)),
                std::lround(neutral + ratio * (green - neutral)),
                std::lround(neutral + ratio * (blue - neutral)));
}

OutlineSample sampleForDraw(QFontEngine *, glyph_t, QFixedPoint, qreal, QColor, fontreal_v3::StripeLayout);

struct MaskKey
{
    glyph_t glyph;
    int x, y;
    qreal scale;
    bool lightInk;
    bool lightRequest;
    fontreal_v3::StripeLayout layout;
    bool operator==(const MaskKey &other) const
    {
        return glyph == other.glyph && x == other.x && y == other.y && scale == other.scale
                && lightInk == other.lightInk && lightRequest == other.lightRequest
                && layout == other.layout;
    }
};

size_t qHash(const MaskKey &key, size_t seed = 0)
{
    return qHashMulti(seed, key.glyph, key.x, key.y, key.scale, key.lightInk, key.lightRequest,
                      static_cast<int>(key.layout));
}

class MaskCache final : public QFontEngineGlyphCache {
public:
    explicit MaskCache(const QFontEngine &engine)
        : QFontEngineGlyphCache(QFontEngine::Format_A8, {}),
          antialias(fontreal_qt::fontconfigAllowsAntialiasing(engine)) { }

    const bool antialias;
    QCache<MaskKey, OutlineSample> masks{128 * 1024};
    std::mutex lock;
};

MaskCache *cacheFor(QFontEngine *engine)
{
    if (!engine->hasInternalCaching())
        return nullptr;
    static const char context = 0;
    static std::mutex attachLock;
    const std::scoped_lock guard(attachLock);
    if (auto *cache = engine->glyphCache(&context, QFontEngine::Format_A8, {}))
        return static_cast<MaskCache *>(cache);
    auto *added = new MaskCache(*engine);
    engine->setGlyphCache(&context, added);
    return added;
}

OutlineSample cachedSample(MaskCache *cache, QFontEngine *engine, glyph_t glyph, QFixedPoint phase,
                           qreal scale, QColor ink, fontreal_v3::StripeLayout layout)
{
    if (!cache)
        return sampleForDraw(engine, glyph, phase, scale, ink, layout);
    const MaskKey key{glyph, phase.x.value(), phase.y.value(), scale, qGray(ink.rgb()) >= 128,
                      engine->fontDef.weight <= QFont::Light, layout};
    {
        const std::scoped_lock guard(cache->lock);
        if (auto *sample = cache->masks.object(key))
            return *sample;
    }
    auto sample = sampleForDraw(engine, glyph, phase, scale, ink, layout);
    const auto cost = sizeof(OutlineSample) + sample.mask.sizeInBytes() + sample.stripes.sizeInBytes();
    const std::scoped_lock guard(cache->lock);
    if (!cache->masks.contains(key))
        cache->masks.insert(key, new OutlineSample(sample), cost);
    return sample;
}

bool drawCached(QRasterPaintEngine *raster, int count, const glyph_t *glyphs,
                const QFixedPoint *positions, QFontEngine *engine)
{
    using fontreal_v3::StripeLayout;
    auto *state = raster->state();
    const QPainter *painter = raster->painter();
    auto *buffer = raster->rasterBuffer();
    const QColor ink = state->pen.color();
    if (!painter || engine->type() != QFontEngine::Freetype || !buffer
            || !ink.isValid() || ink.alpha() == 0 || state->pen.brush().style() != Qt::SolidPattern
            || !(state->renderHints & QPainter::TextAntialiasing)
            || state->matrix.type() > QTransform::TxScale || state->matrix.m22() <= 0
            || !qFuzzyCompare(state->matrix.m11(), state->matrix.m22())
            || state->composition_mode != QPainter::CompositionMode_SourceOver
            || (buffer->format != QImage::Format_RGB32 && buffer->format != QImage::Format_ARGB32_Premultiplied))
        return stockDrawCached(raster, count, glyphs, positions, engine);

    auto *cache = cacheFor(engine);
    if (!(cache ? cache->antialias : fontreal_qt::fontconfigAllowsAntialiasing(*engine)))
        return stockDrawCached(raster, count, glyphs, positions, engine);

    const auto device = painter->device();
    const bool regularWidget = device->devType() == QInternal::Widget
        && engine->glyphFormat == QFontEngine::Format_A32;
    const bool nativeScale = qFuzzyCompare(state->matrix.m22(), device->devicePixelRatioF());
    const auto caption = nativeScale && device->devType() == QInternal::Image
        ? breezeDecorationTarget() : BreezeTarget::None;
    bool alignedCaption = false;
    if (caption != BreezeTarget::None && QGuiApplication::screens().size() == 1) {
        const auto *screen = QGuiApplication::primaryScreen();
        alignedCaption = screen && screen->handle()
            && qFuzzyCompare(screen->handle()->devicePixelRatio(), device->devicePixelRatioF())
            && untransformedKWinOutput();
    }
    auto layout = StripeLayout::None;
    if (nativeScale && painter->opacity() == 1 && state->flags.fast_text && state->penData.alphaRGBBlit) {
        if (alignedCaption || (regularWidget && alignedWindow(raster, static_cast<const QWidget *>(device))))
            layout = fontreal_qt::effectiveLayout(*static_cast<const QFontEngineFT *>(engine));
    }
    QFixedPoint atlasShift;
    if (caption == BreezeTarget::Atlas) {
        // KWin paints at the exact damage origin and uploads at the rounded origin.
        const QPointF origin(-state->matrix.dx(), -state->matrix.dy());
        atlasShift = QFixedPoint::fromPointF(origin - origin.toPoint());
    }
    const bool ySub = engine->supportsVerticalSubPixelPositions()
            && (state->renderHints & QPainter::VerticalSubpixelPositioning);
    const QClipData *clip = raster->clipData();
    for (int i = 0; i < count; ++i) {
        const auto position = positions[i] + atlasShift;
        auto phase = engine->subPixelPositionFor(position);
        if (!ySub)
            phase.y = 0;
        auto masks = cachedSample(cache, engine, glyphs[i], phase, state->matrix.m22(), ink, layout);
        if (masks.mask.isNull()) {
            if (!stockDrawCached(raster, 1, glyphs+i, positions+i, engine))
                return false;
            continue;
        }
        const QPoint topLeft(qFloor(position.x)+masks.frame.left,
                             (ySub ? qFloor(position.y) : qRound(position.y))-masks.frame.top);
        const auto draw = [&](const QImage &mask) {
            raster->alphaPenBlt(mask.constBits(), mask.bytesPerLine(), mask.depth(),
                topLeft.x(), topLeft.y(), mask.width(), mask.height(), false);
        };
        if (!masks.stripes.isNull()) {
            const auto visible = QRect(topLeft, masks.mask.size()).intersected(QRect(0,0,buffer->width(),buffer->height()));
            bool stripes = false;
            for (int y = visible.top(); y <= visible.bottom(); ++y) {
                auto *gray = masks.mask.scanLine(y-topLeft.y());
                auto *channels = reinterpret_cast<QRgb *>(masks.stripes.scanLine(y-topLeft.y()));
                const auto *colors = reinterpret_cast<const QRgb *>(buffer->scanLine(y));
                for (int x = visible.left(); x <= visible.right(); ++x) {
                    const int pos = x-topLeft.x();
                    if ((gray[pos] || masks.directWhite) && qAlpha(colors[x]) == 255 && (!clip || (clip->hasRectClip && clip->clipRect.contains(x,y)))) {
                        if (caption != BreezeTarget::None)
                            channels[pos] = capFringe(channels[pos]);
                        gray[pos] = 0;
                        stripes = true;
                    } else {
                        channels[pos] = qRgb(0,0,0);
                    }
                }
            }
            if (stripes)
                draw(masks.stripes);
        }
        if (clip && !clip->hasRectClip && state->flags.fast_text) {
            // The span compositor applies the clip's fractional alpha.
            state->flags.fast_text = false;
            const auto restore = qScopeGuard([state] { state->flags.fast_text = true; });
            draw(masks.mask);
        } else {
            draw(masks.mask);
        }
    }
    return true;
}
bool swapExperimentPointer(void **slot, void *replacement)
{
    const auto pageSize = static_cast<uintptr_t>(sysconf(_SC_PAGESIZE));
    const auto page = reinterpret_cast<void *>(reinterpret_cast<uintptr_t>(slot) & ~(pageSize-1));
    if (mprotect(page, pageSize, PROT_READ | PROT_WRITE))
        return false;
    __atomic_store_n(slot, replacement, __ATOMIC_RELEASE);
    return !mprotect(page, pageSize, PROT_READ);
}

bool enableForArchivedQt()
{
    const auto gui = dlopen("libQt6Gui.so.6", RTLD_NOLOAD | RTLD_NOW);
    if (!gui)
        return false;
    const auto release = qScopeGuard([=] { dlclose(gui); });
    auto **stock = reinterpret_cast<void **>(dlsym(gui, "_ZTV18QRasterPaintEngine"));
    const auto cached = dlsym(gui, "_ZN18QRasterPaintEngine16drawCachedGlyphsEiPKjPK11QFixedPointP11QFontEngine");
    void *symbol = nullptr;
    Dl_info library{};
    if (!stock || !cached || !dladdr1(stock, &library, &symbol, RTLD_DL_SYMENT)
            || static_cast<ElfW(Sym) *>(symbol)->st_size != sizeof(fontrealRasterVtable))
        return false;

    QFile loaded(QString::fromLocal8Bit(library.dli_fname));
    QCryptographicHash sha(QCryptographicHash::Sha256);
    if (qEnvironmentVariableIsSet("FONTREAL_QUAL_BAD_ABI") || !loaded.open(QIODevice::ReadOnly)
            || !sha.addData(&loaded)
            || sha.result().toHex() != "1cccdc5c19b4d9706f67b928155dc6f46c44799e9fff8ea441de0c6b8a5176c1")
        return false;

    const auto base = reinterpret_cast<uintptr_t>(library.dli_fbase);
    auto **paintSlot = reinterpret_cast<void **>(base + 0x828250);
    if (*paintSlot != stock)
        return false;
    stockDrawCached = reinterpret_cast<DrawCached>(cached);
    std::memcpy(fontrealRasterVtable, stock, sizeof(fontrealRasterVtable));
    unsigned count = 0;
    for (auto &entry : fontrealRasterVtable) {
        if (entry == cached) {
            entry = reinterpret_cast<void *>(drawCached);
            ++count;
        }
    }
    return count == 1 && swapExperimentPointer(paintSlot, fontrealRasterVtable);
}
}


class FontrealPainterProbe final : public QGenericPlugin
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QGenericPluginFactoryInterface" FILE "fontreal-cached-probe.json")
public:
    QObject *create(const QString &key, const QString &) override
    {
        if (key.compare(QStringLiteral("fontreal-cached-probe"), Qt::CaseInsensitive))
            return nullptr;
        qInfo() << "Fontreal painter probe active:" << enableForArchivedQt();
        return new QObject;
    }
};

#include "fontreal-cached-probe.moc"
