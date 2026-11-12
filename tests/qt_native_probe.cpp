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
#include <QHash>
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

Glyph reference(FT_Face face, QChar character, bool mild = false)
{
    require(!FT_Load_Glyph(face, FT_Get_Char_Index(face, character.unicode()),
        FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO | FT_LOAD_NO_BITMAP), "FT load failed");
    require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "FT raster failed");
    const FT_Bitmap &bitmap = face->glyph->bitmap;
    QImage mask(int(bitmap.width), int(bitmap.rows), QImage::Format_RGB32);
    for (int y = 0; y < mask.height(); ++y)
        for (int x = 0; x < mask.width(); ++x) {
            int a = bitmap.buffer[y * bitmap.pitch + x];
            if (mild) a = int(std::lround(255*std::clamp((a-32)/191.0,0.0,1.0)));
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
    int repeats = 1;
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
        for (int i = 0; i < repeats; ++i)
            painter.drawText(QPointF((60+phase)/scale, 48/scale), text);
    }
};

QImage expected(TextWidget &widget, FT_Face face, const QSize &size, bool linear, bool mild, QVector<int> &layers)
{
    QImage image(size, QImage::Format_RGB32);
    layers.fill(0,size.width()*size.height());
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
    for (int repeat = 0; repeat < widget.repeats; ++repeat) {
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
        const Glyph glyph = reference(face, character, mild);
        const int left = int(std::floor(origin + positions[i].x()*scale)) + glyph.left;
        const int top = int(std::lround(48 + (positions[i].y()-line.ascent())*scale)) - glyph.top;
        for (int y = 0; y < glyph.mask.height(); ++y)
            for (int x = 0; x < glyph.mask.width(); ++x) {
                int a = qRed(glyph.mask.pixel(x, y));
                if (a) {
                    int &depth = layers[(top+y)*size.width()+left+x];
                    depth = a == 255 ? 1 : depth+1;
                }
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
    }
    return image;
}

void checkCapture(const QString &path, const QString &menuFont, const QString &terminalFont, bool linear, bool mild, double scale)
{
    const QImage source = QImage(path).convertToFormat(QImage::Format_RGB32);
    require(!source.isNull(), "Cannot read Konsole capture");
    FT_Library library = nullptr;
    require(!FT_Init_FreeType(&library), "Capture FT init failed");
    int matched = 0;
    for (int role = 0; role < 2; ++role) {
        const QRect region = (role == 0 ? QRect(0,0,source.width(),qRound(32*scale))
                                       : QRect(0,qRound(96*scale),source.width(),qRound(286*scale))).intersected(source.rect());
        QHash<QRgb,int> counts;
        for (int y = region.top(); y <= region.bottom(); ++y)
            for (int x = region.left(); x <= region.right(); ++x) ++counts[source.pixel(x,y)];
        QRgb background = 0;
        int count = 0;
        for (auto it = counts.cbegin(); it != counts.cend(); ++it)
            if (it.value() > count) { background = it.key(); count = it.value(); }
        QRgb foreground = background;
        int distance = 0;
        for (auto it = counts.cbegin(); it != counts.cend(); ++it) {
            const QRgb color = it.key();
            const int d = qAbs(qRed(color)-qRed(background))+qAbs(qGreen(color)-qGreen(background))+qAbs(qBlue(color)-qBlue(background));
            if (d > distance) { foreground = color; distance = d; }
        }
        require(distance > 100, "Capture fixture lacks text contrast");
        FT_Face face = nullptr;
        const QString font = role == 0 ? menuFont : terminalFont;
        require(!FT_New_Face(library,QFile::encodeName(font).constData(),0,&face)
            && !FT_Select_Charmap(face,FT_ENCODING_UNICODE) && !FT_Set_Char_Size(face,0,FT_F26Dot6(std::lround(15*scale*64)),72,72), "Capture font setup failed");
        for (QChar character : role == 0 ? QStringLiteral("mnogV") : QStringLiteral("WVwv")) {
            const QImage raw = reference(face,character).mask;
            const QImage adjusted = reference(face,character,true).mask;
            require(raw != adjusted, "Capture glyph does not discriminate contrast");
            const auto pattern = [&](const QImage &mask) {
                QImage image(mask.size(),QImage::Format_RGB32);
                image.fill(background);
                for (int y = 0; y < mask.height(); ++y) for (int x = 0; x < mask.width(); ++x) {
                    const int a = qRed(mask.pixel(x,y));
                    image.setPixel(x,y,qRgb(channel(qRed(foreground),qRed(background),a,linear),
                        channel(qGreen(foreground),qGreen(background),a,linear),channel(qBlue(foreground),qBlue(background),a,linear)));
                }
                return image;
            };
            const QImage wanted = pattern(mild ? adjusted : raw), opposite = pattern(mild ? raw : adjusted);
            const auto error = [&](int left, int top, const QImage &image, int limit) {
                int result = 0;
                for (int y = 0; y < image.height(); ++y) for (int x = 0; x < image.width(); ++x) {
                    const QRgb a = source.pixel(left+x,top+y), b = image.pixel(x,y);
                    result = std::max({result,qAbs(qRed(a)-qRed(b)),qAbs(qGreen(a)-qGreen(b)),qAbs(qBlue(a)-qBlue(b))});
                    if (result > limit) return result;
                }
                return result;
            };
            bool found = false;
            for (int y = region.top(); y+wanted.height() <= region.bottom()+1 && !found; ++y)
                for (int x = region.left(); x+wanted.width() <= region.right()+1 && !found; ++x)
                    if (error(x,y,wanted,1) <= 1 && error(x,y,opposite,1) > 1) found = true;
            require(found, QString("Konsole capture mismatch: role=%1 glyph=%2").arg(role).arg(character));
            ++matched;
        }
        FT_Done_Face(face);
    }
    FT_Done_FreeType(library);
    std::printf("Konsole capture: %d selected glyphs match and reject opposite contrast\n",matched);
}
}

