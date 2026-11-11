#include "experiment.h"
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QPainter>
#include <QPainterPath>
#include <QProcess>
#include <QSaveFile>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_FONT_FORMATS_H
#include FT_LCD_FILTER_H
#include FT_MODULE_H
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace {
void require(bool valid, const QString &message)
{
    if (!valid) throw std::runtime_error(message.toStdString());
}

void ftCheck(FT_Error error, const char *operation)
{
    require(!error, QString("%1 failed (FreeType error %2)").arg(operation).arg(error));
}

struct FreeType {
    FT_Library library = nullptr;
    FT_Face face = nullptr;
    FreeType() { ftCheck(FT_Init_FreeType(&library), "Initialize FreeType"); }
    ~FreeType() { if (face) FT_Done_Face(face); FT_Done_FreeType(library); }
    FreeType(const FreeType &) = delete;
    FreeType &operator=(const FreeType &) = delete;
};

struct Mode {
    const char *id, *name;
    unsigned interpreter;
    FT_Int32 flags;
    FT_Render_Mode render;
    int low = 0, high = 255;
};

const QVector<Mode> modes = {
    {"legacy-mono", "TT35 mono hints / binary", 35, FT_LOAD_TARGET_MONO, FT_RENDER_MODE_MONO},
    {"legacy-gray", "TT35 mono hints / gray edges", 35, FT_LOAD_TARGET_MONO, FT_RENDER_MODE_NORMAL},
    {"auto-gray", "Auto mono hints / gray edges", 40, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO, FT_RENDER_MODE_NORMAL},
    {"native-gray", "TT40 normal / grayscale", 40, FT_LOAD_TARGET_NORMAL, FT_RENDER_MODE_NORMAL},
    {"light-gray", "TT40 light / grayscale", 40, FT_LOAD_TARGET_LIGHT, FT_RENDER_MODE_NORMAL},
    {"unhinted-gray", "Unhinted / grayscale", 40, FT_LOAD_NO_HINTING, FT_RENDER_MODE_NORMAL},
    {"lcd", "TT40 LCD / default RGB filter", 40, FT_LOAD_TARGET_LCD, FT_RENDER_MODE_LCD},
};

const QVector<Mode> edgeModes = {
    {"auto-gray", "Auto mono hints / gray edges", 40, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO, FT_RENDER_MODE_NORMAL},
    {"edge-mild", "Gray edges / mild contrast", 40, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO, FT_RENDER_MODE_NORMAL, 32, 223},
    {"edge-strong", "Gray edges / strong contrast", 40, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO, FT_RENDER_MODE_NORMAL, 64, 191},
    {"auto-mono", "Auto mono hints / binary", 40, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO, FT_RENDER_MODE_MONO},
};

struct Glyph {
    int x = 0, top = 0;
    QImage coverage;
};

QImage bitmapImage(const FT_Bitmap &bitmap)
{
    const bool lcd = bitmap.pixel_mode == FT_PIXEL_MODE_LCD;
    const int width = lcd ? int(bitmap.width) / 3 : int(bitmap.width);
    if (!width || !bitmap.rows) return {};
    require(lcd || bitmap.pixel_mode == FT_PIXEL_MODE_GRAY || bitmap.pixel_mode == FT_PIXEL_MODE_MONO,
            "Unsupported FreeType bitmap format");
    QImage image(width, int(bitmap.rows), QImage::Format_RGB32);
    for (int y = 0; y < image.height(); ++y) {
        const auto *row = bitmap.buffer + (bitmap.pitch >= 0 ? y : image.height() - 1 - y) * std::abs(bitmap.pitch);
        auto *out = reinterpret_cast<QRgb *>(image.scanLine(y));
        for (int x = 0; x < width; ++x) {
            if (lcd) out[x] = qRgb(row[3*x], row[3*x+1], row[3*x+2]);
            else {
                const int a = bitmap.pixel_mode == FT_PIXEL_MODE_MONO
                    ? ((row[x/8] & (0x80 >> (x%8))) ? 255 : 0)
                    : int(row[x]) * 255 / std::max(1, int(bitmap.num_grays) - 1);
                out[x] = qRgb(a, a, a);
            }
        }
    }
    return image;
}

Glyph raster(FT_Face face, FT_UInt index, FT_Pos origin, const Mode &mode)
{
    const int integral = int(std::floor(double(origin) / 64));
    FT_Vector delta{origin - FT_Pos(integral) * 64, 0};
    FT_Set_Transform(face, nullptr, &delta);
    ftCheck(FT_Load_Glyph(face, index, mode.flags | FT_LOAD_NO_BITMAP), "Load glyph");
    ftCheck(FT_Render_Glyph(face->glyph, mode.render), "Render glyph");
    QImage coverage = bitmapImage(face->glyph->bitmap);
    if (mode.low != 0 || mode.high != 255)
        for (int y = 0; y < coverage.height(); ++y)
            for (int x = 0; x < coverage.width(); ++x) {
                const int a = std::clamp(qRed(coverage.pixel(x,y)), mode.low, mode.high) - mode.low;
                const int value = (a*255 + (mode.high-mode.low)/2) / (mode.high-mode.low);
                coverage.setPixel(x,y,qRgb(value,value,value));
            }
    return {integral + face->glyph->bitmap_left, face->glyph->bitmap_top, coverage};
}

int blendChannel(int coverage, const Config &config)
{
    double value = config.dark ? coverage / 255.0 : 1 - coverage / 255.0;
    if (config.linear)
        value = value <= 0.0031308 ? 12.92 * value : 1.055 * std::pow(value, 1 / 2.4) - 0.055;
    return qBound(0, int(std::lround(value * 255)), 255);
}

QImage blend(const QImage &mask, const Config &config)
{
    QImage image(mask.size(), QImage::Format_RGB32);
    for (int y = 0; y < mask.height(); ++y)
        for (int x = 0; x < mask.width(); ++x) {
            const QRgb a = mask.pixel(x, y);
            image.setPixel(x, y, qRgb(blendChannel(qRed(a), config), blendChannel(qGreen(a), config), blendChannel(qBlue(a), config)));
        }
    return image;
}

QImage geometry(double phase, bool snap)
{
    constexpr int samples = 8;
    const double offset = snap ? std::round(phase) : phase;
    QImage high(48*samples, 24*samples, QImage::Format_RGB32);
    high.fill(Qt::black);
    QPainter painter(&high);
    painter.scale(samples, samples);
    painter.translate(offset, 0);
    painter.setPen(Qt::NoPen);
    painter.setBrush(Qt::white);
    painter.drawRect(QRectF(4, 4, 1, 16));
    QPainterPath ring;
    ring.setFillRule(Qt::OddEvenFill);
    ring.addEllipse(QRectF(12, 4, 12, 16));
    ring.addEllipse(QRectF(13, 5, 10, 14));
    painter.drawPath(ring);
    painter.drawPolygon(QPolygonF{{32,4}, {33,4}, {41,20}, {40,20}});
    painter.end();
    QImage mask(48, 24, QImage::Format_RGB32);
    for (int y = 0; y < mask.height(); ++y)
        for (int x = 0; x < mask.width(); ++x) {
            int sum = 0;
            for (int sy = 0; sy < samples; ++sy)
                for (int sx = 0; sx < samples; ++sx)
                    sum += qRed(high.pixel(x*samples+sx, y*samples+sy));
            const int a = (sum + samples*samples/2) / (samples*samples);
            mask.setPixel(x, y, qRgb(a, a, a));
        }
    return mask;
}

void addMask(QImage &destination, const QImage &source, int left, int top)
{
    for (int y = 0; y < source.height(); ++y)
        for (int x = 0; x < source.width(); ++x) {
            const QRgb a = source.pixel(x, y), b = destination.pixel(left+x, top+y);
            const auto over = [](int a, int b) { return a + (b * (255-a) + 127) / 255; };
            destination.setPixel(left+x, top+y, qRgb(over(qRed(a),qRed(b)), over(qGreen(a),qGreen(b)), over(qBlue(a),qBlue(b))));
        }
}
}

