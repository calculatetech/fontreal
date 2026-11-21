#include <QPointF>
#include <execinfo.h>
#include <QFile>
#include <QFileInfo>
#include <QCryptographicHash>
#include <QScopeGuard>
#include <QScopedValueRollback>
#include <QGenericPlugin>
#include <QGenericPluginFactory>
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
#include <QPlatformSurfaceEvent>
#include <QQuickWindow>
#include <QCache>
#include <QtGui/private/qfontengineglyphcache_p.h>
#include <QWidget>
#include <QtWidgets/private/qwidget_p.h>
#include <QtQuick/private/qsgsoftwarerenderer_p.h>
#include <QGuiApplication>
#include <QScreen>
#include <QWindow>
#include <qpa/qplatformscreen.h>
#include <qpa/qplatformwindow.h>
#include <QtGui/private/qfontengine_ft_p.h>
#include "font-engine.h"
#include "wayland-output.h"
#include "runtime-build-id.h"
#include "qt-method-table.h"
#include "runtime-abi.h"
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

bool alignedWaylandWindow(const QWindow *window, bool checkOrientation)
{
    return window->handle() && window->contentOrientation() == Qt::PrimaryOrientation
        && (!checkOrientation || fontreal_qt::unrotatedWaylandScreen(window->screen()))
        && qFuzzyCompare(window->devicePixelRatio(), window->handle()->devicePixelRatio());
}

bool alignedWindow(QRasterPaintEngine *raster, const QWidget *widget, bool partialInk, bool fastText)
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
            && sha.result().toHex() == FONTREAL_QT_WIDGETS_SHA;
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
        return fastText && qgetenv("XDG_SESSION_TYPE") == "x11"
            && !qEnvironmentVariableIsSet("WAYLAND_DISPLAY")
            && qFuzzyCompare(window->devicePixelRatio(), 1.0)
            && qFuzzyCompare(device->devicePixelRatioF(), 1.0)
            && window->screen()->geometry().contains(window->geometry());
    }
    return (platform == QStringLiteral("wayland") || platform == QStringLiteral("wayland-egl"))
        && alignedWaylandWindow(window, partialInk)
        && QGuiApplication::highDpiScaleFactorRoundingPolicy() == Qt::HighDpiScaleFactorRoundingPolicy::PassThrough
        && qFuzzyCompare(window->devicePixelRatio(), device->devicePixelRatioF());
}

struct SoftwareFrame {
    QBackingStore *store = nullptr;
    QPaintDevice *device = nullptr;
    qreal dpr = 0;
};

thread_local SoftwareFrame softwareFrame;
std::mutex softwareWindowsMutex;
QHash<QWindow *, qreal> softwareWindows;

using SoftwareRender = void (*)(QSGSoftwareRenderer *);
using SoftwareMarkDirty = void (*)(QSGAbstractSoftwareRenderer *);
using StorePaintDevice = QPaintDevice *(*)(QBackingStore *);
using QuickInterface = QSGRendererInterface *(*)(const QQuickWindow *);
using QuickUpdate = void (*)(QQuickWindow *);
SoftwareRender stockSoftwareRender = nullptr;
SoftwareMarkDirty markSoftwareDirty = nullptr;
StorePaintDevice stockPaintDevice = nullptr;
QuickInterface quickInterface = nullptr;
QuickUpdate quickUpdate = nullptr;

QPaintDevice *softwarePaintDevice(QBackingStore *store)
{
    auto *device = stockPaintDevice(store);
    if (softwareFrame.store == store)
        softwareFrame.device = device;
    return device;
}

struct SoftwareStoreMember {
    using Member = QBackingStore *QSGSoftwareRenderer::*;
    friend Member softwareBackingStore(SoftwareStoreMember);
};

template<SoftwareStoreMember::Member member>
struct SoftwareStoreAccess {
    friend SoftwareStoreMember::Member softwareBackingStore(SoftwareStoreMember) { return member; }
};

template struct SoftwareStoreAccess<&QSGSoftwareRenderer::m_backingStore>;

