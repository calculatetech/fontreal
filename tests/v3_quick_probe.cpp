#include "fontreal_v3_outline.h"

#include <QApplication>
#include <QEventLoop>
#include <QFileInfo>
#include <QFontDatabase>
#include <QImage>
#include <QPixmap>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRawFont>
#include <QScreen>
#include <QSGRectangleNode>
#include <QSGRendererInterface>
#include <QSGTextNode>
#include <QTextLayout>
#include <QTimer>
#include <QtQuick/private/qsgadaptationlayer_p.h>
#include <array>
#include <cstdio>
#include <dlfcn.h>
#include <link.h>
#include FT_GLYPH_H
#include FT_MODULE_H

using namespace fontreal_v3;

constexpr int width = 96;
constexpr int height = 72;
static int fontSize()
{
    return qgetenv("FONTREAL_PROBE_STOCK_STYLE") == "large" ? 60 : 16;
}
const std::array<QPoint, 2> baselines{QPoint(20, 26), QPoint(20, 62)};
static QColor inkColor(bool light)
{
    const bool rich = qEnvironmentVariableIsSet("FONTREAL_PROBE_RICH_INK");
    return light ? (rich ? QColor(231, 238, 245, 224) : QColor(Qt::white))
                 : (rich ? QColor(37, 24, 21, 208) : QColor(Qt::black));
}


static void require(bool condition, const char *message)
{
    if (!condition)
        qFatal("%s", message);
}

static QImage reference(const char *fontFile, qreal scale, StripeLayout layout, bool thin, bool italic)
{
    FT_Library library = nullptr;
    FT_Face face = nullptr;
    FT_Bool noDarkening = true;
    require(!FT_Init_FreeType(&library)
            && !FT_Property_Set(library, "cff", "no-stem-darkening", &noDarkening)
            && !FT_New_Face(library, fontFile, 0, &face)
            && !FT_Set_Char_Size(face, 0, qRound(fontSize() * scale * 64), 0, 0), "reference font");
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
        const auto tone = toneCurve(fontSize() * scale, ink);
        const auto gray = glyphCoverage(hinted, &unhinted, tone, fontSize() * scale, ink, italic);

        for (int y = 0; y < frame.height; ++y) {
            auto *dest = reinterpret_cast<QRgb *>(result.scanLine(baseline.y() - frame.top + y));
            for (int x = 0; x < frame.width; ++x) {
                const Coverage neutral = gray[y * frame.width + x];
                Channels channels{neutral, neutral, neutral};
                if (layout != StripeLayout::None) {
                    auto samples = hinted.stripes(x, y, layout);
                    for (Coverage &sample : samples)
                        sample = tone[sample];
                    channels = projectChannels(neutral, samples, ink);
                }
                if (ink == Ink::Dark) {
                    for (Coverage &channel : channels)
                        channel = 255 - channel;
                }
                const auto foreground = inkColor(ink == Ink::Light);
                const int background = ink == Ink::Light ? 0 : 255;
                const auto blend = [background, foreground](int alpha, int color) {
                    const int blendedAlpha = alpha * foreground.alpha();
                    return (blendedAlpha * color + (65025 - blendedAlpha) * background + 32512) / 65025;
                };
                dest[baseline.x() + frame.left + x] = qRgb(
                    blend(ink == Ink::Light ? channels[0] : 255 - channels[0], foreground.red()),
                    blend(ink == Ink::Light ? channels[1] : 255 - channels[1], foreground.green()),
                    blend(ink == Ink::Light ? channels[2] : 255 - channels[2], foreground.blue()));

            }
        }
    }
    FT_Done_Face(face);
    FT_Done_FreeType(library);
    return result;
}

class Plate : public QQuickItem
{
public:
    Plate(QQuickWindow &window, const QFont &font)
        : QQuickItem(window.contentItem()), m_font(font)
    {
        setFlag(ItemHasContents);
        setSize(QSizeF(::width, ::height));
    }

