// Capture native outlines and actual unmodified Qt paint without installing either.
#include <QGuiApplication>
#include <QFontDatabase>
#include <QRawFont>
#include <QTextLayout>
#include <QGlyphRun>
#include <QPainter>
#include <QImage>
#include <QDir>
#define main unused_single_glyph_entry
#include "freetype_mask_probe.cpp"
#undef main

static bool sameFace(const QRawFont &a, const QRawFont &b)
{
    for (auto table : {"head", "cmap", "name"})
        if (a.fontTable(table) != b.fontTable(table)) return false;
    return a.isValid() && b.isValid();
}

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    try {
        require(argc == 3, "Expected input and output directory");
        QFile input(argv[1]); require(input.open(QIODevice::ReadOnly), "Input missing");
        QJsonParseError error;
        auto config = QJsonDocument::fromJson(input.readAll(), &error).object();
        require(error.error == QJsonParseError::NoError, "Bad input JSON");
        const QString out = argv[2]; require(QDir().mkpath(out), "Output missing");
        FT_Library library; require(!FT_Init_FreeType(&library), "FT init failed");
        QJsonArray results;
        for (auto item : config["faces"].toArray()) {
            auto faceRecord = item.toObject(); QString file = faceRecord["file"].toString();
            int registration = QFontDatabase::addApplicationFont(file);
            require(registration >= 0, "Cannot register face");
            FT_Face face; require(!FT_New_Face(library, QFile::encodeName(file), 0, &face), "Cannot open face");
            for (int point : {11, 12}) {
                QRawFont source(file, point*96./72.); require(source.isValid(), "Invalid font");
                QFont font(source.familyName()); font.setStyleName(source.styleName());
                font.setWeight(QFont::Weight(source.weight())); font.setStyle(source.style());
                font.setStyleStrategy(QFont::NoFontMerging); font.setPointSizeF(point);
                require(sameFace(QRawFont::fromFont(font), source), "Face substitution");
                QString id = faceRecord["id"].toString()+"-"+QString::number(point);
                QJsonArray layouts; double pixels = -1;
                QImage device(470, 40, QImage::Format_RGB32);
                device.setDotsPerMeterX(std::lround(96/.0254)); device.setDotsPerMeterY(device.dotsPerMeterX());
                require(device.logicalDpiY() == 96 && device.devicePixelRatio() == 1, "Device mismatch");
                int number = 0;
                for (auto textValue : config["texts"].toArray()) {
                    QString text = textValue.toString(); QTextLayout layout(text, font, &device);
                    layout.beginLayout(); auto line = layout.createLine(); line.setLineWidth(454); layout.endLayout();
                    line.setPosition(QPointF(0, 5));
                    require(line.textLength() == text.size() && line.naturalTextWidth() < 454, "Clipped text");
                    QJsonArray occurrences;
                    for (auto run : layout.glyphRuns()) {
                        require(sameFace(run.rawFont(), source), "Run face substitution");
                        if (pixels < 0) pixels = run.rawFont().pixelSize();
                        require(pixels == run.rawFont().pixelSize(), "Mixed pixel sizes");
                        auto gids = run.glyphIndexes(); auto positions = run.positions();
                        require(gids.size() == positions.size(), "Position mismatch");
                        for (int i=0; i<gids.size(); ++i)
                            occurrences.append(QJsonObject{{"glyph", int(gids[i])}, {"text", 0},
                                {"x", int(std::floor(8+positions[i].x()))}, {"y", int(std::lround(positions[i].y()))},
                                {"qt_x", 8+positions[i].x()}, {"qt_y", positions[i].y()}});
                    }
                    QJsonObject row{{"text", text}, {"width", 470}, {"height", 40}, {"occurrences", occurrences}};
                    if (faceRecord["family"].toString() == "Noto Sans") {
                        for (bool dark : {false, true}) {
                            QImage previous;
                            for (int repeat=0; repeat<2; ++repeat) {
                                QImage image(device); image.fill(dark ? Qt::black : Qt::white);
                                QPainter painter(&image); painter.setPen(dark ? Qt::white : Qt::black);
                                layout.draw(&painter, QPointF(8, 0)); painter.end();
                                if (repeat) require(image == previous, "Non-repeatable Qt paint");
                                previous = image;
                            }
                            QString name = id+"-"+QString::number(number)+(dark ? "-dark.png" : "-light.png");
                            require(previous.save(out+"/"+name), "Cannot save Qt paint");
                            row[dark ? "stock_dark" : "stock_light"] = name;
                        }
                    }
                    layouts.append(row); ++number;
                }
                require(pixels > 0 && !FT_Set_Char_Size(face, std::lround(pixels*64), std::lround(pixels*64), 0, 0), "Size failed");
                QJsonArray glyphs;
                for (int cp=32; cp<=126; ++cp) {
                    unsigned gid = FT_Get_Char_Index(face, cp); require(gid, "Missing ASCII glyph");
                    require(!FT_Load_Glyph(face, gid, FT_LOAD_NO_AUTOHINT|FT_LOAD_NO_BITMAP), "Glyph load failed");
                    auto loaded = snapshot(face); QJsonArray rasters;
                    for (int repeat=0; repeat<2; ++repeat) {
                        require(!FT_Load_Glyph(face, gid, FT_LOAD_NO_AUTOHINT|FT_LOAD_NO_BITMAP), "Repeat glyph load failed");
                        require(snapshot(face) == loaded, "Non-repeatable loaded outline");
                        require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "Raster failed");
                        rasters.append(snapshot(face));
                    }
                    require(rasters[0] == rasters[1], "Non-repeatable native raster");
                    glyphs.append(QJsonObject{{"glyph", int(gid)}, {"codepoint", cp}, {"loaded", loaded}, {"rendered", rasters}});
                }
                QJsonObject result{{"id", id}, {"point_size", point}, {"native_size", pixels},
                    {"font_id", faceRecord["id"]}, {"font_format", FT_Get_Font_Format(face)},
                    {"hinting_preference", int(font.hintingPreference())}, {"glyphs", glyphs}, {"rows", layouts}};
                QFile output(out+"/"+id+".json"); require(output.open(QIODevice::WriteOnly), "Cannot save capture");
                auto bytes = QJsonDocument(result).toJson(); require(output.write(bytes) == bytes.size(), "Short capture write");
                results.append(id);
            }
            FT_Done_Face(face); QFontDatabase::removeApplicationFont(registration);
        }
        FT_Done_FreeType(library);
        QFile maps("/proc/self/maps"); require(maps.open(QIODevice::ReadOnly), "Cannot inspect loaded libraries");
        QFile proof(out+"/maps.txt"); require(proof.open(QIODevice::WriteOnly), "Cannot save library proof");
        proof.write(maps.readAll());
        QFile index(out+"/index.json"); require(index.open(QIODevice::WriteOnly), "Cannot save index");
        index.write(QJsonDocument(results).toJson());
        return 0;
    } catch (const std::exception &e) { std::fprintf(stderr, "%s\n", e.what()); return 1; }
}