void renderSoftware(QSGSoftwareRenderer *renderer)
{
    auto *store = renderer->*softwareBackingStore(SoftwareStoreMember{});
    auto *window = store ? store->window() : nullptr;
    const bool redirected = renderer->renderTarget().paintDevice != nullptr;
    qreal dpr = 0;
    if (window && !redirected) {
        const std::scoped_lock lock(softwareWindowsMutex);
        dpr = softwareWindows.value(window);
    }
    const bool present = dpr > 0;

    // A redirect can consume scene updates without painting the window backing store.
    enum PaintMode { Gray, Subpixel, Redirected };
    constexpr auto mode = "_fontrealDirectSoftware";
    const auto next = redirected ? Redirected : (present ? Subpixel : Gray);
    if (window && renderer->property(mode).toInt() != next) {
        renderer->setProperty(mode, int(next));
        if (!redirected)
            markSoftwareDirty(renderer);
    }
    const QScopedValueRollback<SoftwareFrame> frame(softwareFrame, {present ? store : nullptr, nullptr, dpr});
    stockSoftwareRender(renderer);
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
    static auto *const legacyAtlas = dlsym(RTLD_DEFAULT,
        "_ZN4KWin18DecorationRenderer15renderToPainterEP8QPainterRK6QRectF");
    static auto *const alignedAtlas = dlsym(RTLD_DEFAULT,
        "_ZN4KWin18DecorationRenderer6renderEPNS_12ItemRendererERKNS_7RegionFE");
    static auto *const image = dlsym(RTLD_DEFAULT,
        "_ZNK4KWin20ItemRendererQPainter10renderItemEP8QPainterPNS_4ItemERKSt8functionIFbS4_EE");
    static auto *const legacyImage = dlsym(RTLD_DEFAULT,
        "_ZNK4KWin20ItemRendererQPainter10renderItemEP8QPainterPNS_4ItemE");
    static auto *const legacyPreprocess = legacyAtlas && !alignedAtlas ? dlsym(RTLD_DEFAULT,
        "_ZN4KWin14DecorationItem10preprocessEv") : nullptr;
    static auto *const legacyOpenGL = legacyPreprocess ? dlsym(RTLD_DEFAULT,
        "_ZN4KWin18ItemRendererOpenGL10renderItemERKNS_12RenderTargetERKNS_14RenderViewportEPNS_4ItemEiRK7QRegionRKNS_15WindowPaintDataE") : nullptr;
    void *frames[24];
    const int count = backtrace(frames, std::size(frames));
    bool breeze = false;
    bool preprocessed = false;
    for (int i = 1; i < count; ++i) {
        Dl_info address{};
        if (!dladdr(frames[i], &address))
            continue;
        breeze |= address.dli_fname && QByteArrayView(address.dli_fname).endsWith("/org.kde.kdecoration3/org.kde.breeze.so");
        if (breeze && address.dli_saddr) {
            if (address.dli_saddr == atlas || address.dli_saddr == legacyAtlas)
                return BreezeTarget::Atlas;
            // KWin's newer renderer snaps its decoration atlas before painting.
            if (address.dli_saddr == alignedAtlas || address.dli_saddr == image || address.dli_saddr == legacyImage)
                return BreezeTarget::Image;
            // The legacy renderToPainter can tail-call Breeze and leave no stack frame.
            if (preprocessed && address.dli_saddr == legacyOpenGL)
                return BreezeTarget::Atlas;
            preprocessed |= address.dli_saddr == legacyPreprocess;
        }
    }
    return BreezeTarget::None;
}

Dl_info kwinSymbol(const void *address, unsigned type, size_t size)
{
    Dl_info info{};
    void *metadata = nullptr;
    if (!address || !dladdr1(address, &info, &metadata, RTLD_DL_SYMENT)
            || info.dli_saddr != address || !metadata)
        return {};
    const auto *symbol = static_cast<const ElfW(Sym) *>(metadata);
    if (ELF64_ST_TYPE(symbol->st_info) != type || symbol->st_size != size)
        return {};
    return info;
}

