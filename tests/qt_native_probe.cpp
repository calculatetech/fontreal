#include <QApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFontDatabase>
#include <QFontMetricsF>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QRawFont>
#include <QWidget>
#include <QTextLayout>
#include <QGlyphRun>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MODULE_H
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <stdexcept>

namespace {
void require(bool ok, const QString &message)
{
    if (!ok) throw std::runtime_error(message.toStdString());
}

QByteArray hash(const QImage &source)
{
    QImage image = source.convertToFormat(QImage::Format_RGB32);
    return QCryptographicHash::hash(
        QByteArrayView(reinterpret_cast<const char *>(image.constBits()), image.sizeInBytes()),
        QCryptographicHash::Sha256).toHex();
}

QImage cropMask(const QImage &source)
{
    int left = source.width(), top = source.height(), right = -1, bottom = -1;
    for (int y = 0; y < source.height(); ++y)
        for (int x = 0; x < source.width(); ++x)
            if (qRed(source.pixel(x, y))) {
                left = std::min(left, x); right = std::max(right, x);
                top = std::min(top, y); bottom = std::max(bottom, y);
            }
    return right < left ? QImage() : source.copy(left, top, right-left+1, bottom-top+1);
}

QImage rawMask(const QRawFont &font, QChar character)
{
    const auto indexes = font.glyphIndexesForString(QString(character));
    require(indexes.size() == 1 && indexes[0], "Missing Qt glyph");
    const QImage alpha = font.alphaMapForGlyph(indexes[0], QRawFont::PixelAntialiasing);
    QImage result(alpha.size(), QImage::Format_RGB32);
    for (int y = 0; y < alpha.height(); ++y)
        for (int x = 0; x < alpha.width(); ++x) {
            int a = qAlpha(alpha.pixel(x, y));
            result.setPixel(x, y, qRgb(a, a, a));
        }
    return cropMask(result);
}

struct Glyph {
    QImage mask;
    int left, top;
};

Glyph reference(FT_Face face, QChar character)
{
    require(!FT_Load_Glyph(face, FT_Get_Char_Index(face, character.unicode()),
        FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO | FT_LOAD_NO_BITMAP), "FT load failed");
    require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "FT raster failed");
    const FT_Bitmap &bitmap = face->glyph->bitmap;
    QImage mask(int(bitmap.width), int(bitmap.rows), QImage::Format_RGB32);
    for (int y = 0; y < mask.height(); ++y)
        for (int x = 0; x < mask.width(); ++x) {
            int a = bitmap.buffer[y * bitmap.pitch + x];
            mask.setPixel(x, y, qRgb(a, a, a));
        }
    return {mask, face->glyph->bitmap_left, face->glyph->bitmap_top};
}

double decode(double x) { return x <= 0.04045 ? x/12.92 : std::pow((x+0.055)/1.055, 2.4); }
double encode(double x) { return x <= 0.0031308 ? x*12.92 : 1.055*std::pow(x, 1/2.4)-0.055; }
int channel(int fg, int bg, int coverage, bool linear)
{
    double f = fg/255., b = bg/255., a = coverage/255.;
    double value = linear ? encode(a*decode(f)+(1-a)*decode(b)) : a*f+(1-a)*b;
    return std::clamp(int(std::lround(value*255)), 0, 255);
}

class TextWidget : public QWidget {
public:
    QFont textFont;
    QFont paintedFont;
    QString text;
    QColor foreground, background;
    double phase = 0;
    int paints = 0;
    void paintEvent(QPaintEvent *) override
    {
        ++paints;
        const double scale = devicePixelRatioF();
        QPainter painter(this);
        painter.fillRect(rect(), background);
        painter.fillRect(QRectF(100/scale, 70/scale, 10/scale, 6/scale), QColor(53, 89, 131));
        painter.setFont(textFont);
        paintedFont = painter.font();
        painter.setPen(foreground);
        // 60 is an exact logical origin at each tested device scale.
        painter.drawText(QPointF((60+phase)/scale, 48/scale), text);
    }
};