int main(int argc, char **argv)
{
    try {
        QApplication app(argc, argv);
        if ((argc == 7 || argc == 8) && QByteArray(argv[1]) == "--capture") {
            const double scale=argc==8 ? QString::fromLocal8Bit(argv[7]).toDouble() : 1;
            require(scale>0 && std::isfinite(scale), "Invalid capture scale");
            checkCapture(QString::fromLocal8Bit(argv[2]),QString::fromLocal8Bit(argv[3]),QString::fromLocal8Bit(argv[4]),
                         QByteArray(argv[5]) == "linear",QByteArray(argv[6]) == "mild",scale);
            return 0;
        }
        require(argc == 9, "Usage: qt-native-probe expected-mode contrast pixels scale font1 font2 font3 diagnostic-directory");
        const QString mode = QString::fromLocal8Bit(argv[1]);
        const bool enabled = mode == "linear" || mode == "encoded";
        const QString contrast = QString::fromLocal8Bit(argv[2]);
        require(contrast == "none" || contrast == "mild", "Invalid expected contrast");
        const bool mild = contrast == "mild";
        const int pixels = QString::fromLocal8Bit(argv[3]).toInt();
        const double scale = QString::fromLocal8Bit(argv[4]).toDouble();
        const QString diagnostic = QString::fromLocal8Bit(argv[8]);
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
        for (int fontIndex = 5; fontIndex <= 7; ++fontIndex) {
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
            for (QChar character : QStringLiteral("lmnogVwv")) {
                const QImage mask = rawMask(raw, character);
                const QImage oracle = cropMask(reference(face, character, mild).mask);
                if (enabled) require(mask == oracle, "QRawFont mask differs: " + path + " " + character);
                masks.append(QString::fromLatin1(hash(mask)));
            }
            struct TextCase { QString text; int repeats = 1; };
            for (const TextCase &test : QVector<TextCase>{{"l"},{"W"},{"V"},{"w"},{"v"},{"m"},{"n"},{"o"},
                                                       {"g"},{"lllm"},{"WWWV"},{"()"},{" "},{""},{"W",2}}) {
                const QString text = test.text;
                widget.text = text;
                widget.repeats = test.repeats;
                QImage overlapRaw, overlapMild;
                if (enabled && mild && test.repeats == 2) {
                    overlapRaw = reference(face,u'W').mask;
                    overlapMild = reference(face,u'W',true).mask;
                }
                for (double phase : {0., 0.5}) {
                    widget.phase = phase;
                    for (int palette = 0; palette < 3; ++palette) {
                        widget.foreground = palette == 0 ? Qt::black : palette == 1 ? Qt::white : QColor(73, 121, 167);
                        widget.background = palette == 0 ? Qt::white : palette == 1 ? Qt::black : QColor(219, 197, 181);
                        if (!overlapRaw.isNull()) {
                            bool discriminates = false;
                            for (int y = 0; y < overlapRaw.height(); ++y) for (int x = 0; x < overlapRaw.width(); ++x) {
                                const double a = qRed(overlapRaw.pixel(x,y))/255.0;
                                const int b = qRed(overlapMild.pixel(x,y));
                                const int rawCombined = int(std::lround(255*(a+(1-a)*a)));
                                const int after = int(std::lround(255*std::clamp((rawCombined-32)/191.0,0.0,1.0)));
                                const int fg = widget.foreground.red(), bg = widget.background.red();
                                const int twice = channel(fg,channel(fg,bg,b,mode == "linear"),b,mode == "linear");
                                discriminates |= qAbs(twice-channel(fg,bg,after,mode == "linear")) > 4;
                            }
                            require(discriminates, "Overlap fixture cannot distinguish per-glyph ramp ordering");
                        }
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
                            QVector<int> layers;
                            const QImage oracle = expected(widget, face, actual.size(), mode == "linear", mild, layers);
                            int error = 0;
                            bool mismatch = false;
                            for (int y = 0; y < actual.height(); ++y)
                                for (int x = 0; x < actual.width(); ++x) {
                                    QRgb a = actual.pixel(x,y), b = oracle.pixel(x,y);
                                    const int difference = std::max({std::abs(qRed(a)-qRed(b)),
                                        std::abs(qGreen(a)-qGreen(b)),std::abs(qBlue(a)-qBlue(b))});
                                    error = std::max(error,difference);
                                    mismatch |= difference > std::max(1,layers[y*actual.width()+x]);
                                }
                            maximumError = std::max(maximumError, error);
                            // Each overlapping glyph can introduce one byte of composition rounding.
                            if (mismatch) {
                                actual.save(diagnostic + "/actual.png"); oracle.save(diagnostic + "/expected.png");
                                throw std::runtime_error(QString("Widget mismatch: %1 text=%2 px=%3 scale=%4 phase=%5 palette=%6 error=%7 repeats=%8")
                                    .arg(raw.familyName(), text).arg(pixels).arg(scale).arg(phase).arg(palette).arg(error).arg(widget.repeats).toStdString());
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
        QJsonObject result{{"mode",mode}, {"contrast",contrast}, {"pixels",pixels}, {"scale",scale}, {"devicePixels",pixels*scale},
            {"qtGui",guiPath}, {"fonts",fonts}, {"masks",masks}, {"images",cases}, {"checkedImages",checked},
            {"maxChannelError",maximumError}, {"paintEvents",widget.paints}, {"coldLogicalMetricsChecks",metricChecks}};
        std::puts(QJsonDocument(result).toJson(QJsonDocument::Compact).constData());
        return 0;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 2;
    }
}
