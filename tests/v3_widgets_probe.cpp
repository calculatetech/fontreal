#include "fontreal_v3_outline.h"
#include <QApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <dlfcn.h>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPixmap>
#include <QScreen>
#include <QTest>
#include <QWidget>
#include <QWindow>
#include <array>
#include <cstdio>
#include <cstdlib>
#include FT_GLYPH_H
#include FT_MODULE_H
#include FT_MULTIPLE_MASTERS_H

using namespace fontreal_v3;

constexpr int width = 96;
constexpr int height = 72;
constexpr int fontSize = 16;
const std::array<QPoint, 2> baselines{QPoint(20, 26), QPoint(20, 62)};
const QRect clipControl(21, 12, 3, 52);

static void require(bool condition, const char *message)
{
    if (!condition)
        qFatal("%s", message);
}

static void applyClip(QPainter &painter, int mode = 1)
{
    const bool zeroOnly = mode >= 2;
    QPainterPath nearEdge;
    QPainterPath narrowEdge;
    nearEdge.addRect(zeroOnly ? QRect(10, 12, 3, 52) : clipControl);
    narrowEdge.addRect(zeroOnly ? QRect(40, 12, 3, 52) : clipControl);
    nearEdge.addRect(QRectF(25.02, 12, .02, 52));
    narrowEdge.addRect(QRectF(25.02, 12, .02, 52));
    if (!zeroOnly) {
        nearEdge.addRect(QRectF(28.1, 12, .4, 52));
        narrowEdge.addRect(QRectF(28.1, 12, .4, 52));
    }
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setClipPath(nearEdge, Qt::ReplaceClip);
    painter.setClipPath(narrowEdge, Qt::IntersectClip);
    if (mode == 3) {
        QPainterPath finalEdge;
        finalEdge.addRect(QRectF(25.02, 12, .02, 52));
        painter.setClipPath(finalEdge, Qt::IntersectClip);
        painter.setRenderHint(QPainter::TextAntialiasing, false);
    }
}

static void paint(QPainter &painter, const QFont &font)
{
    painter.fillRect(0, 0, width, height / 2, Qt::white);
    painter.fillRect(0, height / 2, width, height / 2, Qt::black);
    painter.setFont(font);
    if (qEnvironmentVariableIsSet("FONTREAL_PROBE_CLIP"))
        applyClip(painter, qEnvironmentVariableIntValue("FONTREAL_PROBE_CLIP"));
    if (qEnvironmentVariableIsSet("FONTREAL_PROBE_TEXT_AA_OFF"))
        painter.setRenderHint(QPainter::TextAntialiasing, false);
    painter.setPen(Qt::black);
    painter.drawText(baselines[0], QStringLiteral("K"));
    if (qEnvironmentVariableIsSet("FONTREAL_PROBE_OVERLAP"))
        painter.drawText(baselines[0] + QPoint(3, 0), QStringLiteral("K"));
    painter.setPen(Qt::white);
    painter.drawText(baselines[1], QStringLiteral("K"));
    if (qEnvironmentVariableIsSet("FONTREAL_PROBE_OVERLAP"))
        painter.drawText(baselines[1] + QPoint(3, 0), QStringLiteral("K"));
}

class ProbeWidget : public QWidget
{
public:
    explicit ProbeWidget(const QFont &font) : m_font(font)
    {
        setAttribute(Qt::WA_OpaquePaintEvent);
        resize(::width, ::height);
        move(40, 40);
    }

    QImage intermediate;
    int paintCount = 0;

protected:
    void paintEvent(QPaintEvent *) override
    {
        ++paintCount;
        const qreal scale = devicePixelRatioF();
        intermediate = QImage(QSize(qRound(::width * scale), qRound(::height * scale)),
                              QImage::Format_RGB32);
        intermediate.setDevicePixelRatio(scale);
        {
            QPainter offscreen(&intermediate);
            paint(offscreen, m_font);
        }
        QPainter window(this);
        paint(window, m_font);
    }

private:
    QFont m_font;
};