QString defaultFont()
{
    QProcess process;
    process.start("fc-match", {"-f", "%{file}", "sans-serif"});
    require(process.waitForFinished() && process.exitStatus() == QProcess::NormalExit && process.exitCode() == 0,
            "Cannot locate a default font. Supply --font /path/to/font.ttf.");
    const QString path = QString::fromUtf8(process.readAllStandardOutput()).trimmed();
    require(!path.isEmpty(), "fc-match returned no font. Supply --font /path/to/font.ttf.");
    return path;
}

Experiment renderExperiment(const Config &config)
{
    require(std::isfinite(config.size) && config.size >= 6 && config.size <= 48, "Size must be between 6 and 48 pixels");
    require(std::isfinite(config.scale) && config.scale >= 0.5 && config.scale <= 3, "Scale must be between 0.5 and 3");
    require(std::isfinite(config.phase) && config.phase >= 0 && config.phase <= 1, "Phase must be between 0 and 1 device pixel");
    require(!config.text.isEmpty() && config.text.size() <= 96, "Sample must contain 1 to 96 printable ASCII characters");
    for (QChar c : config.text) require(c.unicode() >= 32 && c.unicode() <= 126, "This experiment supports printable ASCII only");
    require(config.inspect.size() == 1 && config.inspect[0].unicode() >= 33 && config.inspect[0].unicode() <= 126,
            "Inspect one visible ASCII character");
    QFile file(config.font);
    require(file.open(QIODevice::ReadOnly), "Cannot read font: " + config.font);
    const QByteArray hash = QCryptographicHash::hash(file.readAll(), QCryptographicHash::Sha256).toHex();
    FreeType ft;
    ftCheck(FT_New_Face(ft.library, QFile::encodeName(config.font).constData(), 0, &ft.face), "Open font");
    require(FT_IS_SCALABLE(ft.face) && QByteArray(FT_Get_Font_Format(ft.face)) == "TrueType", "Choose a scalable TrueType outline font (.ttf)");
    ftCheck(FT_Select_Charmap(ft.face, FT_ENCODING_UNICODE), "Select Unicode charmap");
    const FT_F26Dot6 characterSize = std::lround(config.size * config.scale * 64);
    ftCheck(FT_Set_Char_Size(ft.face, 0, characterSize, 72, 72), "Set font size");
    const FT_Pos phase = std::lround(config.phase * 64);
    QVector<FT_UInt> indices;
    QVector<FT_Pos> origins;
    QJsonArray idsJson, originsJson;
    FT_Pos pen = 0;
    FT_UInt previous = 0;
    for (QChar c : config.text) {
        const FT_UInt index = FT_Get_Char_Index(ft.face, c.unicode());
        require(index != 0, QString("Font has no glyph for '%1'").arg(c));
        FT_Vector kerning{};
        if (previous && FT_HAS_KERNING(ft.face))
            ftCheck(FT_Get_Kerning(ft.face, previous, index, FT_KERNING_UNFITTED, &kerning), "Read kerning");
        pen += kerning.x;
        const FT_Pos origin = config.snap ? std::lround(double(pen + phase) / 64) * 64 : pen + phase;
        indices.push_back(index);
        origins.push_back(origin);
        idsJson.append(int(index));
        originsJson.append(double(origin));
        ftCheck(FT_Load_Glyph(ft.face, index, FT_LOAD_NO_HINTING | FT_LOAD_NO_BITMAP), "Read shared advance");
        pen += ft.face->glyph->advance.x;
        previous = index;
    }
    const FT_UInt ell = FT_Get_Char_Index(ft.face, 'l');
    require(ell != 0, "Font has no lowercase l for the stroke inspection");
    const FT_UInt probe = FT_Get_Char_Index(ft.face, config.inspect[0].unicode());
    require(probe != 0, "Font has no glyph for inspection: " + config.inspect);
    QVector<QVector<Glyph>> glyphs;
    int minX = 0, maxX = int(std::ceil(double(pen+phase)/64)), minY = -int(std::ceil(config.size*config.scale)), maxY = 0;
    Experiment result;
    for (const Mode &mode : config.edges ? edgeModes : modes) {
        Sample sample;
        sample.id = mode.id;
        sample.name = mode.name;
        FT_Error error = FT_Property_Set(ft.library, "truetype", "interpreter-version", &mode.interpreter);
        unsigned actual = 0;
        if (!error) error = FT_Property_Get(ft.library, "truetype", "interpreter-version", &actual);
        if (!error && actual != mode.interpreter) error = FT_Err_Unimplemented_Feature;
        if (!error && mode.render == FT_RENDER_MODE_LCD) error = FT_Library_SetLcdFilter(ft.library, FT_LCD_FILTER_DEFAULT);
        sample.metadata = {{"id", sample.id}, {"name", sample.name}, {"interpreter", int(actual)},
            {"requested_interpreter", int(mode.interpreter)}, {"load_flags", int(mode.flags | FT_LOAD_NO_BITMAP)},
            {"render_mode", int(mode.render)}, {"lcd_filter", mode.render == FT_RENDER_MODE_LCD ? int(FT_LCD_FILTER_DEFAULT) : -1},
            {"glyph_ids", idsJson}, {"origins_26_6", originsJson}};
        if (mode.low != 0 || mode.high != 255)
            sample.metadata.insert("coverage_transfer", QJsonObject{{"source", "auto-gray"},
                {"kind", "clipped-linear"}, {"low", mode.low}, {"high", mode.high}});
        QVector<Glyph> run;
        if (error) {
            sample.unavailable = QString("Unavailable: FreeType error %1").arg(error);
            sample.metadata.insert("unavailable", sample.unavailable);
        } else {
            for (int i = 0; i < indices.size(); ++i) {
                Glyph glyph = raster(ft.face, indices[i], origins[i], mode);
                minX = std::min(minX, glyph.x);
                maxX = std::max(maxX, glyph.x + glyph.coverage.width());
                minY = std::min(minY, -glyph.top);
                maxY = std::max(maxY, -glyph.top + glyph.coverage.height());
                run.push_back(glyph);
            }
            const FT_Pos origin = config.snap ? std::lround(double(phase)/64)*64 : phase;
            const Glyph glyph = raster(ft.face, ell, origin, mode);
            sample.glyph = glyph.coverage;
            QJsonArray profile;
            for (int x = 0; x < sample.glyph.width(); ++x) {
                const QRgb a = sample.glyph.pixel(x, sample.glyph.height()/2);
                profile.append(QJsonArray{qRed(a),qGreen(a),qBlue(a)});
            }
            sample.metadata.insert("ell", QJsonObject{{"glyph_id",int(ell)}, {"left",glyph.x}, {"top",glyph.top}, {"width",sample.glyph.width()}, {"height",sample.glyph.height()}, {"midrow_rgb_coverage",profile}});
            const Glyph inspected = probe == ell ? glyph : raster(ft.face, probe, origin, mode);
            sample.inspected = inspected.coverage;
            sample.metadata.insert("probe", QJsonObject{{"character",config.inspect}, {"glyph_id",int(probe)},
                {"left",inspected.x}, {"top",inspected.top}, {"width",sample.inspected.width()}, {"height",sample.inspected.height()}});
        }
        glyphs.push_back(run);
        result.samples.push_back(sample);
    }
    const QSize runSize(maxX-minX+16, maxY-minY+16);
    for (int m = 0; m < result.samples.size(); ++m) {
        auto &sample = result.samples[m];
        if (!sample.unavailable.isEmpty()) continue;
        sample.coverage = QImage(runSize, QImage::Format_RGB32);
        sample.coverage.fill(Qt::black);
        for (const Glyph &glyph : glyphs[m])
            addMask(sample.coverage, glyph.coverage, glyph.x-minX+8, -glyph.top-minY+8);
        sample.rendered = blend(sample.coverage, config);
    }
    const QColor background = config.dark ? Qt::black : Qt::white;
    const QColor foreground = config.dark ? Qt::white : Qt::black;
    const int rowHeight = std::max(54, runSize.height()+26);
    result.comparison = QImage(std::max(720, runSize.width()+260), rowHeight*result.samples.size()+42, QImage::Format_RGB32);
    result.comparison.fill(background);
    QPainter painter(&result.comparison);
    QFont labelFont("sans-serif");
    labelFont.setPixelSize(12);
    painter.setFont(labelFont);
    painter.setPen(foreground);
    painter.drawText(12, 18, QString("%1 | %2 px x %3 = %4 device px | phase %5 | %6 | %7")
        .arg(QString::fromUtf8(ft.face->family_name)).arg(config.size).arg(config.scale).arg(double(characterSize)/64).arg(double(phase)/64)
        .arg(config.snap ? "SNAPPED" : "FRACTIONAL").arg(config.linear ? "linear-light blend" : "encoded-sRGB blend"));
    int detailHeight = 48, detailWidth = 170;
    for (const Sample &sample : result.samples) {
        detailHeight = std::max(detailHeight, sample.inspected.height()*8+42);
        detailWidth = std::max(detailWidth, sample.inspected.width()*8+16);
    }
    result.detail = QImage(detailWidth*result.samples.size(), detailHeight, QImage::Format_RGB32);
    result.detail.fill(background);
    QPainter detailPainter(&result.detail);
    detailPainter.setFont(labelFont);
    detailPainter.setPen(foreground);
    for (int m = 0; m < result.samples.size(); ++m) {
        const auto &sample = result.samples[m];
        const int y = 42 + m*rowHeight;
        painter.drawText(12, y+18, sample.name);
        if (sample.unavailable.isEmpty()) {
            painter.drawImage(250, y, sample.rendered);
            detailPainter.drawText(m*detailWidth+8, 18, sample.id + " | " + config.inspect + " (8x)");
            detailPainter.drawImage(m*detailWidth+8, 32, blend(sample.inspected,config).scaled(sample.inspected.size()*8, Qt::IgnoreAspectRatio, Qt::FastTransformation));
        } else painter.drawText(250, y+18, sample.unavailable);
    }
    painter.end();
    detailPainter.end();
    result.snapped = geometry(double(phase)/64, true);
    result.fractional = geometry(double(phase)/64, false);
    result.target = QImage(700, 470, QImage::Format_RGB32);
    result.target.fill(background);
    QPainter targetPainter(&result.target);
    targetPainter.setFont(labelFont);
    targetPainter.setPen(foreground);
    targetPainter.drawText(12, 20, "Synthetic geometry target; not a font renderer. Native samples and exact 8x pixel repeats.");
    targetPainter.drawText(12, 45, "Straight stem, ring, diagonal. 8x sampling and box average. Phase: " + QString::number(double(phase)/64));
    for (int i = 0; i < 2; ++i) {
        const QImage image = blend(i ? result.snapped : result.fractional, config);
        const int y = 65+i*200;
        targetPainter.drawText(12, y+16, i ? "Snapped target" : "Fractional reference");
        targetPainter.drawImage(160, y, image);
        targetPainter.drawImage(260, y, image.scaled(image.size()*8, Qt::IgnoreAspectRatio, Qt::FastTransformation));
    }
    targetPainter.end();
    int major, minor, patch;
    FT_Library_Version(ft.library, &major, &minor, &patch);
    QJsonArray records;
    for (const auto &sample : result.samples) records.append(sample.metadata);
    result.metadata = {{"font", QFileInfo(config.font).canonicalFilePath()}, {"font_sha256",QString::fromLatin1(hash)},
        {"family",QString::fromUtf8(ft.face->family_name)}, {"freetype_version",QString("%1.%2.%3").arg(major).arg(minor).arg(patch)},
        {"text",config.text}, {"size",config.size}, {"scale",config.scale}, {"effective_size_26_6",double(characterSize)},
        {"inspection_character",config.inspect},
        {"phase_26_6",double(phase)}, {"snap",config.snap}, {"dark",config.dark}, {"linear",config.linear},
        {"layout","shared unhinted advances and unfitted kerning; no shaping"}, {"baseline",8-minY}, {"left_padding",8-minX},
        {"modes",records}, {"lcd_geometry","RGB stripe assumption; inspect grayscale modes on other panels"},
        {"target","synthetic geometry only; eight samples per axis; no candidate font algorithm"}};
    if (config.edges) result.metadata.insert("study", "diagonal-edges");
    return result;
}