    bool invert = false;

protected:
    QSGNode *updatePaintNode(QSGNode *node, UpdatePaintNodeData *) override
    {
        if (!node) {
            node = new QSGNode;
            for (int i = 0; i < 2; ++i) {
                m_backgrounds[i] = window()->createRectangleNode();
                m_backgrounds[i]->setRect(QRectF(0, i * ::height / 2, ::width, ::height / 2));
                m_text[i] = window()->createTextNode();
                const bool outline = qgetenv("FONTREAL_PROBE_STOCK_STYLE") == "outline";
                if (outline || !qEnvironmentVariableIsSet("FONTREAL_PROBE_DEFAULT_QML"))
                    m_text[i]->setRenderType(QSGTextNode::NativeRendering);
                if (outline) {
                    m_text[i]->setTextStyle(QSGTextNode::Outline);
                    m_text[i]->setStyleColor(i == 0 ? QColor("#8d442e") : QColor("#b2c9dd"));
                }
                m_text[i]->setColor(inkColor(i != 0));

                QTextLayout layout(QStringLiteral("K"), m_font);
                layout.beginLayout();
                const QTextLine line = layout.createLine();
                layout.endLayout();
                m_text[i]->addTextLayout(baselines[i] - QPointF(0, line.ascent()), &layout);
                require(m_text[i]->childCount() == (outline ? 2 : 1), "unexpected native glyph nodes");
                m_glyphs[i] = static_cast<QSGGlyphNode *>(m_text[i]->lastChild());
                node->appendChildNode(m_backgrounds[i]);
                node->appendChildNode(m_text[i]);
            }
        }
        for (int i = 0; i < 2; ++i) {
            const bool dark = bool(i == 0) != invert;
            m_backgrounds[i]->setColor(dark ? Qt::white : Qt::black);
            m_glyphs[i]->setColor(inkColor(!dark));
        }
        return node;
    }

private:
    QFont m_font;
    std::array<QSGRectangleNode *, 2> m_backgrounds{};
    std::array<QSGTextNode *, 2> m_text{};
    std::array<QSGGlyphNode *, 2> m_glyphs{};
};

static int compare(const char *label, const QImage &image, const QImage &expected)
{
    require(!image.isNull() && image.size() == expected.size(), "capture size");
    int mismatch = 0;
    int grayPixels = 0;
    int colorPixels = 0;
    int maxDelta = 0;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            const QRgb actual = image.pixel(x, y);
            const QRgb want = expected.pixel(x, y);
            const int delta = std::max({qAbs(qRed(actual) - qRed(want)),
                                        qAbs(qGreen(actual) - qGreen(want)),
                                        qAbs(qBlue(actual) - qBlue(want))});
            maxDelta = std::max(maxDelta, delta);
            if (delta > 1) {
                if (mismatch < 5)
                    std::printf("%s (%d,%d) pixels %08x %08x\n", label, x, y, actual, want);
                ++mismatch;
            }
            colorPixels += qRed(actual) != qGreen(actual) || qGreen(actual) != qBlue(actual);
            grayPixels += qRed(actual) > 0 && qRed(actual) < 255;
        }
    }
    std::printf("%s mismatch=%d colored=%d gray=%d max_delta=%d\n",
                label, mismatch, colorPixels, grayPixels, maxDelta);
    return mismatch + (qEnvironmentVariableIsSet("FONTREAL_PROBE_RICH_INK") ? 0 : colorPixels);
}

static void swapPanels(QImage &image)
{
    const QImage first = image.copy(0, 0, image.width(), image.height() / 2);
    const auto stride = image.bytesPerLine();
    for (int y = 0; y < first.height(); ++y) {
        memcpy(image.scanLine(y), image.constScanLine(y + first.height()), stride);
        memcpy(image.scanLine(y + first.height()), first.constScanLine(y), stride);
    }
}