static QImage reference(const char *fontFile, qreal scale, StripeLayout layout, bool thin, bool italic)
{
    FT_Library library = nullptr;
    FT_Face face = nullptr;
    FT_Bool noDarkening = true;
    require(!FT_Init_FreeType(&library)
            && !FT_Property_Set(library, "cff", "no-stem-darkening", &noDarkening)
            && !FT_New_Face(library, fontFile, 0, &face)
            && !FT_Set_Char_Size(face, 0, qRound(fontSize * scale * 64), 0, 0), "reference font");
    const int designWeight = qEnvironmentVariableIntValue("FONTREAL_PROBE_WEIGHT");
    if (designWeight > 0 && FT_HAS_MULTIPLE_MASTERS(face)) {
        FT_MM_Var *axes = nullptr;
        require(!FT_Get_MM_Var(face, &axes), "reference variation axes");
        std::vector<FT_Fixed> coordinates(axes->num_axis);
        for (FT_UInt i = 0; i < axes->num_axis; ++i)
            coordinates[i] = axes->axis[i].tag == FT_MAKE_TAG('w', 'g', 'h', 't')
                ? designWeight * 65536L : axes->axis[i].def;
        require(!FT_Set_Var_Design_Coordinates(face, axes->num_axis, coordinates.data()), "reference weight axis");
        FT_Done_MM_Var(library, axes);
    }
    const int flags = FT_LOAD_NO_BITMAP | FT_LOAD_NO_AUTOHINT | FT_LOAD_TARGET_NORMAL;
    QImage result(qRound(width * scale), qRound(height * scale), QImage::Format_RGB32);
    result.fill(Qt::white);
    for (int y = qRound(height * scale / 2); y < result.height(); ++y)
        std::fill_n(reinterpret_cast<QRgb *>(result.scanLine(y)), result.width(), qRgb(0, 0, 0));

    for (int polarity = 0; polarity < 2; ++polarity) {
        const QPoint baseline(qRound(baselines[polarity].x() * scale),
                              qRound(baselines[polarity].y() * scale));
        FT_Set_Transform(face, nullptr, nullptr);
        FT_Glyph outline = nullptr;
        require(!FT_Load_Char(face, 'K', flags) && !FT_Get_Glyph(face->glyph, &outline)
                && outline->format == FT_GLYPH_FORMAT_OUTLINE
                && !FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "reference raster");
        const FT_GlyphSlot slot = face->glyph;
        const GlyphFrame frame{slot->bitmap_left, slot->bitmap_top, int(slot->bitmap.width),
                               int(slot->bitmap.rows)};
        const auto hinted = sampleOutline(library, reinterpret_cast<FT_OutlineGlyph>(outline)->outline,
                                          frame);
        FT_Done_Glyph(outline);
        OutlineSamples unhinted;
        if (thin) {
            require(!FT_Load_Char(face, 'K', flags | FT_LOAD_NO_HINTING), "reference thin outline");
            unhinted = sampleOutline(library, slot->outline, frame);
        }
        const auto ink = polarity == 0 ? Ink::Dark : Ink::Light;
        const auto tone = toneCurve(fontSize * scale, ink);
        const auto gray = glyphCoverage(hinted, &unhinted, tone, fontSize * scale, ink, italic);

        const bool overlap = qEnvironmentVariableIsSet("FONTREAL_PROBE_OVERLAP");
        const int foreground = ink == Ink::Dark ? 0 : 255;
        const QRgb background = qRgb(255 - foreground, 255 - foreground, 255 - foreground);
        for (int offset : {0, qRound(3 * scale)}) {
            if (offset && !overlap)
                break;
            for (int y = 0; y < frame.height; ++y) {
                auto *dest = reinterpret_cast<QRgb *>(result.scanLine(baseline.y() - frame.top + y));
                for (int x = 0; x < frame.width; ++x) {
                    QRgb &pixel = dest[baseline.x() + frame.left + x + offset];
                    const Coverage neutral = gray[y * frame.width + x];
                    Channels channels{neutral, neutral, neutral};
                    if (layout != StripeLayout::None && pixel == background) {
                        auto samples = hinted.stripes(x, y, layout);
                        for (Coverage &sample : samples)
                            sample = tone[sample];
                        channels = projectChannels(neutral, samples, ink);
                    }
                    const auto blend = [foreground](int value, int alpha) {
                        return (value * (255 - alpha) + foreground * alpha + 127) / 255;
                    };
                    pixel = qRgb(blend(qRed(pixel), channels[0]), blend(qGreen(pixel), channels[1]),
                                 blend(qBlue(pixel), channels[2]));
                }
            }
        }
    }
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return result;
}