QImage expected(TextWidget &widget, FT_Face face, const QSize &size, bool linear)
{
    QImage image(size, QImage::Format_RGB32);
    image.fill(widget.background);
    for (int y = 70; y < 76; ++y)
        for (int x = 100; x < 110; ++x) image.setPixel(x, y, qRgb(53, 89, 131));
    if (widget.text.isEmpty()) return image;
    QTextLayout layout(widget.text, widget.paintedFont);
    layout.beginLayout();
    QTextLine line = layout.createLine();
    line.setLineWidth(10000);
    layout.endLayout();
    const double scale = widget.devicePixelRatioF();
    const double origin = std::floor((60 + widget.phase)/scale*64)/64*scale;
    int characterIndex = 0;
    // Layout is an opaque Qt owner. Raster coverage and composition remain independent.
    for (const QGlyphRun &run : layout.glyphRuns()) {
      const auto positions = run.positions();
      const auto indexes = run.glyphIndexes();
      require(positions.size() == indexes.size(), "Missing Qt layout positions");
      for (int i = 0; i < indexes.size(); ++i) {
        require(characterIndex < widget.text.size(), "Unexpected Qt glyph");
        const QChar character = widget.text.at(characterIndex++);
        require(indexes[i] == FT_Get_Char_Index(face, character.unicode()), "Qt glyph identity changed");
        const Glyph glyph = reference(face, character);
        const int left = int(std::floor(origin + positions[i].x()*scale)) + glyph.left;
        const int top = int(std::lround(48 + (positions[i].y()-line.ascent())*scale)) - glyph.top;
        for (int y = 0; y < glyph.mask.height(); ++y)
            for (int x = 0; x < glyph.mask.width(); ++x) {
                int a = qRed(glyph.mask.pixel(x, y));
                const QRgb bg = image.pixel(left+x, top+y);
                const QColor fg = widget.foreground;
                image.setPixel(left+x, top+y, qRgb(
                    channel(fg.red(), qRed(bg), a, linear),
                    channel(fg.green(), qGreen(bg), a, linear),
                    channel(fg.blue(), qBlue(bg), a, linear)));
            }
      }
    }
    require(characterIndex == widget.text.size(), "Qt layout omitted a requested glyph");
    return image;
}
}