void exportExperiment(const Experiment &experiment, const QString &directory)
{
    QDir dir(directory);
    require(!dir.exists() || dir.entryList(QDir::AllEntries | QDir::Hidden | QDir::System | QDir::NoDotAndDotDot).isEmpty(),
            "Export directory must be new or empty; existing files will not be overwritten");
    require(dir.exists() || QDir().mkpath(directory), "Cannot create export directory: " + directory);
    const auto save = [&](const QImage &image, const QString &name) {
        require(image.save(dir.filePath(name), "PNG"), "Cannot write image: " + name);
    };
    save(experiment.comparison, "comparison.png");
    save(experiment.detail, "detail.png");
    save(experiment.target, "target.png");
    save(experiment.snapped, "target-snapped-coverage.png");
    save(experiment.fractional, "target-fractional-coverage.png");
    for (const auto &sample : experiment.samples) if (sample.unavailable.isEmpty()) {
        save(sample.rendered, sample.id + ".png");
        save(sample.coverage, sample.id + "-coverage.png");
        save(sample.glyph, sample.id + "-ell-coverage.png");
        save(sample.inspected, sample.id + "-probe-coverage.png");
    }
    QSaveFile metadata(dir.filePath("metrics.json"));
    require(metadata.open(QIODevice::WriteOnly), "Cannot open metrics.json");
    const QByteArray json = QJsonDocument(experiment.metadata).toJson();
    require(metadata.write(json) == json.size() && metadata.commit(), "Cannot write metrics.json");
}