static void frame(QQuickWindow &window)
{
    QEventLoop loop;
    bool received = false;
    const auto signal = QObject::connect(&window, &QQuickWindow::frameSwapped, &loop, [&] {
        received = true;
        loop.quit();
    }, Qt::QueuedConnection);
    QTimer::singleShot(5000, &loop, &QEventLoop::quit);
    window.update();
    loop.exec();
    QObject::disconnect(signal);
    require(received, "no presented OpenGL frame");
}

int main(int argc, char **argv)
{
    QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
    QApplication app(argc, argv);
    require(argc == 3, "font and output prefix required");
    const QString file = QString::fromLocal8Bit(argv[1]);
    require(QFontDatabase::addApplicationFont(file) >= 0, "register font");
    const QRawFont raw(file, fontSize());
    require(raw.isValid(), "raw font");
    QFont font(raw.familyName());
    font.setStyleName(raw.styleName());
    font.setPixelSize(fontSize());
    font.setStyle(raw.style());
    font.setWeight(QFont::Weight(raw.weight()));
    font.setHintingPreference(QFont::PreferFullHinting);
    require(QRawFont::fromFont(font).fontTable("head") == raw.fontTable("head"), "resolved font");

    QQuickWindow window;
    window.setFlags(Qt::FramelessWindowHint | Qt::Window);
    window.setGeometry(40, 40, width, height);
    Plate plate(window, font);
    window.show();
    frame(window);
    require(window.rendererInterface()->graphicsApi() == QSGRendererInterface::OpenGL,
            "OpenGL scene graph");
    const qreal scale = window.devicePixelRatio();
    const qreal configuredScale = qEnvironmentVariable("QT_SCALE_FACTOR").toDouble();
    require(qFuzzyCompare(scale, configuredScale), "window scale");
    std::printf("scale=%.2f api=%d\n", scale, int(window.rendererInterface()->graphicsApi()));

    for (const char *name : {"libQt6Quick.so.6", "libQt6Gui.so.6", "libfreetype.so.6"}) {
        void *handle = dlopen(name, RTLD_LAZY | RTLD_NOLOAD);
        link_map *map = nullptr;
        require(handle && !dlinfo(handle, RTLD_DI_LINKMAP, &map), "library mapping");
        if (qstrcmp(name, "libfreetype.so.6") == 0)
            require(QFileInfo(QString::fromLocal8Bit(map->l_name)).canonicalFilePath()
                            == qEnvironmentVariable("FONTREAL_PROBE_FT"), "official FreeType mapping");
        std::printf("%s\n", map->l_name);
        dlclose(handle);
    }

    const QString output = QString::fromLocal8Bit(argv[2]);
    const bool compareStock = qEnvironmentVariableIsSet("FONTREAL_PROBE_STOCK_STYLE");
    const auto expected = compareStock ? QImage() : reference(argv[1], scale, StripeLayout::None, false, false);
    if (!compareStock)
        require(expected.save(output + "-oracle.png"), "save oracle");
    int total = 0;
    for (int step = 0; step < 3; ++step) {
        plate.invert = step == 1;
        plate.update();
        frame(window);
        const QImage screen = window.screen()->grabWindow(window.winId()).toImage().convertToFormat(QImage::Format_RGB32);
        const QImage buffer = window.grabWindow().convertToFormat(QImage::Format_RGB32);
        require(screen.save(output + QString("-%1-visible.png").arg(step)), "save native surface");
        require(buffer.save(output + QString("-%1-buffer.png").arg(step)), "save Quick readback");
        if (!compareStock) {
            auto match = expected;
            if (plate.invert)
                swapPanels(match);
            total += compare(qPrintable(QString("step %1 visible").arg(step)), screen, match);
            total += compare(qPrintable(QString("step %1 buffer").arg(step)), buffer, match);
        }
    }
    if (compareStock)
        return 0; // The fixture compares these captures with official Qt.
    return qEnvironmentVariable("FONTREAL_RENDERING") == QString("3") ? total != 0 : total == 0;
}
