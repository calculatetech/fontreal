#include "window.h"
#include <QApplication>
#include <QCheckBox>
#include <QCryptographicHash>
#include <QDir>
#include <QDoubleSpinBox>
#include <QFile>
#include <QFileDialog>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QMap>
#include <QProcess>
#include <QPushButton>
#include <QTabWidget>
#include <QTemporaryDir>
#include <QTextStream>
#include <QTimer>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_LCD_FILTER_H
#include FT_MODULE_H
#include <cmath>
#include <memory>
#include <stdexcept>

namespace {
void check(bool value, const QString &message)
{
    if (!value) throw std::runtime_error(message.toStdString());
}
QByteArray bytes(const QString &path)
{
    QFile file(path);
    check(file.open(QIODevice::ReadOnly), "Cannot read " + path);
    return file.readAll();
}
QJsonObject json(const QString &directory)
{
    QJsonParseError error;
    const auto doc = QJsonDocument::fromJson(bytes(directory + "/metrics.json"), &error);
    check(error.error == QJsonParseError::NoError && doc.isObject(), "Invalid exported JSON");
    return doc.object();
}
QImage image(const QString &path)
{
    QImage result(path);
    check(!result.isNull(), "Missing or invalid PNG: " + path);
    return result.convertToFormat(QImage::Format_RGB32);
}
QString findFont(const QString &pattern)
{
    QProcess p;
    p.start("fc-match", {"-f", "%{file}", pattern});
    check(p.waitForFinished() && p.exitCode() == 0, "fc-match failed");
    return QString::fromUtf8(p.readAllStandardOutput()).trimmed();
}
void invoke(const QString &binary, const QString &font, const QString &directory,
            const QString &working, QStringList arguments = {}, bool success = true)
{
    QProcess p;
    p.setWorkingDirectory(working);
    p.start(binary, QStringList{"--font", font, "--export", directory} + arguments);
    check(p.waitForFinished(30000), "Experiment process did not finish");
    const QString error = QString::fromUtf8(p.readAllStandardError());
    check(p.exitStatus() == QProcess::NormalExit && (success ? p.exitCode() == 0 : p.exitCode() != 0), "Unexpected export result: " + error);
    if (!success) check(error.contains("fontreal:"), "Expected an explicit validation error");
}

struct ReferenceMode { const char *id; unsigned interpreter; FT_Int32 flags; FT_Render_Mode render; };
const ReferenceMode referenceModes[] = {
    {"legacy-mono",35,FT_LOAD_TARGET_MONO,FT_RENDER_MODE_MONO},
    {"legacy-gray",35,FT_LOAD_TARGET_MONO,FT_RENDER_MODE_NORMAL},
    {"auto-gray",40,FT_LOAD_FORCE_AUTOHINT|FT_LOAD_TARGET_MONO,FT_RENDER_MODE_NORMAL},
    {"native-gray",40,FT_LOAD_TARGET_NORMAL,FT_RENDER_MODE_NORMAL},
    {"light-gray",40,FT_LOAD_TARGET_LIGHT,FT_RENDER_MODE_NORMAL},
    {"unhinted-gray",40,FT_LOAD_NO_HINTING,FT_RENDER_MODE_NORMAL},
    {"lcd",40,FT_LOAD_TARGET_LCD,FT_RENDER_MODE_LCD}
};

void checkModeReferences(const QString &font, const QString &directory, int phase, bool snapped,
                         int characterSize = 13*64, const QString &inspect = "l")
{
    const auto metadata = json(directory);
    const auto records = metadata["modes"].toArray();
    check(metadata["inspection_character"] == inspect && metadata["effective_size_26_6"].toInt() == characterSize, "Wrong inspection or effective size");
    check(records.size() == 7, "A mode record disappeared");
    const auto commonOrigins = records[0].toObject()["origins_26_6"].toArray();
    const auto commonIds = records[0].toObject()["glyph_ids"].toArray();
    check(commonIds.size() == metadata["text"].toString().size(), "Lost a specimen glyph");
    int available = 0;
    for (int i = 0; i < 7; ++i) {
        const auto record = records[i].toObject();
        const auto &mode = referenceModes[i];
        check(record["id"] == mode.id && record["origins_26_6"].toArray() == commonOrigins && record["glyph_ids"].toArray() == commonIds, "Mode identity or shared layout changed");
        FT_Library library = nullptr;
        check(!FT_Init_FreeType(&library), "Reference FreeType initialization failed");
        FT_Face face = nullptr;
        check(!FT_New_Face(library, QFile::encodeName(font).constData(), 0, &face), "Reference font failed");
        check(!FT_Select_Charmap(face, FT_ENCODING_UNICODE) && !FT_Set_Char_Size(face,0,characterSize,72,72), "Reference size failed");
        auto error = FT_Property_Set(library, "truetype", "interpreter-version", &mode.interpreter);
        unsigned actual = 0;
        if (!error) error = FT_Property_Get(library,"truetype","interpreter-version",&actual);
        if (!error && mode.render == FT_RENDER_MODE_LCD) error = FT_Library_SetLcdFilter(library,FT_LCD_FILTER_DEFAULT);
        if (error) check(record.contains("unavailable"), "Unsupported treatment was silently replaced");
        else {
            ++available;
            check(!record.contains("unavailable") && actual == mode.interpreter, "Available mode incorrectly reported");
            const int origin = snapped ? int(std::lround(phase/64.0))*64 : phase;
            const int integral = int(std::floor(origin/64.0));
            FT_Vector delta{origin-integral*64,0};
            FT_Set_Transform(face,nullptr,&delta);
            for (const QString kind : {"ell", "probe"}) {
            const FT_UInt ell = FT_Get_Char_Index(face,kind == "ell" ? 'l' : inspect[0].unicode());
            check(!FT_Load_Glyph(face,ell,mode.flags|FT_LOAD_NO_BITMAP) && !FT_Render_Glyph(face->glyph,mode.render), "Reference glyph failed");
            const auto bitmap = face->glyph->bitmap;
            const QImage actualImage = image(directory + "/" + mode.id + "-" + kind + "-coverage.png");
            const bool lcd = mode.render == FT_RENDER_MODE_LCD;
            check(actualImage.width() == int(bitmap.width)/(lcd?3:1) && actualImage.height() == int(bitmap.rows), "Coverage dimensions differ from independent FreeType");
            const auto ellJson = record[kind].toObject();
            if (kind == "probe") check(ellJson["character"] == inspect, "Probe label describes the wrong character");
            check(ellJson["left"].toInt() == integral+face->glyph->bitmap_left && ellJson["top"].toInt() == face->glyph->bitmap_top && ellJson["glyph_id"].toInt() == int(ell), "Reference glyph bearings/identity differ");
            check(record["load_flags"].toInt() == (mode.flags|FT_LOAD_NO_BITMAP) && record["render_mode"].toInt() == mode.render, "Metadata does not describe actual requested mode");
            for (int y = 0; y < actualImage.height(); ++y) {
                const auto *row = bitmap.buffer + (bitmap.pitch >= 0 ? y : int(bitmap.rows)-1-y)*std::abs(bitmap.pitch);
                for (int x = 0; x < actualImage.width(); ++x) {
                    QRgb expected;
                    if (lcd) expected = qRgb(row[x*3],row[x*3+1],row[x*3+2]);
                    else {
                        const int a = mode.render == FT_RENDER_MODE_MONO ? ((row[x/8] & (128 >> (x%8))) ? 255 : 0) : row[x];
                        expected = qRgb(a,a,a);
                    }
                    check(actualImage.pixel(x,y) == expected, "Treatment coverage differs from independent FreeType: " + QString(mode.id));
                }
            }
            for (int c = 0; c < commonIds.size(); ++c)
                check(commonIds[c].toInt() == int(FT_Get_Char_Index(face, metadata["text"].toString()[c].unicode())), "Wrong glyph selected");
            }
        }
        FT_Done_Face(face);
        FT_Done_FreeType(library);
    }
    check(available >= 3, "Too few available modes for this experiment");
    for (const auto &origin : commonOrigins)
        if (snapped) check(origin.toInt()%64 == 0, "Snapped glyph has a fractional origin");
    QTextStream(stdout) << "S1: all seven declared modes checked against independent FreeType; " << available << " available\n";
}

int expectedBlend(int alpha, bool dark, bool linear)
{
    double value = dark ? alpha/255.0 : 1-alpha/255.0;
    if (linear) value = value <= 0.0031308 ? value*12.92 : 1.055*std::pow(value,1.0/2.4)-0.055;
    return int(std::lround(value*255));
}

void checkDetail(const QString &directory, bool dark, bool linear)
{
    const auto detail = image(directory+"/detail.png");
    const auto records = json(directory)["modes"].toArray();
    const int cell = detail.width()/records.size();
    for (int i = 0; i < records.size(); ++i) {
        const auto record = records[i].toObject();
        if (record.contains("unavailable")) continue;
        const auto mask = image(directory+"/"+record["id"].toString()+"-probe-coverage.png");
        for (int y = 0; y < mask.height(); ++y) for (int x = 0; x < mask.width(); ++x) {
            const auto a = mask.pixel(x,y);
            const auto expected = qRgb(expectedBlend(qRed(a),dark,linear),expectedBlend(qGreen(a),dark,linear),expectedBlend(qBlue(a),dark,linear));
            for (int dy = 0; dy < 8; ++dy) for (int dx = 0; dx < 8; ++dx)
                check(detail.pixel(i*cell+8+x*8+dx,32+y*8+dy) == expected, "Detail interpolates or substitutes selected glyph pixels");
        }
    }
}

void core(const QString &binary, const QString &font, const QString &root, const QString &working)
{
    const QByteArray original = bytes(font);
    const QString a = root+"/a", b = root+"/b", fractional = root+"/fractional", zero = root+"/zero";
    invoke(binary,font,a,working);
    invoke(binary,font,b,working);
    checkModeReferences(font,a,32,true);
    invoke(binary,font,fractional,working,{"--fractional"});
    checkModeReferences(font,fractional,32,false);
    check(bytes(a+"/metrics.json") == bytes(b+"/metrics.json"), "Equivalent runs changed metadata");
    for (const auto &name : QDir(a).entryList({"*.png"},QDir::Files)) check(image(a+"/"+name) == image(b+"/"+name), "Equivalent runs changed pixels");
    const auto hash = QString::fromLatin1(QCryptographicHash::hash(original,QCryptographicHash::Sha256).toHex());
    check(json(a)["font_sha256"] == hash, "Incorrect font provenance");
    invoke(binary,font,root+"/size",working,{"--size","14"});
    check(json(root+"/size")["size"].toDouble() == 14 && image(a+"/native-gray.png") != image(root+"/size/native-gray.png"), "Size does not control output");
    const QString other = findFont("monospace");
    check(bytes(other) != original, "This test needs different installed sans and mono fonts");
    invoke(binary,other,root+"/font",working);
    check(json(root+"/font")["font_sha256"] != json(a)["font_sha256"] && image(root+"/font/native-gray.png") != image(a+"/native-gray.png"), "Font selection does not control output");
    QTextStream(stdout) << "S2: repeats are identical; font and size changes alter output and provenance\n";
    const auto snapped = image(a+"/target-snapped-coverage.png");
    const auto split = image(a+"/target-fractional-coverage.png");
    check(qRed(snapped.pixel(5,12)) == 255 && qRed(snapped.pixel(4,12)) == 0, "Target does not snap its stem");
    check(qRed(split.pixel(4,12)) == 128 && qRed(split.pixel(5,12)) == 128, "Fractional contrast is not two half-covered columns");
    invoke(binary,font,zero,working,{"--phase","0","--fractional"});
    check(qRed(image(zero+"/target-fractional-coverage.png").pixel(4,12)) == 255, "Aligned fractional reference is wrong");
    bool actualFractional = false;
    for (const auto &value : json(fractional)["modes"].toArray()[0].toObject()["origins_26_6"].toArray()) actualFractional |= value.toInt()%64 != 0;
    check(actualFractional, "Fractional placement silently snapped all glyphs");
    QTextStream(stdout) << "S3: synthetic stem and actual glyph origins distinguish snapped/fractional placement\n";
    for (int y = 5; y < 19; ++y) check(qRed(snapped.pixel(5,y)) == 255, "Softening damaged aligned stem");
    for (const auto &region : {QRect(13,4,12,16),QRect(33,4,10,16)}) {
        bool soft = false;
        for (int y = region.top(); y <= region.bottom(); ++y)
            for (int x = region.left(); x <= region.right(); ++x) { const int a = qRed(snapped.pixel(x,y)); soft |= a > 0 && a < 255; }
        check(soft, "Target curve or diagonal was not softened");
    }
    QTextStream(stdout) << "S4: soft curve/diagonal coverage coexists with a full straight core\n";
    check(bytes(font) == original && QDir(working).entryList(QDir::AllEntries|QDir::NoDotAndDotDot|QDir::Hidden).isEmpty(), "Run changed source font or wrote undeclared working files");
    QTextStream(stdout) << "S5: normal export leaves source font and working directory unchanged\n";
    const QString occupied = root+"/occupied";
    check(QDir().mkdir(occupied), "Cannot prepare output marker");
    QFile marker(occupied+"/keep");
    check(marker.open(QIODevice::WriteOnly) && marker.write("keep") == 4, "Cannot write output marker");
    marker.close();
    invoke(binary,font,occupied,working,{},false);
    check(bytes(occupied+"/keep") == "keep" && QDir(occupied).entryList(QDir::Files).size() == 1, "Existing output was overwritten");
    const QVector<QStringList> bad = {{"--size","5"},{"--size","49"},{"--size","bad"},{"--scale","0"},{"--phase","2"},{"--text",QString::fromUtf8("é")},{"--text",""},
        {"--inspect",""},{"--inspect","mm"},{"--inspect"," "},{"--inspect",QString::fromUtf8("é")}};
    int n = 0;
    for (const auto &args : bad) invoke(binary,font,root+"/bad"+QString::number(n++),working,args,false);
    invoke(binary,root+"/missing.ttf",root+"/missing",working,{},false);
    const QString cff = "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf";
    if (QFile::exists(cff)) invoke(binary,cff,root+"/unsupported",working,{},false);
    const QString symbols = findFont("Noto Sans Symbols 2");
    if (symbols.contains("NotoSansSymbols2")) invoke(binary,symbols,root+"/missing-glyph",working,{},false);
    invoke(binary,font,root+"/small",working,{"--size","6","--scale","0.5","--text","l"});
    invoke(binary,font,root+"/large",working,{"--size","48","--scale","3","--text","l"});
    QTextStream(stdout) << "S7: invalid inputs fail explicitly and existing output is preserved\n";
    const auto baseCoverage = image(a+"/native-gray-coverage.png");
    QPoint partial(-1,-1);
    for (int y = 0; y < baseCoverage.height() && partial.x() < 0; ++y)
        for (int x = 0; x < baseCoverage.width(); ++x) { const int a = qRed(baseCoverage.pixel(x,y)); if (a > 0 && a < 255) { partial = {x,y}; break; } }
    check(partial.x() >= 0, "Need a gray edge to discriminate blend modes");
    for (int dark = 0; dark < 2; ++dark) for (int linear = 0; linear < 2; ++linear) {
        QStringList args;
        if (dark) args << "--dark";
        if (linear) args << "--linear";
        const QString out = root+QString("/blend%1%2").arg(dark).arg(linear);
        invoke(binary,font,out,working,args);
        for (const auto &mode : referenceModes) {
            const QString name = QString(mode.id)+"-coverage.png";
            if (QFile::exists(a+"/"+name)) check(image(a+"/"+name) == image(out+"/"+name), "Palette/blending changed measured coverage");
        }
        double value = qRed(baseCoverage.pixel(partial))/255.0;
        if (!dark) value = 1-value;
        if (linear) value = value <= 0.0031308 ? value*12.92 : 1.055*std::pow(value,1.0/2.4)-0.055;
        const int expected = int(std::lround(value*255));
        check(qRed(image(out+"/native-gray.png").pixel(partial)) == expected, "Terminal blend pixel is wrong");
    }
    QTextStream(stdout) << "S8: all palette/blend pairs preserve masks and match independent numeric oracles\n";
    for (const QString probe : {"m","n","o","g"}) {
        const QString out = root+"/probe-"+probe;
        invoke(binary,font,out,working,{"--inspect",probe});
        checkModeReferences(font,out,32,true,13*64,probe);
        checkDetail(out,false,false);
        check(image(out+"/comparison.png") == image(a+"/comparison.png"), "Inspection selection changed the specimen comparison");
        for (const auto &mode : referenceModes) {
            if (!QFile::exists(a+"/"+mode.id+"-coverage.png")) continue;
            check(image(out+"/"+mode.id+"-coverage.png") == image(a+"/"+mode.id+"-coverage.png"), "Inspection selection changed specimen coverage");
            check(image(out+"/"+mode.id+"-ell-coverage.png") == image(a+"/"+mode.id+"-ell-coverage.png"), "Inspection selection changed the l baseline");
        }
    }
    QTextStream(stdout) << "S9: m/n/o/g inspection matches independent FreeType and exact 8x pixels; specimen and l baselines unchanged\n";
    invoke(binary,font,root+"/15px",working,{"--size","15","--inspect","m"});
    invoke(binary,font,root+"/10px-150",working,{"--size","10","--scale","1.5","--inspect","m"});
    check(json(root+"/15px")["effective_size_26_6"].toInt() == 15*64 && json(root+"/10px-150")["effective_size_26_6"].toInt() == 15*64, "Size and scale did not produce the expected raster size");
    for (const auto &mode : referenceModes) {
        for (const QString suffix : {"-coverage.png","-ell-coverage.png","-probe-coverage.png"}) {
            const QString name = QString(mode.id)+suffix;
            if (QFile::exists(root+"/15px/"+name)) check(image(root+"/15px/"+name) == image(root+"/10px-150/"+name), "Equivalent size/scale products changed coverage");
        }
    }
    QTextStream(stdout) << "S2: 15px at 1x and 10px at 1.5x have identical treatment, l, and m coverage\n";
}

void view(const QString &binary, const QString &font, const QString &root, const QString &working)
{
    const QByteArray original = bytes(font);
    check(QDir::setCurrent(working), "Cannot select GUI test working directory");
    for (const QStringList args : QVector<QStringList>{{"--size","5"},{"--scale","0"},{"--phase","2"},{"--inspect","mm"}}) {
        QProcess p;
        p.start(binary,QStringList{"--font",font}+args);
        if (!p.waitForFinished(3000)) { p.kill(); p.waitForFinished(); check(false,"GUI startup silently accepted invalid parameters"); }
        check(p.exitStatus() == QProcess::NormalExit && p.exitCode() != 0 && p.readAllStandardError().contains("fontreal:"), "GUI startup did not reject invalid parameters clearly");
    }
    Config config;
    config.font = font;
    config.phase = 0.4922;
    std::unique_ptr<QWidget> window(createWindow(config));
    window->show();
    QApplication::processEvents();
    const QString initial = root+"/gui-initial";
    invoke(binary,font,initial,working,{"--phase","0.4922"});
    check(dynamic_cast<PixelCanvas *>(window->findChild<QWidget *>("Comparison"))->image() == image(initial+"/comparison.png")
        && dynamic_cast<PixelCanvas *>(window->findChild<QWidget *>("Geometry target"))->image() == image(initial+"/target.png"),
        "GUI numeric controls changed an accepted CLI phase across a snapping boundary");
    window->findChild<QDoubleSpinBox *>("size")->setValue(14);
    window->findChild<QDoubleSpinBox *>("scale")->setValue(1.25);
    window->findChild<QDoubleSpinBox *>("phase")->setValue(0.25);
    window->findChild<QCheckBox *>("snap")->setChecked(false);
    window->findChild<QCheckBox *>("dark")->setChecked(true);
    window->findChild<QCheckBox *>("linear")->setChecked(true);
    const QString selectedFont = findFont("monospace");
    const QByteArray selectedOriginal = bytes(selectedFont);
    auto *fontControl = window->findChild<QLineEdit *>("font");
    fontControl->setText(selectedFont);
    QMetaObject::invokeMethod(fontControl,"editingFinished",Qt::DirectConnection);
    auto *inspection = window->findChild<QLineEdit *>("inspect");
    inspection->setText("m");
    QMetaObject::invokeMethod(inspection,"editingFinished",Qt::DirectConnection);
    QApplication::processEvents();
    const QString exported = root+"/view-reference";
    invoke(binary,selectedFont,exported,working,{"--size","14","--scale","1.25","--phase","0.25","--fractional","--dark","--linear","--inspect","m"});
    auto *tabs = window->findChild<QTabWidget *>();
    const QStringList names{"Comparison","Pixel detail","Geometry target"};
    const QStringList files{"comparison.png","detail.png","target.png"};
    for (int i = 0; i < names.size(); ++i) {
        tabs->setCurrentIndex(i);
        QApplication::processEvents();
        auto *canvas = dynamic_cast<PixelCanvas *>(window->findChild<QWidget *>(names[i]));
        const QImage expected = image(exported+"/"+files[i]);
        check(canvas && canvas->image() == expected, "Actual viewer controls feed wrong image");
        const QImage captured = canvas->grab().toImage().convertToFormat(QImage::Format_RGB32);
        check(captured.width() >= expected.width() && captured.height() >= expected.height(), "Canvas clips source pixels");
        check(captured.copy(QRect(QPoint(0,0),expected.size())) == expected, "Actual viewer resamples source pixels");
    }
    checkDetail(exported,true,true);
    fontControl->setText(root+"/missing.ttf");
    QMetaObject::invokeMethod(fontControl,"editingFinished",Qt::DirectConnection);
    check(dynamic_cast<PixelCanvas *>(window->findChild<QWidget *>("Comparison"))->image().isNull()
        && window->findChild<QLabel *>("status")->text().contains("Cannot read font")
        && !window->findChild<QPushButton *>("export")->isEnabled(), "Invalid font leaves stale output or no error");
    fontControl->setText(selectedFont);
    QMetaObject::invokeMethod(fontControl,"editingFinished",Qt::DirectConnection);
    auto *text = window->findChild<QLineEdit *>("text");
    text->setText(QString::fromUtf8("é"));
    QMetaObject::invokeMethod(text,"editingFinished",Qt::DirectConnection);
    check(dynamic_cast<PixelCanvas *>(window->findChild<QWidget *>("Comparison"))->image().isNull() && !window->findChild<QPushButton *>("export")->isEnabled(), "Invalid controls retain stale results");
    text->setText(config.text);
    QMetaObject::invokeMethod(text,"editingFinished",Qt::DirectConnection);
    const auto guiExport = [&](const QString &directory, bool occupied = false) {
        check(QDir().mkpath(directory), "Cannot prepare GUI export folder");
        bool selected = false, rejected = false;
        QTimer::singleShot(0,window.get(),[&] {
            auto *dialog = qobject_cast<QFileDialog *>(QApplication::activeModalWidget());
            if (dialog) {
                dialog->setDirectory(directory);
                dialog->selectFile(directory);
                if (occupied) QTimer::singleShot(0,window.get(),[&] {
                    auto *error = qobject_cast<QMessageBox *>(QApplication::activeModalWidget());
                    if (error) { rejected = error->text().contains("new or empty"); error->accept(); }
                });
                selected = QMetaObject::invokeMethod(dialog,"accept",Qt::DirectConnection);
            }
        });
        window->findChild<QPushButton *>("export")->click();
        check(selected && (!occupied || rejected), "GUI export did not reach expected terminal result");
    };
    QImage referenceCoverage;
    QMap<QString,QImage> referenceMasks;
    for (int dark = 0; dark < 2; ++dark) for (int linear = 0; linear < 2; ++linear) {
        window->findChild<QCheckBox *>("dark")->setChecked(dark);
        window->findChild<QCheckBox *>("linear")->setChecked(linear);
        const QString out = root+QString("/gui-%1%2").arg(dark).arg(linear);
        guiExport(out);
        checkModeReferences(selectedFont,out,16,false,14*1.25*64,"m");
        checkDetail(out,dark,linear);
        const auto mask = image(out+"/native-gray-coverage.png");
        const auto rendered = image(out+"/native-gray.png");
        for (const auto &mode : referenceModes) {
            const QString name = QString(mode.id)+"-coverage.png";
            if (!QFile::exists(out+"/"+name)) continue;
            const auto coverage = image(out+"/"+name);
            if (!referenceMasks.contains(name)) referenceMasks.insert(name,coverage);
            check(coverage == referenceMasks[name], "GUI palette/blending changed a treatment mask");
        }
        if (referenceCoverage.isNull()) referenceCoverage = mask;
        check(mask == referenceCoverage, "GUI palette/blending changed coverage");
        bool partial = false;
        for (int y = 0; y < mask.height(); ++y) for (int x = 0; x < mask.width(); ++x) {
            const int a = qRed(mask.pixel(x,y));
            partial |= a > 0 && a < 255;
            check(qRed(rendered.pixel(x,y)) == expectedBlend(a,dark,linear), "GUI blend differs from numeric oracle");
        }
        check(partial, "GUI blend oracle needs a partial edge");
        check(dynamic_cast<PixelCanvas *>(window->findChild<QWidget *>("Comparison"))->image() == image(out+"/comparison.png"), "GUI export differs from current display");
    }
    const QString occupied = root+"/gui-11";
    QMap<QString,QByteArray> before;
    for (const auto &name : QDir(occupied).entryList(QDir::Files)) before.insert(name,bytes(occupied+"/"+name));
    const auto namesBefore = QDir(occupied).entryList(QDir::AllEntries|QDir::NoDotAndDotDot);
    guiExport(occupied,true);
    check(QDir(occupied).entryList(QDir::AllEntries|QDir::NoDotAndDotDot) == namesBefore, "GUI export changed occupied directory contents");
    for (auto it = before.cbegin(); it != before.cend(); ++it) check(bytes(occupied+"/"+it.key()) == it.value(), "GUI export overwrote an existing file");
    check(bytes(font) == original && bytes(selectedFont) == selectedOriginal && QDir(working).entryList(QDir::AllEntries|QDir::Hidden|QDir::NoDotAndDotDot).isEmpty(), "GUI changed font or wrote undeclared working files");
    QTextStream(stdout) << "S6/S7/S8/S9: real controls, all canvases, independent glyph/blend references, exact detail, startup and update rejection, source/output preservation, and GUI export passed at DPR " << window->devicePixelRatioF() << '\n';
}
}

int main(int argc, char **argv)
{
    QCoreApplication::setAttribute(Qt::AA_DontUseNativeDialogs);
    QApplication app(argc,argv);
    try {
        check(argc == 3, "Usage: experiment-test APP core|view");
        QTemporaryDir root;
        check(root.isValid(), "Cannot create test directory");
        const QString working = root.path()+"/working";
        check(QDir().mkdir(working), "Cannot create test working directory");
        const QString font = findFont("sans-serif");
        if (QByteArray(argv[2]) == "core") core(argv[1],font,root.path(),working);
        else view(argv[1],font,root.path(),working);
        return 0;
    } catch (const std::exception &error) {
        QTextStream(stderr) << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