int main(int argc, char **argv)
{
    try {
        require(argc == 7, "Usage: qt-native-probe expected-mode pixels scale font1 font2 diagnostic-directory");
        const QString mode = QString::fromLocal8Bit(argv[1]);
        const bool enabled = mode == "linear" || mode == "encoded";
        const int pixels = QString::fromLocal8Bit(argv[2]).toInt();
        const double scale = QString::fromLocal8Bit(argv[3]).toDouble();
        const QString diagnostic = QString::fromLocal8Bit(argv[6]);
        QApplication app(argc, argv);
        TextWidget widget;
        widget.resize(160, 96);
        widget.show();
        app.processEvents();
        require(widget.devicePixelRatioF() == scale, "Unexpected QWidget device scale");
        FT_Library library = nullptr;
        require(!FT_Init_FreeType(&library), "FT init failed");
        unsigned interpreter = 40;
        require(!FT_Property_Set(library, "truetype", "interpreter-version", &interpreter), "FT property failed");
        QJsonArray cases;
        QJsonArray masks;
        QJsonArray fonts;
        int maximumError = 0, checked = 0, metricChecks = 0;
        for (int fontIndex = 4; fontIndex <= 5; ++fontIndex) {
            const QString path = QString::fromLocal8Bit(argv[fontIndex]);
            const int fontId = QFontDatabase::addApplicationFont(path);
            require(fontId >= 0, "Qt font registration failed");
            QRawFont raw(path, pixels*scale);
            require(raw.isValid(), "Invalid QRawFont");
            QFont font(raw.familyName());
            font.setStyleName(raw.styleName());
            font.setPixelSize(pixels);
            require(QRawFont::fromFont(font).fontTable("head") == raw.fontTable("head"), "Qt selected a different font face");
            QFile fontFile(path);
            require(fontFile.open(QIODevice::ReadOnly), "Cannot read font identity");
            fonts.append(QJsonObject{{"path",path}, {"family",raw.familyName()},
                {"sha256",QString::fromLatin1(QCryptographicHash::hash(fontFile.readAll(), QCryptographicHash::Sha256).toHex())}});
            widget.textFont = font;
            FT_Face face = nullptr;
            require(!FT_New_Face(library, QFile::encodeName(path).constData(), 0, &face), "FT face failed");
            require(!FT_Set_Char_Size(face, 0, FT_F26Dot6(std::lround(pixels*scale*64)), 72, 72), "FT size failed");
            bool coldMetricChecked = false;
            for (QChar character : QStringLiteral("lmnog")) {
                const QImage mask = rawMask(raw, character);
                const QImage oracle = cropMask(reference(face, character).mask);
                if (enabled) require(mask == oracle, "QRawFont mask differs: " + path + " " + character);
                masks.append(QString::fromLatin1(hash(mask)));
            }
            for (const QString &text : {QString("l"), QString("W"), QString("m"), QString("n"), QString("o"),
                                        QString("g"), QString("lllm"), QString()}) {
                widget.text = text;
                for (double phase : {0., 0.5}) {
                    widget.phase = phase;
                    for (int palette = 0; palette < 3; ++palette) {
                        widget.foreground = palette == 0 ? Qt::black : palette == 1 ? Qt::white : QColor(73, 121, 167);
                        widget.background = palette == 0 ? Qt::white : palette == 1 ? Qt::black : QColor(219, 197, 181);
                        widget.repaint();
                        app.processEvents();
                        const QImage actual = widget.grab().toImage().convertToFormat(QImage::Format_RGB32);
                        if (enabled && !coldMetricChecked) {
                            const double advance = QFontMetricsF(widget.paintedFont, &widget).horizontalAdvance(u'W');
                            require(!FT_Set_Char_Size(face, 0, pixels*64, 72, 72), "FT logical size failed");
                            reference(face, u'W');
                            const double hinted = face->glyph->advance.x/64.;
                            const double design = (face->glyph->linearHoriAdvance >> 10)/64.;
                            // Qt selects hinted or design spacing. Both must use the logical size.
                            require(advance == hinted || advance == design,
                                QString("Cold logical W advance changed after scaled raster: Qt=%1 hinted=%2 design=%3 family=%4")
                                    .arg(advance).arg(hinted).arg(design).arg(raw.familyName()));
                            require(!FT_Set_Char_Size(face, 0, FT_F26Dot6(std::lround(pixels*scale*64)), 72, 72), "FT effective size failed");
                            coldMetricChecked = true;
                            ++metricChecks;
                        }
                        const int paintCount = widget.paints;
                        widget.repaint();
                        const QImage cached = widget.grab().toImage().convertToFormat(QImage::Format_RGB32);
                        require(widget.paints > paintCount && actual == cached, "Cached repaint changed pixels");
                        if (enabled) {
                            const QImage oracle = expected(widget, face, actual.size(), mode == "linear");
                            int error = 0;
                            for (int y = 0; y < actual.height(); ++y)
                                for (int x = 0; x < actual.width(); ++x) {
                                    QRgb a = actual.pixel(x,y), b = oracle.pixel(x,y);
                                    error = std::max({error, std::abs(qRed(a)-qRed(b)),
                                        std::abs(qGreen(a)-qGreen(b)), std::abs(qBlue(a)-qBlue(b))});
                                }
                            maximumError = std::max(maximumError, error);
                            if (error > 1) {
                                actual.save(diagnostic + "/actual.png"); oracle.save(diagnostic + "/expected.png");
                                throw std::runtime_error(QString("Widget mismatch: %1 text=%2 px=%3 scale=%4 phase=%5 palette=%6 error=%7")
                                    .arg(raw.familyName(), text).arg(pixels).arg(scale).arg(phase).arg(palette).arg(error).toStdString());
                            }
                            ++checked;
                        }
                        cases.append(QString::fromLatin1(hash(actual)));
                    }
                }
            }
            FT_Done_Face(face);
        }
        FT_Done_FreeType(library);
        QFile maps("/proc/self/maps");
        require(maps.open(QIODevice::ReadOnly), "Cannot inspect Qt mapping");
        QString guiPath;
        for (const QByteArray &line : maps.readAll().split('\n'))
            if (line.contains("/libQt6Gui.so.")) { guiPath = QString::fromUtf8(line.mid(line.indexOf('/'))); break; }
        QJsonObject result{{"mode",mode}, {"pixels",pixels}, {"scale",scale}, {"devicePixels",pixels*scale},
            {"qtGui",guiPath}, {"fonts",fonts}, {"masks",masks}, {"images",cases}, {"checkedImages",checked},
            {"maxChannelError",maximumError}, {"paintEvents",widget.paints}, {"coldLogicalMetricsChecks",metricChecks}};
        std::puts(QJsonDocument(result).toJson(QJsonDocument::Compact).constData());
        return 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 2;
    }
}