static int compare(const char *target, const QImage &image, const QImage &expected)
{
    require(!image.isNull() && image.size() == expected.size(), "capture size");
    int mismatch = 0;
    int colorPixels = 0;
    int partial = 0;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            QRgb actual = image.pixel(x, y);
            QRgb wanted = expected.pixel(x, y);
            if (actual != wanted) {
                if (mismatch < 3)
                    std::printf("%s (%d, %d) actual=%08x expected=%08x\n", target, x, y, actual, wanted);
                ++mismatch;
            }
            colorPixels += qRed(actual) != qGreen(actual) || qGreen(actual) != qBlue(actual);
            partial += actual != qRgb(0, 0, 0) && actual != qRgb(255, 255, 255);
        }
    }
    std::printf("%s mismatch=%d color=%d partial=%d\n", target, mismatch, colorPixels, partial);
    return mismatch;
}

static void compareThinReference(const char *fontFile, const QImage &image, bool italic)
{
    // These fixtures use the source font bytes and the approved independent NumPy
    // alignment, bridge, and centerline model at 12 points and 96 DPI.
    const char *fontHash = italic
        ? "ed722e6c2996b08e8516d27a7c017972cfabf5d1736b496b6526da78fd17691a"
        : "09a73dc31624ae9e759fd1187c8cbf37e320a74ce8d931d1ae0f735b0e41a2e5";
    const char *expected = italic
        ? "20ace58f266c9b8565377a044b20b247e106c05205c6465e1a92a92fe926f30d"
        : "281411a8cbb1f58bf54fa3bf76efc30a07b1c00900e77ad7b12395cbb4c18abe";
    QFile font(QString::fromUtf8(fontFile));
    require(font.open(QIODevice::ReadOnly), "open thin fixture font");
    require(QCryptographicHash::hash(font.readAll(), QCryptographicHash::Sha256).toHex() == fontHash,
            "thin fixture font differs from independent reference input");
    const auto gray = image.convertToFormat(QImage::Format_Grayscale8);
    const QByteArrayView bytes(reinterpret_cast<const char *>(gray.constBits()), gray.sizeInBytes());
    require(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex() == expected,
            "thin fixture differs from independent NumPy coverage");
}