bool untransformedKWinOutput()
{
    using ActiveOutput = const void *(*)(const void *);
    struct OutputTransform { unsigned kind; };
    using Transform = OutputTransform (*)(const void *);
    static auto *const workspace = static_cast<void *const *>(dlsym(RTLD_DEFAULT, "_ZN4KWin9Workspace5_selfE"));
    static const auto *active = static_cast<const unsigned char *>(dlsym(RTLD_DEFAULT, "_ZNK4KWin9Workspace12activeOutputEv"));
    static const auto transform = []() -> Transform {
        const auto *logical = static_cast<const unsigned char *>(
            dlsym(RTLD_DEFAULT, "_ZNK4KWin13LogicalOutput9transformEv"));
        if (!logical)
            logical = static_cast<const unsigned char *>(dlsym(RTLD_DEFAULT, "_ZNK4KWin6Output9transformEv"));
        const auto owner = kwinSymbol(workspace, STT_OBJECT, sizeof(*workspace));
        auto module = kwinSymbol(active, STT_FUNC, 5).dli_fbase;
        if (!module)
            module = kwinSymbol(active, STT_FUNC, 9).dli_fbase;
        if (!module || !owner.dli_fbase)
            return nullptr;
        // The executable may own a copy relocation for Workspace::_self.
        if (owner.dli_fbase != module && (!owner.dli_fname
                || QFileInfo(QString::fromLocal8Bit(owner.dli_fname)).canonicalFilePath()
                    != QCoreApplication::applicationFilePath()))
            return nullptr;

        const auto code = [module](const unsigned char *address, size_t size) -> const unsigned char * {
            if (kwinSymbol(address, STT_FUNC, size).dli_fbase == module)
                return address;
            constexpr unsigned char endbr[] = {0xf3, 0x0f, 0x1e, 0xfa};
            if (kwinSymbol(address, STT_FUNC, size + sizeof(endbr)).dli_fbase == module
                    && !std::memcmp(address, endbr, sizeof(endbr)))
                return address + sizeof(endbr);
            return nullptr;
        };
        const auto *pointer = code(active, 5);
        if (!pointer || pointer[0] != 0x48 || pointer[1] != 0x8b || pointer[2] != 0x47 || pointer[4] != 0xc3)
            return nullptr;
        const auto readsTransform = [](const unsigned char *getter) {
            return getter && getter[0] == 0x8b && getter[1] == 0x47 && getter[3] == 0xc3;
        };
        if (readsTransform(code(logical, 4)))
            return reinterpret_cast<Transform>(logical);

        const auto *backend = static_cast<const unsigned char *>(
            dlsym(RTLD_DEFAULT, "_ZNK4KWin13BackendOutput9transformEv"));
        const auto *forward = code(logical, 9);
        if (!readsTransform(code(backend, 4)) || !forward
                || forward[0] != 0x48 || forward[1] != 0x8b || forward[2] != 0x7f || forward[4] != 0xe9)
            return nullptr;
        int32_t displacement;
        std::memcpy(&displacement, forward + 5, sizeof(displacement));
        const auto *target = reinterpret_cast<const unsigned char *>(reinterpret_cast<intptr_t>(forward) + 9 + displacement);
        if (target == backend)
            return reinterpret_cast<Transform>(logical);
        // Some builds forward through a resolved procedure linkage table entry.
        const auto belongs = [module](const void *address, size_t size) {
            Dl_info first{}, last{};
            const auto *bytes = static_cast<const unsigned char *>(address);
            return dladdr(bytes, &first) && dladdr(bytes + size - 1, &last)
                && first.dli_fbase == module && last.dli_fbase == module;
        };
        if (!belongs(target, 6) || target[0] != 0xff || target[1] != 0x25)
            return nullptr;
        std::memcpy(&displacement, target + 2, sizeof(displacement));
        const auto *slot = reinterpret_cast<const void *>(reinterpret_cast<intptr_t>(target) + 6 + displacement);
        const void *resolved = nullptr;
        if (!belongs(slot, sizeof(resolved)))
            return nullptr;
        std::memcpy(&resolved, slot, sizeof(resolved));
        return resolved == backend ? reinterpret_cast<Transform>(logical) : nullptr;
    }();
    const auto *output = transform && *workspace ? reinterpret_cast<ActiveOutput>(active)(*workspace) : nullptr;
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
    const bool finalSoftware = softwareFrame.device && nativeScale && engine->glyphFormat == QFontEngine::Format_A32
        && raster->paintDevice() == softwareFrame.device
        && qFuzzyCompare(softwareFrame.dpr, device->devicePixelRatioF());
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
    const QClipData *clip = raster->clipData();
    const bool partialInk = painter->opacity() < 1 || ink.alphaF() < 1;
    const bool screenClip = clip && (finalSoftware || (regularWidget && partialInk));
    const bool regionClip = screenClip && clip->hasRegionClip;
    // Qt can mark a clip rectangular based on span bounds alone.
    const bool spanClip = screenClip && !regionClip && clip->m_spans && clip->m_clipLines;
    const bool rectangularSpans = spanClip && clip->hasRectClip;
    if (nativeScale && state->penData.alphaRGBBlit && state->penData.type == QSpanData::Solid) {
        const bool fastText = painter->opacity() == 1 && state->flags.fast_text;
        const bool alignedWidget = regularWidget
            && alignedWindow(raster, static_cast<const QWidget *>(device), partialInk, fastText);
        if ((alignedCaption && fastText) || alignedWidget || finalSoftware)
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
            const QRegion region = regionClip ? clip->clipRegion.intersected(visible) : QRegion{};
            auto band = region.cbegin();
            const auto end = region.cend();
            bool stripes = false;
            for (int y = visible.top(); y <= visible.bottom(); ++y) {
                auto *gray = masks.mask.scanLine(y-topLeft.y());
                auto *channels = reinterpret_cast<QRgb *>(masks.stripes.scanLine(y-topLeft.y()));
                const auto *colors = reinterpret_cast<const QRgb *>(buffer->scanLine(y));
                const auto *line = spanClip && y < clip->clipSpanHeight
                    ? &clip->m_clipLines[y] : nullptr;
                // QRegion rectangles are ordered in horizontal bands.
                while (band != end && band->bottom() < y)
                    ++band;
                auto interval = band;
                int span = 0;
                for (int x = visible.left(); x <= visible.right(); ++x) {
                    const int pos = x-topLeft.x();
                    bool fullClipCoverage = !clip || (clip->hasRectClip && clip->clipRect.contains(x,y));
                    if (regionClip) {
                        while (interval != end && interval->top() <= y && interval->right() < x)
                            ++interval;
                        fullClipCoverage = interval != end && interval->top() <= y && x >= interval->left();
                    }
                    if (line) {
                        while (span < line->count && x >= line->spans[span].x + line->spans[span].len)
                            ++span;
                        const int coverage = span < line->count && x >= line->spans[span].x
                            ? line->spans[span].coverage : 0;
                        fullClipCoverage = coverage == 255;
                        // Qt skips the span alpha when it classifies this clip as rectangular.
                        if (rectangularSpans && !fullClipCoverage)
                            gray[pos] = qt_div_255(gray[pos] * coverage);
                    }
                    if ((gray[pos] || masks.directWhite) && qAlpha(colors[x]) == 255 && fullClipCoverage) {
                        if (caption != BreezeTarget::None)
                            channels[pos] = capFringe(channels[pos]);
                        gray[pos] = 0;
                        stripes = true;
                    } else {
                        channels[pos] = qRgb(0,0,0);
                    }
                }
            }
            if (stripes) {
                // Qt's A32 compositor already receives the opacity in the premultiplied pen.
                const bool fastText = state->flags.fast_text;
                state->flags.fast_text = true;
                const auto restore = qScopeGuard([state, fastText] { state->flags.fast_text = fastText; });
                draw(masks.stripes);
            }
        }
        if (clip && (!clip->hasRectClip || spanClip) && state->flags.fast_text) {
            // Keep Qt's grayscale span fallback at the clip edge.
            state->flags.fast_text = false;
            const auto restore = qScopeGuard([state] { state->flags.fast_text = true; });
            draw(masks.mask);
        } else {
            draw(masks.mask);
        }
    }
    return true;
}
bool enableSoftwareQuick(void *module)
{
    auto **table = static_cast<void **>(dlsym(module, "_ZTV19QSGSoftwareRenderer"));
    auto *render = dlsym(module, "_ZN19QSGSoftwareRenderer6renderEv");
    const auto dirty = dlsym(module, "_ZN27QSGAbstractSoftwareRenderer9markDirtyEv");
    const auto paintDevice = dlsym(module, "_ZN13QBackingStore11paintDeviceEv");
    const auto interface = dlsym(module, "_ZNK12QQuickWindow17rendererInterfaceEv");
    const auto update = dlsym(module, "_ZN12QQuickWindow6updateEv");
    Dl_info info{};
    if (!table || !render || !dirty || !paintDevice || !interface || !update
            || !dladdr(table, &info))
        return false;

    static const unsigned char archivedQuick[] = { FONTREAL_QT_QUICK_ID };
    if (!runtimeBuildIdMatches(nullptr, info.dli_fbase, archivedQuick, sizeof(archivedQuick)))
        return false;

    QFile file(QString::fromLocal8Bit(info.dli_fname));
    QCryptographicHash hash(QCryptographicHash::Sha256);
    if (!file.open(QIODevice::ReadOnly) || !hash.addData(&file)
            || hash.result().toHex() != FONTREAL_QT_QUICK_SHA)
        return false;

    const auto base = reinterpret_cast<uintptr_t>(info.dli_fbase);
    auto **slot = fontreal_qt::methodSlot(table, render);
    auto **deviceSlot = reinterpret_cast<void **>(base + FONTREAL_QT_PAINT_DEVICE);
    if (!slot || *deviceSlot != paintDevice)
        return false;
    stockSoftwareRender = reinterpret_cast<SoftwareRender>(render);
    markSoftwareDirty = reinterpret_cast<SoftwareMarkDirty>(dirty);
    stockPaintDevice = reinterpret_cast<StorePaintDevice>(paintDevice);
    // Retain the exact device Qt passes to its painter without re-reading platform window state.
    if (!fontreal_qt::replacePointer(deviceSlot, reinterpret_cast<void *>(softwarePaintDevice)))
        return false;
    if (!fontreal_qt::replacePointer(slot, reinterpret_cast<void *>(renderSoftware))) {
        fontreal_qt::replacePointer(deviceSlot, paintDevice);
        return false;
    }
    quickInterface = reinterpret_cast<QuickInterface>(interface);
    quickUpdate = reinterpret_cast<QuickUpdate>(update);
    return true;
}

