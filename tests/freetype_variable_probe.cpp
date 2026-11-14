#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MULTIPLE_MASTERS_H
#include <cmath>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

static void check(bool ok) { if (!ok) throw std::runtime_error("Variable probe failed"); }
static QJsonObject snapshot(FT_Face face) {
    auto slot = face->glyph;
    QJsonArray points, ends;
    if (slot->format == FT_GLYPH_FORMAT_OUTLINE) {
        for (int i=0;i<slot->outline.n_points;++i)
            points.append(QJsonArray{double(slot->outline.points[i].x),double(slot->outline.points[i].y),int(slot->outline.tags[i])});
        for (int i=0;i<slot->outline.n_contours;++i) ends.append(int(slot->outline.contours[i]));
    }
    QByteArray raw;
    if (slot->format == FT_GLYPH_FORMAT_BITMAP) {
        check(slot->bitmap.pixel_mode == FT_PIXEL_MODE_GRAY);
        for (unsigned y=0;y<slot->bitmap.rows;++y)
            raw.append(reinterpret_cast<char*>(slot->bitmap.buffer+y*slot->bitmap.pitch),slot->bitmap.width);
    }
    return {{"outline",points},{"contours",ends},{"mask",QString::fromLatin1(raw.toHex())},
            {"width",int(slot->bitmap.width)},{"height",int(slot->bitmap.rows)},
            {"left",slot->bitmap_left},{"top",slot->bitmap_top}};
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    try {
        check(argc==5);
        FT_Library library;FT_Face face;FT_MM_Var* axes;
        check(!FT_Init_FreeType(&library));check(!FT_New_Face(library,argv[1],0,&face));
        auto size=std::lround(std::strtod(argv[2],nullptr)*64);
        auto flags=FT_Int32(std::strtol(argv[3],nullptr,0));
        check(!FT_Set_Char_Size(face,size,size,0,0));check(!FT_Get_MM_Var(face,&axes));
        std::vector<FT_Fixed> coordinates(axes->num_axis);
        check(!FT_Get_Var_Design_Coordinates(face,axes->num_axis,coordinates.data()));
        unsigned weightAxis=axes->num_axis;
        for(unsigned i=0;i<axes->num_axis;++i)
            if(axes->axis[i].tag==FT_MAKE_TAG('w','g','h','t'))weightAxis=i;
        check(weightAxis<axes->num_axis);
        QJsonArray results;
        const double weights[]={300,399,399.5,400,700,300,400,400,400};
        const char* modes[]={"ramp217","ramp217","ramp217","ramp217","ramp217","ramp217","none","mild","ramp217"};
        for(unsigned step=0;step<9;++step) {
            coordinates[weightAxis]=std::lround(weights[step]*65536);
            check(!FT_Set_Var_Design_Coordinates(face,axes->num_axis,coordinates.data()));
            setenv("FONTREAL_FT_CONTRAST",modes[step],1);
            std::vector<FT_Fixed> current(axes->num_axis);
            check(!FT_Get_Var_Design_Coordinates(face,axes->num_axis,current.data()));
            QJsonArray glyphs;
            for (auto character: std::string("2gilI1 minimum 0358 VvWw 0123456789")) {
                auto glyph=FT_Get_Char_Index(face,character);check(glyph!=0);
                check(!FT_Load_Glyph(face,glyph,flags));auto loaded=snapshot(face);
                check(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL));auto first=snapshot(face);
                check(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL));check(first==snapshot(face));
                glyphs.append(QJsonObject{{"char",QString(character)},{"glyph",int(glyph)},
                                         {"loaded",loaded},{"rendered",first}});
            }
            results.append(QJsonObject{{"requested_weight",weights[step]},
                                       {"weight",double(current[weightAxis])/65536},
                                       {"mode",modes[step]},{"glyphs",glyphs}});
        }
        QFile output(argv[4]);check(output.open(QIODevice::WriteOnly));
        auto bytes=QJsonDocument(results).toJson();check(output.write(bytes)==bytes.size());
        FT_Done_MM_Var(library,axes);FT_Done_Face(face);FT_Done_FreeType(library);
        return 0;
    } catch(const std::exception& error) {qFatal("%s",error.what());}
}
