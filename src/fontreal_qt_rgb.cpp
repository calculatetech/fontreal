#include "fontreal_v3_outline.h"
#include FT_GLYPH_H

#include <QBackingStore>
#include <QGlyphRun>
#include <QImage>
#include <QPainter>
#include <QScreen>
#include <QTextLayout>
#include <QWidget>
#include <QtEndian>

#include <array>
#include <cstdlib>
#include <dlfcn.h>
#include <fontconfig/fontconfig.h>
#include <memory>
#include <optional>

namespace {
using namespace fontreal_v3;

bool launched = false;
thread_local std::optional<Ink> paintInk;

// Restore the caller's preload before Konsole starts any child process.
__attribute__((constructor)) void restorePreload()
{
    const char *previous = std::getenv("FONTREAL_KONSOLE_PILOT_PRELOAD");
    if (!previous)
        return;
    const int result = *previous ? setenv("LD_PRELOAD", previous, 1) : unsetenv("LD_PRELOAD");
    unsetenv("FONTREAL_KONSOLE_PILOT_PRELOAD");
    launched = result == 0;
}

bool sameFace(const QRawFont &a, const QRawFont &b)
{
    if (!a.isValid() || !b.isValid() || a.pixelSize() != b.pixelSize())
        return false;
    if (a == b)
        return true;
    const auto head = a.fontTable("head");
    return !head.isEmpty() && head == b.fontTable("head") && a.fontTable("name") == b.fontTable("name");
}

bool matchFace(FcConfig *config, const QRawFont &face)
{
    using Pattern = std::unique_ptr<FcPattern, decltype(&FcPatternDestroy)>;
    Pattern query(FcPatternCreate(), FcPatternDestroy);
    if (!face.isValid() || !query || !face.fontTable("fvar").isEmpty())
        return false;
    const auto weight = face.fontTable("OS/2");
    if (weight.size() < 6 || qFromBigEndian<quint16>(weight.constData() + 4) <= 350)
        return false;
    // FreeType can auto-hint a TrueType face with no font program and a minimal control program.
    if (!face.fontTable("loca").isEmpty() && face.fontTable("fpgm").isEmpty()
            && face.fontTable("prep").size() <= 7)
        return false;
    const auto name = face.familyName().toUtf8();
    const auto style = face.styleName().toUtf8();
    FcPatternAddString(query.get(), FC_FAMILY, reinterpret_cast<const FcChar8 *>(name.constData()));
    FcPatternAddString(query.get(), FC_STYLE, reinterpret_cast<const FcChar8 *>(style.constData()));
    FcPatternAddDouble(query.get(), FC_PIXEL_SIZE, face.pixelSize());
    FcConfigSubstitute(config, query.get(), FcMatchPattern);
    FcDefaultSubstitute(query.get());
    FcResult result;
    Pattern match(FcFontMatch(config, query.get(), &result), FcPatternDestroy);
    FcChar8 *file = nullptr;
    int index = -1;
    if (!match || FcPatternGetString(match.get(), FC_FILE, 0, &file) != FcResultMatch
            || FcPatternGetInteger(match.get(), FC_INDEX, 0, &index) != FcResultMatch || index != 0)
        return false;
    const auto path = QByteArray(reinterpret_cast<const char *>(file));
    // A raw file load selects face zero. Require that it is the same physical face Qt resolved.
    const QRawFont matched(QString::fromUtf8(path), face.pixelSize(), face.hintingPreference());
    if (!sameFace(face, matched))
        return false;

    // Ask Fontconfig for the selected file and size, as Qt does for its antialias preferences.
    query.reset(FcPatternCreate());
    if (!query)
        return false;
    FcPatternAddString(query.get(), FC_FAMILY, reinterpret_cast<const FcChar8 *>(name.constData()));
    FcPatternAddString(query.get(), FC_FILE, reinterpret_cast<const FcChar8 *>(path.constData()));
    FcPatternAddInteger(query.get(), FC_INDEX, index);
    FcPatternAddDouble(query.get(), FC_PIXEL_SIZE, face.pixelSize());
    FcConfigSubstitute(config, query.get(), FcMatchPattern);
    FcDefaultSubstitute(query.get());
    const auto *fonts = FcConfigGetFonts(config, FcSetSystem);
    for (int i = 0; fonts && i < fonts->nfont; ++i) {
        auto *candidate = fonts->fonts[i];
        FcChar8 *candidateFile = nullptr;
        int candidateIndex = -1;
        double candidateSize = 0;
        if (FcPatternGetString(candidate, FC_FILE, 0, &candidateFile) != FcResultMatch
                || FcPatternGetInteger(candidate, FC_INDEX, 0, &candidateIndex) != FcResultMatch
                || candidateIndex != index || path != reinterpret_cast<const char *>(candidateFile)
                || (FcPatternGetDouble(candidate, FC_PIXEL_SIZE, 0, &candidateSize) == FcResultMatch
                    && candidateSize != face.pixelSize()))
            continue;
        Pattern prepared(FcFontRenderPrepare(config, query.get(), candidate), FcPatternDestroy);
        int rgba = FC_RGBA_UNKNOWN;
        int hint = FC_HINT_NONE;
        FcBool antialias = FcFalse;
        FcBool autohint = FcFalse;
        return prepared && FcPatternGetInteger(prepared.get(), FC_RGBA, 0, &rgba) == FcResultMatch
            && rgba == FC_RGBA_RGB
            && FcPatternGetBool(prepared.get(), FC_ANTIALIAS, 0, &antialias) == FcResultMatch && antialias
            && !(FcPatternGetBool(prepared.get(), FC_AUTOHINT, 0, &autohint) == FcResultMatch && autohint)
            && FcPatternGetInteger(prepared.get(), FC_HINT_STYLE, 0, &hint) == FcResultMatch
            && (hint == FC_HINT_MEDIUM || hint == FC_HINT_FULL);
    }
    return false;
}

bool supportedFace(const QRawFont &face)
{
    struct Entry {
        QRawFont face;
        bool supported = false;
    };
    struct Cache {
        std::unique_ptr<FcConfig, decltype(&FcConfigDestroy)> config{nullptr, FcConfigDestroy};
        std::array<Entry, 4> entries;
        size_t next = 0;
    };
    thread_local Cache cache;
    auto *config = FcConfigGetCurrent();
    if (!config)
        return false;
    if (cache.config.get() != config) {
        cache.entries = {};
        cache.config.reset(FcConfigReference(config));
    }
    for (const auto &entry : cache.entries) {
        if (entry.face == face)
            return entry.supported;
    }
    const bool supported = matchFace(config, face);
    cache.entries[cache.next] = {face, supported};
    cache.next = (cache.next + 1) % cache.entries.size();
    return supported;
}

struct Layout {
    QList<QGlyphRun> runs;
    qreal baseline = 0;
};

Layout shape(const QString &text, const QFont &font, const QPainter &painter)
{
    QTextLayout layout(text, font, painter.device());
    QTextOption option;
    option.setTextDirection(painter.layoutDirection());
    layout.setTextOption(option);
    layout.beginLayout();
    const auto line = layout.createLine();
    layout.endLayout();
    if (!line.isValid() || line.textLength() != text.size())
        return {};
    return {layout.glyphRuns(), line.y() + line.ascent()};
}

QRectF checkedBounds(const QString &text, const QFont &stock, const QFont &keyed, const QPainter &painter)
{
    const auto primary = QRawFont::fromFont(stock);
    const auto keyedPrimary = QRawFont::fromFont(keyed);
    if (stock.families() != QStringList{primary.familyName()} || !sameFace(primary, keyedPrimary)
            || !supportedFace(primary))
        return {};
    const auto original = shape(text, stock, painter);
    const auto candidate = shape(text, keyed, painter);
    if (original.runs.size() != 1 || candidate.runs.size() != 1 || original.baseline != candidate.baseline)
        return {};
    const auto &stockRun = original.runs.front();
    const auto &keyedRun = candidate.runs.front();
    const auto glyphs = stockRun.glyphIndexes();
    const auto positions = stockRun.positions();
    if (stockRun.rawFont() != primary || keyedRun.rawFont() != keyedPrimary
            || glyphs != keyedRun.glyphIndexes() || positions != keyedRun.positions())
        return {};

    QRectF bounds;
    for (qsizetype i = 0; i < glyphs.size(); ++i) {
        const auto box = primary.boundingRect(glyphs[i]);
        if (!box.isEmpty())
            bounds |= box.translated(positions[i] - QPointF(0, original.baseline));
    }
    return bounds;
}

bool solidBehind(const QPainter &painter, const QWidget &widget, const QPointF &origin,
                 const QRectF &bounds, bool light)
{
    const auto transform = painter.deviceTransform();
    auto *store = widget.backingStore();
    const auto *image = store ? dynamic_cast<const QImage *>(store->paintDevice()) : nullptr;
    if (transform.type() > QTransform::TxTranslate || !image || image->devicePixelRatio() != 1
            || image->paintEngine() != painter.paintEngine()
            || (image->format() != QImage::Format_RGB32 && image->format() != QImage::Format_ARGB32_Premultiplied))
        return false;

    // Horizontal LCD filtering can reach beyond the hinted outline's edges.
    const auto region = transform.mapRect(bounds.translated(origin)).toAlignedRect().adjusted(-1, 0, 1, 0);
    if (region.isEmpty() || !image->rect().contains(region))
        return false;

    const QRgb background = light ? qRgb(0, 0, 0) : qRgb(255, 255, 255);
    for (int y = region.top(); y <= region.bottom(); ++y) {
        const auto *row = reinterpret_cast<const QRgb *>(image->constScanLine(y));
        for (int x = region.left(); x <= region.right(); ++x) {
            if (row[x] != background)
                return false;
        }
    }
    return true;
}

bool eligible(const QPainter &painter, const QWidget *widget)
{
    const auto *screen = widget ? widget->screen() : nullptr;
    return widget && widget->inherits("Konsole::TerminalDisplay")
        && QGuiApplication::platformName() == QStringLiteral("wayland")
        && qEnvironmentVariable("XDG_CURRENT_DESKTOP").split(u':').contains(QStringLiteral("KDE"))
        && !qEnvironmentVariableIsSet("QT_SCALE_FACTOR") && !qEnvironmentVariableIsSet("QT_SCREEN_SCALE_FACTORS")
        && screen && QGuiApplication::screens().size() == 1 && screen->devicePixelRatio() == 1
        && screen->orientation() == Qt::LandscapeOrientation
        && screen->primaryOrientation() == Qt::LandscapeOrientation && widget->devicePixelRatioF() == 1
        && painter.font().styleStrategy() == QFont::PreferAntialias
        && painter.font().weight() > QFont::Light
        && painter.font().hintingPreference() == QFont::PreferDefaultHinting
        && painter.pen().brush().style() == Qt::SolidPattern && painter.opacity() == 1
        && painter.compositionMode() == QPainter::CompositionMode_SourceOver
        && painter.testRenderHint(QPainter::TextAntialiasing) && !painter.hasClipping();
}

void replaceCoverage(FT_GlyphSlot slot, FT_Glyph glyph, Ink ink)
{
    const auto &bitmap = slot->bitmap;
    if (bitmap.pixel_mode != FT_PIXEL_MODE_LCD || !bitmap.buffer || !bitmap.width
            || bitmap.width % 3 || !bitmap.rows || bitmap.width > 288 || bitmap.rows > 96
            || bitmap.pitch < int(bitmap.width))
        return;

    const auto samples = sampleOutline(slot->library, reinterpret_cast<FT_OutlineGlyph>(glyph)->outline,
        {slot->bitmap_left, slot->bitmap_top, int(bitmap.width / 3), int(bitmap.rows)});
    if (samples.pixels.empty())
        return;

    const auto tone = toneCurve(slot->face->size->metrics.y_ppem, ink);
    for (int y = 0; y < samples.frame.height; ++y) {
        auto *row = bitmap.buffer + y * bitmap.pitch;
        for (int x = 0; x < samples.frame.width; ++x) {
            auto stripes = samples.stripes(x, y, StripeLayout::Rgb);
            for (auto &stripe : stripes)
                stripe = tone[stripe];
            const auto coverage = projectChannels(tone[samples.center(x, y)], stripes, ink);
            for (int channel = 0; channel < 3; ++channel)
                row[3 * x + channel] = coverage[channel];
        }
    }
}
}

