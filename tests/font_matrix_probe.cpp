#include <QGuiApplication>
#include <QFontDatabase>
#include <QRawFont>
#include <QTextLayout>
#include <QGlyphRun>
#include <QImage>
#include <QDir>
#include <QMap>
#include <QSet>
#include <iostream>

#define main single_glyph_probe_entry
#include "freetype_mask_probe.cpp"
#undef main

static bool sameFont(const QRawFont &actual, const QRawFont &source)
{
    if (!actual.isValid()) return false;
    for (const char *table : {"head", "cmap", "name"})
        if (actual.fontTable(table) != source.fontTable(table)) return false;
    return true;
}

static QFont exactFont(const QRawFont &source, int registration, int point)
{
    QFont font(source.familyName());
    font.setStyleName(source.styleName());
    font.setWeight(QFont::Weight(source.weight()));
    font.setStyle(source.style());
    font.setStyleStrategy(QFont::NoFontMerging);
    font.setPointSizeF(point);
    if (sameFont(QRawFont::fromFont(font), source)) return font;
    // Legacy and typographic family names can differ in the same file.
    for (const auto &family : QFontDatabase::applicationFontFamilies(registration))
        for (const auto &style : QFontDatabase::styles(family)) {
            QFont registered = QFontDatabase::font(family, style, point);
            registered.setStyleStrategy(QFont::NoFontMerging);
            registered.setPointSizeF(point);
            if (sameFont(QRawFont::fromFont(registered), source)) return registered;
        }
    throw std::runtime_error("Cannot resolve exact registered face");
}

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    try {
        require(argc == 3, "Expected INPUT_JSON OUTPUT_DIRECTORY");
        QFile input(argv[1]);
        require(input.open(QIODevice::ReadOnly), "Cannot read matrix input");
        QJsonParseError error;
        auto config = QJsonDocument::fromJson(input.readAll(), &error).object();
        require(error.error == QJsonParseError::NoError, "Invalid matrix JSON");
        const QString output = QString::fromLocal8Bit(argv[2]);
        require(QDir().mkpath(output), "Cannot create matrix output");
        const int width = config["width"].toInt();
        require(width > 64, "Invalid canvas width");
        FT_Library library = nullptr;
        require(!FT_Init_FreeType(&library), "FT_Init_FreeType failed");
        FT_Bool nearest = false;
        require(!FT_Property_Get(library, "autofitter", "fontreal-nearest-y-v2", &nearest),
                "Expected CFF-capable nearest-Y provider");
        nearest = true;
        require(!FT_Property_Set(library, "autofitter", "fontreal-nearest-y-v2", &nearest), "Cannot select nearest Y");
        QJsonArray index;
        for (auto value : config["faces"].toArray()) {
            auto faceRecord = value.toObject();
            QString file = faceRecord["file"].toString();
            int registration = QFontDatabase::addApplicationFont(file);
            require(registration >= 0, "Cannot register requested font");
            FT_Face face = nullptr;
            require(!FT_New_Face(library, QFile::encodeName(file).constData(), 0, &face), "Cannot load requested face");
            require(FT_IS_SCALABLE(face) && !FT_HAS_COLOR(face), "Expected scalable monochrome face");
            if (!face->charmap)
                require(!FT_Select_Charmap(face, FT_ENCODING_MS_SYMBOL), "No Unicode or symbol charmap");
            for (auto pointValue : config["points"].toArray()) {
                const int point = pointValue.toInt();
                require(point >= 8 && point <= 16, "Expected integer 8-16pt");
                QRawFont source(file, point*96./72.);
                require(source.isValid(), "Invalid source font");
                QFont font = exactFont(source, registration, point);
                QImage device(1, 1, QImage::Format_RGB32);
                device.setDotsPerMeterX(std::lround(96/0.0254));
                device.setDotsPerMeterY(std::lround(96/0.0254));
                QJsonArray texts = config["texts"].toArray();
                if (faceRecord["symbols"].toBool()) {
                    for (int start = 0xf020; start <= 0xf0ff; start += 32) {
                        QString bank;
                        for (int cp = start; cp < start+32; ++cp) bank += QChar(cp);
                        texts.append(bank);
                    }
                }
                if (faceRecord["nerd"].toBool()) texts.append(QString::fromUtf8("Nerd icons: \uf120 \uf07b \uf013 \ue0b0 \ue0b2"));
                QMap<unsigned, QJsonObject> glyphs;
                QJsonArray occurrences, frames, missing;
                double y = 8, resolved = -1;
                int textNumber = 0;
                for (auto textValue : texts) {
                    QString text = textValue.toString();
                    QTextLayout layout(text, font, &device);
                    QTextOption option;
                    option.setWrapMode(QTextOption::WrapAtWordBoundaryOrAnywhere);
                    layout.setTextOption(option);
                    layout.beginLayout();
                    int consumed = 0;
                    while (true) {
                        QTextLine line = layout.createLine();
                        if (!line.isValid()) break;
                        line.setLineWidth(width-32);
                        line.setPosition(QPointF(16, y));
                        frames.append(QJsonObject{{"text", textNumber}, {"start", line.textStart()},
                            {"length", line.textLength()}, {"top", y}, {"height", line.height()}});
                        consumed += line.textLength();
                        y += std::ceil(line.height())+2;
                    }
                    layout.endLayout();
                    require(consumed == text.size(), "Text not fully laid out");
                    for (auto run : layout.glyphRuns(-1, -1, QTextLayout::RetrieveAll)) {
                        require(sameFont(run.rawFont(), source), "Font substitution detected");
                        if (resolved < 0) {
                            resolved = run.rawFont().pixelSize();
                            require(!FT_Set_Char_Size(face, std::lround(resolved*64), std::lround(resolved*64), 0, 0), "FT size failed");
                        }
                        require(std::abs(run.rawFont().pixelSize()-resolved) < .01, "Mixed native sizes");
                        auto ids = run.glyphIndexes();
                        auto positions = run.positions();
                        auto strings = run.stringIndexes();
                        require(ids.size() == positions.size() && ids.size() == strings.size(), "Incomplete shaped run");
                        for (int i = 0; i < ids.size(); ++i) {
                            unsigned id = ids[i];
                            require(id < unsigned(face->num_glyphs), "Invalid shaped glyph");
                            int stringIndex = strings[i];
                            require(stringIndex >= 0 && stringIndex < text.size(), "Invalid source index");
                            auto position = positions[i];
                            QJsonObject occurrence{{"glyph", int(id)}, {"x", std::floor(position.x())},
                                {"y", int(std::lround(position.y()))}, {"text", textNumber}, {"string_index", stringIndex}};
                            if (!id) {
                                occurrence["missing_advance"] = run.rawFont().advancesForGlyphIndexes({0}).at(0).x();
                            }
                            occurrences.append(occurrence);
                            if (!id) { missing.append(occurrence); continue; }
                            if (!glyphs.contains(id)) {
                                require(!FT_Load_Glyph(face, id, FT_LOAD_FORCE_AUTOHINT | FT_LOAD_TARGET_MONO | FT_LOAD_NO_BITMAP), "FT load failed");
                                QJsonObject loaded = snapshot(face);
                                require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "FT raster failed");
                                QJsonObject raster = snapshot(face);
                                require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "FT repeat failed");
                                require(raster == snapshot(face), "Repeat raster differs");
                                require(raster["pixel_mode"].toInt() == FT_PIXEL_MODE_GRAY, "Expected grayscale raster");
                                glyphs[id] = QJsonObject{{"glyph", int(id)}, {"loaded", loaded}, {"raster", raster}};
                            }
                            auto raster = glyphs[id]["raster"].toObject();
                            int x = int(std::floor(position.x()))+raster["left"].toInt();
                            int top = int(std::lround(position.y()))-raster["top"].toInt();
                            require(x >= 0 && top >= 0 && x+raster["width"].toInt() <= width && top+raster["height"].toInt() <= int(std::ceil(y))+8,
                                    "Glyph exceeds matrix canvas");
                        }
                    }
                    ++textNumber;
                }
                require(resolved > 0 && !occurrences.isEmpty(), "Empty shaped condition");
                QJsonArray captures;
                for (auto glyph : glyphs) captures.append(glyph);
                QJsonObject characterMap;
                for (auto text : texts)
                    for (auto codepoint : text.toString().toUcs4())
                        characterMap[QString::number(codepoint)] = int(FT_Get_Char_Index(face, codepoint));
                QString id = faceRecord["id"].toString()+QString("-%1").arg(point, 2, 10, QChar('0'));
                QJsonObject record{{"id", id}, {"font_id", faceRecord["id"]}, {"point_size", point},
                    {"native_size", resolved}, {"width", width}, {"height", int(std::ceil(y))+8},
                    {"family", source.familyName()}, {"style", source.styleName()},
                    {"font_format", QString::fromLatin1(FT_Get_Font_Format(face))},
                    {"style_flags", int(face->style_flags)}, {"charmap_encoding", double(face->charmap->encoding)},
                    {"texts", texts}, {"frames", frames}, {"occurrences", occurrences}, {"missing", missing},
                    {"character_map", characterMap}, {"glyphs", captures}};
                QFile target(output+"/"+id+".json");
                require(target.open(QIODevice::WriteOnly), "Cannot write matrix condition");
                QByteArray bytes = QJsonDocument(record).toJson(QJsonDocument::Compact);
                require(target.write(bytes) == bytes.size(), "Short matrix write");
                index.append(QJsonObject{{"id", id}, {"file", id+".json"}});
            }
            FT_Done_Face(face);
            QFontDatabase::removeApplicationFont(registration);
            std::cout << faceRecord["label"].toString().toStdString() << " captured" << std::endl;
        }
        FT_Done_FreeType(library);
        QFile target(output+"/index.json");
        require(target.open(QIODevice::WriteOnly), "Cannot write matrix index");
        target.write(QJsonDocument(index).toJson());
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