bool detectQuick(bool softwareRgb)
{
    auto *module = dlopen("libQt6Quick.so.6", RTLD_NOLOAD | RTLD_NOW);
    if (!module)
        return false;

    const bool active = softwareRgb && enableSoftwareQuick(module);
    if (softwareRgb)
        qInfo() << "Fontreal software Quick probe active:" << active;
    // The installed table calls back into this Qt library for the life of the process.
    if (!active)
        dlclose(module);
    return true;
}

class QuickActivation final : public QObject
{
public:
    QuickActivation()
    {
        if (!observed || quickInterface)
            qGuiApp->installEventFilter(this);
    }

private:
    const bool softwareRgb = fontreal_qt::nativeWaylandScale();
    bool observed = detectQuick(softwareRgb);
    bool watchingScreens = false;

    static bool publish(QWindow *window, qreal dpr)
    {
        const std::scoped_lock lock(softwareWindowsMutex);
        const auto entry = softwareWindows.find(window);
        return entry != softwareWindows.end() && std::exchange(entry.value(), dpr) != dpr;
    }

    static void refresh(QQuickWindow *window)
    {
        const auto screens = QGuiApplication::screens();
        const bool exposed = window->isVisible() && window->isExposed();
        const bool aligned = exposed && screens.size() == 1 && window->screen() == screens.first()
            && qFuzzyCompare(window->opacity(), 1.0) && alignedWaylandWindow(window, true);
        if (publish(window, aligned ? window->devicePixelRatio() : 0) && exposed && window->handle())
            quickUpdate(window);
    }