static void requireMono(const QImage &image)
{
    bool sawInk[] = {false, false};
    for (int y = 0; y < image.height(); ++y) {
        const int panel = y >= image.height() / 2;
        const QRgb background = panel ? qRgb(0, 0, 0) : qRgb(255, 255, 255);
        const QRgb foreground = panel ? qRgb(255, 255, 255) : qRgb(0, 0, 0);
        for (int x = 0; x < image.width(); ++x) {
            const QRgb pixel = image.pixel(x, y);
            require(pixel == background || pixel == foreground, "AA veto produced a partial pixel");
            sawInk[panel] |= pixel == foreground;
        }
    }
    require(sawInk[0] && sawInk[1], "AA veto lost glyphs");
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    require(argc == 9, "layout mode family style file thin italic image-prefix");
    const QByteArray expectedFreeType = qgetenv("FONTREAL_PROBE_FT");
    Dl_info library = {};
    require(dladdr(dlsym(RTLD_DEFAULT, "FT_Init_FreeType"), &library) != 0,
            "could not resolve FreeType provider");
    const QByteArray mapped = QFileInfo(QString::fromUtf8(library.dli_fname)).canonicalFilePath().toUtf8();
    require(mapped == expectedFreeType, "FreeType symbol provider has the wrong identity");
    QFile maps(QStringLiteral("/proc/self/maps"));
    require(maps.open(QIODevice::ReadOnly), "could not read loaded mappings");
    int freeTypeMappings = 0;
    for (const auto &line : maps.readAll().split('\n')) {
        if (line.contains("/libfreetype.so.")) {
            require(line.endsWith(expectedFreeType), "multiple FreeType libraries mapped");
            ++freeTypeMappings;
        }
    }
    require(freeTypeMappings != 0, "no FreeType image mapped");
    std::printf("Mapped FreeType %s (%d segments)\n", mapped.constData(), freeTypeMappings);
    const auto layout = StripeLayout(std::atoi(argv[1]));
    const QString mode = QString::fromUtf8(argv[2]);
    QFont font(QString::fromUtf8(argv[3]));
    if (*argv[4])
        font.setStyleName(QString::fromUtf8(argv[4]));
    font.setPixelSize(fontSize);
    font.setHintingPreference(QFont::PreferFullHinting);
    const int designWeight = qEnvironmentVariableIntValue("FONTREAL_PROBE_WEIGHT");
    if (designWeight > 0)
        font.setVariableAxis(QFont::Tag("wght"), designWeight);
    if (mode == "app-mono")
        font.setStyleStrategy(QFont::NoAntialias);
    else if (mode == "app-gray")
        font.setStyleStrategy(QFont::NoSubpixelAntialias);

    if (mode == "float-clip" || mode == "float-native" || mode == "float-reference") {
        const bool nativeTrueType = qEnvironmentVariableIsSet("FONTREAL_PROBE_TEXT_AA_OFF");
        QImage target(width, height, QImage::Format_RGBA32FPx4_Premultiplied);
        for (int y = 0; y < height; ++y) {
            auto *row = reinterpret_cast<float *>(target.scanLine(y));
            for (int x = 0; x < width; ++x) {
                row[4 * x] = mode == "float-reference" ? 1.0f : 1.5f;
                row[4 * x + 1] = 0.5f;
                row[4 * x + 2] = 0.25f;
                row[4 * x + 3] = 1.0f;
            }
        }
        const auto draw = [&](QImage image, const QRegion &clip) {
            QPainter painter(&image);
            if (!clip.isEmpty())
                painter.setClipRegion(clip);
            painter.setFont(font);
            if (mode != "float-clip" || nativeTrueType)
                painter.setRenderHint(QPainter::TextAntialiasing, false);
            painter.drawText(baselines[0], QStringLiteral("K"));
            painter.end();
            return image;
        };
        const QRegion mainClip(QRect(19, 12, 20, 18));
        const QImage rectangular = draw(target, mainClip);
        if (nativeTrueType || mode != "float-clip") {
            QFile bytes(QString::fromUtf8(argv[8]) + ".rgba32f");
            require(bytes.open(QIODevice::WriteOnly)
                    && bytes.write(reinterpret_cast<const char *>(rectangular.constBits()),
                                   rectangular.sizeInBytes()) == rectangular.sizeInBytes(),
                    "write float native fixture");
            if (mode != "float-clip")
                return 0;
        }
        const QImage complex = draw(target, mainClip | QRect(20, 48, 16, 16));
        target = draw(target, {});
        require(rectangular == complex && complex == target, "HDR glyph pixels depend on remote clip shape");
        const auto gray = reference(argv[5], 1, StripeLayout::None, false, false);
        int untouched = 0;
        int drawn = 0;
        for (int y = 14; y < 26; ++y) {
            const auto *row = reinterpret_cast<const float *>(target.constScanLine(y));
            for (int x = 22; x < 34; ++x) {
                if (qRed(gray.pixel(x, y)) == 255) {
                    require(row[4 * x] == 1.5f, "clipped glyph clamped an untouched HDR pixel");
                    ++untouched;
                } else if (row[4 * x] < 1.5f) {
                    ++drawn;
                }
            }
        }
        require(untouched && drawn, "HDR clip fixture lacks both pixel outcomes");
        return 0;
    }

    ProbeWidget widget(font);
    widget.show();
    require(QTest::qWaitForWindowExposed(&widget), "no exposed window");
    QTest::qWait(100);
    const auto capture = [&] {
        return widget.screen()->grabWindow(widget.winId()).toImage().convertToFormat(QImage::Format_RGB32);
    };
    const auto window = capture();
    const QImage firstIntermediate = widget.intermediate;
    const int firstPaintCount = widget.paintCount;
    widget.repaint();
    QTest::qWait(25);
    require(widget.paintCount > firstPaintCount, "repaint did not run");
    require(window == capture() && firstIntermediate == widget.intermediate,
            "repaint changed the native or nested pixels");
    const int fullPaintCount = widget.paintCount;
    const int dirtyX = qEnvironmentVariableIsSet("FONTREAL_PROBE_OVERLAP") ? 31 : 24;
    const QRegion dirty = QRegion(QRect(dirtyX, 12, 3, 15)) | QRegion(QRect(dirtyX, 48, 3, 15));
    widget.repaint(dirty);
    QTest::qWait(25);
    require(widget.paintCount > fullPaintCount, "partial repaint did not run");
    require(window == capture() && firstIntermediate == widget.intermediate,
            "partial and full repaint pixels differ");
    const qreal scale = widget.devicePixelRatioF();
    std::printf("Qt %s, platform %s, DPR %g, font %s %s\n", qVersion(), qPrintable(app.platformName()),
                scale, qPrintable(QFontInfo(font).family()), qPrintable(QFontInfo(font).styleName()));
    require(!window.isNull() && !widget.intermediate.isNull(), "missing captures");
    if (*argv[8]) {
        require(window.save(QString::fromUtf8(argv[8]) + "-window.png"), "window write");
        require(widget.intermediate.save(QString::fromUtf8(argv[8]) + "-intermediate.png"), "image write");
    }
    if (mode == "app-mono" || mode == "system-mono") {
        requireMono(window);
        requireMono(widget.intermediate);
        std::puts("window and nested image contain both glyphs and binary coverage");
        return 0;
    }
    if (mode == "stock")
        return 0;
    if (mode == "clip-zero") {
        const auto uncut = reference(argv[5], 1, StripeLayout::None, false, false);
        int witness[2]{};
        for (int y = 0; y < height; ++y) {
            const int polarity = y >= height / 2;
            const QRgb background = polarity ? qRgb(0, 0, 0) : qRgb(255, 255, 255);
            witness[polarity] += uncut.pixel(25, y) != background;
            for (int x = 0; x < width; ++x) {
                require(window.pixel(x, y) == background && widget.intermediate.pixel(x, y) == background,
                        "the zero-only clip changed a background pixel");
            }
        }
        require(witness[0] && witness[1], "fixture lacks glyph coverage inside the zero-only clip");
        return 0;
    }
    if (mode == "clip") {
        const auto expected = reference(argv[5], 1, layout, false, false);
        const auto gray = reference(argv[5], 1, StripeLayout::None, false, false);
        QImage clipMask(width, height, QImage::Format_RGB32);
        clipMask.fill(Qt::black);
        {
            QPainter clipPainter(&clipMask);
            applyClip(clipPainter);
            clipPainter.fillRect(clipMask.rect(), Qt::white);
        }
        require(qRed(clipMask.pixel(25, 16)) == 0, "fixture lacks a zero-coverage clip");
        const int fractional = qRed(clipMask.pixel(28, 16));
        require(fractional > 0 && fractional < 255, "fixture lacks a fractional clip");
        int coloredControlPixels = 0;
        int grayControlPixels = 0;
        for (int y = 0; y < height; ++y) {
            for (int x = 0; x < width; ++x) {
                const QRgb pixel = window.pixel(x, y);
                if (clipControl.contains(x, y)) {
                    require(pixel == expected.pixel(x, y), "full clip span did not retain its RGB coverage");
                    coloredControlPixels += qRed(pixel) != qGreen(pixel) || qGreen(pixel) != qBlue(pixel);
                } else if (x == 28 && y >= 12 && y < 64) {
                    const int background = y < height / 2 ? 255 : 0;
                    const int neutral = qRed(gray.pixel(x, y));
                    const int clip = qRed(clipMask.pixel(x, y));
                    const int expectedValue = (clip * neutral + (255 - clip) * background + 127) / 255;
                    const QRgb expectedGray = qRgb(expectedValue, expectedValue, expectedValue);
                    require(pixel == expectedGray && widget.intermediate.pixel(x, y) == expectedGray,
                            "partial clip did not apply its coverage to the grayscale mask");
                    grayControlPixels += expectedValue != background && expectedValue != neutral;
                } else {
                    const QRgb background = y < height / 2 ? qRgb(255, 255, 255) : qRgb(0, 0, 0);
                    require(pixel == background && widget.intermediate.pixel(x, y) == background,
                            "zero-coverage clip changed a background pixel");
                }
            }
        }
        require(coloredControlPixels > 0 && grayControlPixels > 0, "clip fixture lacks a visible control");
        return 0;
    }

    const bool thin = std::atoi(argv[6]);
    const bool italic = std::atoi(argv[7]);
    if (thin && (designWeight == 0 || mode == "ignored-axis"))
        compareThinReference(argv[5], widget.intermediate, italic);
    if (thin || designWeight > 0)
        require(widget.intermediate != reference(argv[5], scale, StripeLayout::None, !thin, italic),
                "fixture did not distinguish the thin-stroke path");
    const auto windowLayout = mode == "app-gray" || scale != 1 ? StripeLayout::None : layout;
    int mismatch = compare("window", window, reference(argv[5], scale, windowLayout, thin, italic));
    mismatch += compare("nested RGB32 image", widget.intermediate,
                        reference(argv[5], scale, StripeLayout::None, thin, italic));
    return mismatch ? 1 : 0;
}