extern "C" FT_Error FT_Render_Glyph(FT_GlyphSlot slot, FT_Render_Mode mode)
{
    static const auto render = reinterpret_cast<decltype(&FT_Render_Glyph)>(dlsym(RTLD_NEXT, "FT_Render_Glyph"));
    if (!render)
        return FT_Err_Unimplemented_Feature;

    FT_Glyph outline = nullptr;
    if (paintInk && mode == FT_RENDER_MODE_LCD && slot && slot->format == FT_GLYPH_FORMAT_OUTLINE
            && slot->face->size && !FT_HAS_COLOR(slot->face) && slot->outline.n_points > 0)
        FT_Get_Glyph(slot, &outline);

    const auto result = render(slot, mode);
    if (outline) {
        if (!result)
            replaceCoverage(slot, outline, *paintInk);
        FT_Done_Glyph(outline);
    }
    return result;
}

// Interpose this public overload, which Konsole uses for direct terminal text.
extern "C" void paintText(QPainter *, const QPointF &, const QString &)
    asm("_ZN8QPainter8drawTextERK7QPointFRK7QString");

extern "C" void paintText(QPainter *painter, const QPointF &origin, const QString &text)
{
    static const auto paint = reinterpret_cast<decltype(&paintText)>(
        dlsym(RTLD_NEXT, "_ZN8QPainter8drawTextERK7QPointFRK7QString"));
    if (!paint)
        std::abort();

    const auto color = painter->pen().color();
    const bool light = color == Qt::white;
    const auto *widget = dynamic_cast<const QWidget *>(painter->device());
    if (!launched || paintInk || (!light && color != Qt::black) || !eligible(*painter, widget)) {
        paint(painter, origin, text);
        return;
    }

    const auto font = painter->font();
    auto keyed = font;
    // TerminalDisplay uses PreferAntialias without either outline flag.
    keyed.setStyleStrategy(QFont::StyleStrategy(QFont::PreferAntialias
                          | (light ? QFont::ForceOutline : QFont::PreferOutline)));
    const auto bounds = checkedBounds(text, font, keyed, *painter);
    if (bounds.isEmpty() || !solidBehind(*painter, *widget, origin, bounds, light)) {
        paint(painter, origin, text);
        return;
    }

    painter->setFont(keyed);
    paintInk = light ? Ink::Light : Ink::Dark;
    paint(painter, origin, text);
    paintInk.reset();
    painter->setFont(font);
}