    void watch(QQuickWindow *window)
    {
        {
            const std::scoped_lock lock(softwareWindowsMutex);
            if (softwareWindows.contains(window))
                return;
            softwareWindows.insert(window, 0);
        }
        const auto refreshWindow = [window] { refresh(window); };
        connect(window, &QWindow::screenChanged, this, refreshWindow);
        connect(window, &QWindow::visibleChanged, this, refreshWindow);
        connect(window, &QWindow::opacityChanged, this, refreshWindow);
        connect(window, &QWindow::contentOrientationChanged, this, refreshWindow);
        connect(window, &QObject::destroyed, this, [window] {
            const std::scoped_lock lock(softwareWindowsMutex);
            softwareWindows.remove(window);
        });
        if (!watchingScreens) {
            watchingScreens = true;
            fontreal_qt::watchScreens(this, [] {
                QList<QWindow *> windows;
                {
                    const std::scoped_lock lock(softwareWindowsMutex);
                    windows = softwareWindows.keys();
                }
                for (auto *window : windows)
                    refresh(static_cast<QQuickWindow *>(window));
            });
        }
    }

    bool eventFilter(QObject *watched, QEvent *event) override
    {
        const auto type = event->type();
        if ((type != QEvent::PlatformSurface && type != QEvent::Expose && type != QEvent::DevicePixelRatioChange)
                || !watched->inherits("QQuickWindow"))
            return false;

        auto *window = static_cast<QQuickWindow *>(watched);
        if (type == QEvent::PlatformSurface) {
            const auto surface = static_cast<QPlatformSurfaceEvent *>(event)->surfaceEventType();
            if (surface == QPlatformSurfaceEvent::SurfaceAboutToBeDestroyed) {
                publish(window, 0);
                return false;
            }
            // The stock loops create the surface before starting a new renderer.
            if (!observed) {
                observed = detectQuick(softwareRgb);
                if (observed) {
                    // At startup the generic plug-in could not select an unmapped Quick library.
                    auto *gpu = QGenericPluginFactory::create(
                        QStringLiteral("fontreal-quick-default-probe"), {});
                    if (gpu)
                        gpu->setParent(this);
                }
            }
            if (!quickInterface) {
                if (observed)
                    qGuiApp->removeEventFilter(this);
                return false;
            }
            const auto *renderer = quickInterface(window);
            if (renderer && renderer->graphicsApi() == QSGRendererInterface::Software)
                watch(window);
        }
        if (quickInterface)
            refresh(window);
        return false;
    }
};

