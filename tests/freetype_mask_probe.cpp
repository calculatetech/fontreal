#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_FONT_FORMATS_H
#include FT_OUTLINE_H
#include FT_MODULE_H
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>

static void require(bool ok, const char *message)
{
    if (!ok) throw std::runtime_error(message);
}

static QJsonObject snapshot(FT_Face face)
{
    FT_GlyphSlot s = face->glyph;
    QByteArray bytes;
    if (s->format == FT_GLYPH_FORMAT_BITMAP && s->bitmap.buffer) {
        const auto &b = s->bitmap;
        unsigned width = b.pixel_mode == FT_PIXEL_MODE_MONO ? (b.width + 7) / 8 :
                         b.width * (b.pixel_mode == FT_PIXEL_MODE_BGRA ? 4 : 1);
        const unsigned char *row = b.buffer;
        for (unsigned y = 0; y < b.rows; ++y, row += b.pitch)
            bytes.append(reinterpret_cast<const char *>(row), int(width));
    }
    QJsonArray outline, contours;
    if (s->format == FT_GLYPH_FORMAT_OUTLINE) {
        for (int i = 0; i < s->outline.n_points; ++i)
            outline.append(QJsonArray{double(s->outline.points[i].x),
                                      double(s->outline.points[i].y),
                                      int(s->outline.tags[i])});
        for (int i = 0; i < s->outline.n_contours; ++i)
            contours.append(int(s->outline.contours[i]));
    }
    const auto &m = s->metrics;
    return {{"format", double(s->format)}, {"width", int(s->bitmap.width)},
            {"height", int(s->bitmap.rows)}, {"pixel_mode", int(s->bitmap.pixel_mode)},
            {"grays", int(s->bitmap.num_grays)}, {"pitch", s->bitmap.pitch},
            {"left", s->bitmap_left}, {"top", s->bitmap_top},
            {"mask", QString::fromLatin1(bytes.toHex())}, {"outline", outline},
            {"contours", contours},
            {"advance", QJsonArray{double(s->advance.x), double(s->advance.y)}},
            {"metrics", QJsonArray{double(m.width), double(m.height),
                double(m.horiBearingX), double(m.horiBearingY), double(m.horiAdvance),
                double(m.vertBearingX), double(m.vertBearingY), double(m.vertAdvance)}}};
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        require(argc == 12, "Expected FONT PIXELS FLAGS CODEPOINT MODE DX DY REPEATS OUT TRANSFORM REMOVE_AUTOHINTER");
        FT_Library library = nullptr;
        FT_Face face = nullptr;
        require(!FT_Init_FreeType(&library), "FT_Init_FreeType failed");
        if (std::atoi(argv[11])) {
            FT_Module hinter = FT_Get_Module(library, "autofitter");
            require(hinter && !FT_Remove_Module(library, hinter), "Cannot remove auto-hinter");
        }
        require(!FT_New_Face(library, argv[1], 0, &face), "FT_New_Face failed");
        const QByteArray transform(argv[10]);
        require(transform == "none" || transform == "quarter" || transform == "diagonal" ||
                transform == "deferred-diagonal", "Invalid transform");
        FT_Matrix matrix = transform == "quarter" ? FT_Matrix{0, -65536, 65536, 0} :
                                                    FT_Matrix{65536, -32768, 32768, 65536};
        if (transform == "quarter" || transform == "diagonal")
            FT_Set_Transform(face, &matrix, nullptr);
        const auto deferred = [&] {
            if (transform == "deferred-diagonal" && face->glyph->format == FT_GLYPH_FORMAT_OUTLINE) {
                FT_Outline_Transform(&face->glyph->outline, &matrix);
                FT_Vector_Transform(&face->glyph->advance, &matrix);
            }
        };
        const double pixels = std::strtod(argv[2], nullptr);
        if (FT_IS_SCALABLE(face))
            require(!FT_Set_Char_Size(face, std::lround(pixels * 64),
                                     std::lround(pixels * 64), 0, 0), "FT size failed");
        else
            require(!FT_Select_Size(face, 0), "Bitmap strike failed");
        const auto index = FT_Get_Char_Index(face, std::strtoul(argv[4], nullptr, 0));
        require(index != 0, "Missing requested glyph");
        const auto flags = FT_Int32(std::strtol(argv[3], nullptr, 0));
        require(!FT_Load_Glyph(face, index, flags), "FT_Load_Glyph failed");
        deferred();
        QJsonObject result{{"family", QString::fromUtf8(face->family_name)},
                           {"style", QString::fromUtf8(face->style_name)},
                           {"font_format", QString::fromLatin1(FT_Get_Font_Format(face))},
                           {"scalable", bool(FT_IS_SCALABLE(face))},
                           {"color", bool(FT_HAS_COLOR(face))}, {"glyph", int(index)},
                           {"tricky", bool(FT_IS_TRICKY(face))},
                           {"fixed_sizes", face->num_fixed_sizes},
                           {"autohinter", FT_Get_Module(library, "autofitter") != nullptr},
                           {"transform", QString::fromLatin1(transform)},
                           {"loaded", snapshot(face)}};
        if (face->glyph->format == FT_GLYPH_FORMAT_OUTLINE)
            FT_Outline_Translate(&face->glyph->outline, std::strtol(argv[6], nullptr, 0),
                                 std::strtol(argv[7], nullptr, 0));
        QJsonArray rendered;
        const int mode = std::atoi(argv[5]);
        if (mode >= 0)
            for (int i = 0; i < std::atoi(argv[8]); ++i) {
                require(!FT_Render_Glyph(face->glyph, FT_Render_Mode(mode)), "FT_Render_Glyph failed");
                rendered.append(snapshot(face));
            }
        result["rendered"] = rendered;
        // A second load through the same slot detects retained treatment state.
        require(!FT_Load_Glyph(face, FT_Get_Char_Index(face, 'g'), flags), "Next glyph failed");
        deferred();
        if (mode >= 0)
            require(!FT_Render_Glyph(face->glyph, FT_Render_Mode(mode)), "Next raster failed");
        result["next"] = snapshot(face);
        QFile output(QString::fromLocal8Bit(argv[9]));
        require(output.open(QIODevice::WriteOnly), "Cannot write probe output");
        const QByteArray data = QJsonDocument(result).toJson();
        require(output.write(data) == data.size(), "Incomplete probe output");
        FT_Done_Face(face);
        FT_Done_FreeType(library);
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