bool enableForArchivedQt()
{
    const auto gui = dlopen("libQt6Gui.so.6", RTLD_NOLOAD | RTLD_NOW);
    if (!gui)
        return false;
    const auto release = qScopeGuard([=] { dlclose(gui); });
    auto **stock = reinterpret_cast<void **>(dlsym(gui, "_ZTV18QRasterPaintEngine"));
    const auto cached = dlsym(gui, "_ZN18QRasterPaintEngine16drawCachedGlyphsEiPKjPK11QFixedPointP11QFontEngine");
    Dl_info library{};
    if (!stock || !cached || !dladdr(stock, &library))
        return false;

    QFile loaded(QString::fromLocal8Bit(library.dli_fname));
    QCryptographicHash sha(QCryptographicHash::Sha256);
    if (qEnvironmentVariableIsSet("FONTREAL_QUAL_BAD_ABI") || !loaded.open(QIODevice::ReadOnly)
            || !sha.addData(&loaded)
            || sha.result().toHex() != FONTREAL_QT_GUI_SHA)
        return false;

    auto **slot = fontreal_qt::methodSlot(stock, cached);
    if (!slot)
        return false;
    stockDrawCached = reinterpret_cast<DrawCached>(cached);
    return fontreal_qt::replacePointer(slot, reinterpret_cast<void *>(drawCached));
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
        const bool active = enableForArchivedQt();
        qInfo() << "Fontreal painter probe active:" << active;
        if (active && fontreal_qt::waylandPlatform())
            return new QuickActivation;
        return new QObject;
    }
};

#include "fontreal-cached-probe.moc"
