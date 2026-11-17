// Capture untouched masks and outlines from an explicitly selected FreeType provider.
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MODULE_H
#include FT_FONT_FORMATS_H
#include <dlfcn.h>
#include <stdexcept>

static void check(FT_Error error) {
    if (error) throw std::runtime_error("FreeType error " + std::to_string(error));
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        if (argc != 3) throw std::runtime_error("usage: supersampling-probe FONT POINTS");
        bool valid=false;
        int points=QString::fromLocal8Bit(argv[2]).toInt(&valid);
        if (!valid || points<8 || points>16) throw std::runtime_error("points must be 8 through 16");
        FT_Library library;
        check(FT_Init_FreeType(&library));
        FT_UInt interpreter=40;
        FT_Bool darkening=false;
        check(FT_Property_Set(library,"truetype","interpreter-version",&interpreter));
        check(FT_Property_Set(library,"cff","no-stem-darkening",&darkening));
        FT_Face face;
        check(FT_New_Face(library,argv[1],0,&face));
        if (!FT_IS_SCALABLE(face)) throw std::runtime_error("a scalable face is required");
        int major,minor,patch;
        FT_Library_Version(library,&major,&minor,&patch);
        Dl_info provider{};
        if (!dladdr(reinterpret_cast<void *>(FT_Init_FreeType),&provider))
            throw std::runtime_error("cannot identify loaded FreeType");
        QJsonArray captures;
        const char *names[]={"native1","native2","native4","target4"};
        const int scales[]={1,2,4,4};
        for (int mode=0;mode<4;++mode) {
            int scale=scales[mode], dpi=mode==3 ? 96 : 96*scale;
            check(FT_Set_Char_Size(face,0,points*64,dpi,dpi));
            FT_Matrix matrix{scale*65536L,0,0,scale*65536L};
            FT_Set_Transform(face,mode==3 ? &matrix : nullptr,nullptr);
            QJsonArray glyphs;
            for (int code=32;code<=126;++code) {
                FT_UInt index=FT_Get_Char_Index(face,code);
                if (!index) throw std::runtime_error("missing ASCII glyph");
                check(FT_Load_Glyph(face,index,FT_LOAD_NO_AUTOHINT|FT_LOAD_NO_BITMAP));
                FT_GlyphSlot slot=face->glyph;
                QJsonArray outline,tags,contours;
                for (int i=0;i<slot->outline.n_points;++i) {
                    outline.append(QJsonArray{double(slot->outline.points[i].x),double(slot->outline.points[i].y)});
                    tags.append(int(static_cast<unsigned char>(slot->outline.tags[i])));
                }
                for (int i=0;i<slot->outline.n_contours;++i) contours.append(slot->outline.contours[i]);
                double advance=double(slot->advance.x)/64;
                check(FT_Render_Glyph(slot,FT_RENDER_MODE_NORMAL));
                if (slot->bitmap.pixel_mode!=FT_PIXEL_MODE_GRAY)
                    throw std::runtime_error("expected grayscale bitmap");
                QJsonArray pixels;
                for (unsigned y=0;y<slot->bitmap.rows;++y) {
                    const unsigned char *row=slot->bitmap.buffer+y*slot->bitmap.pitch;
                    for (unsigned x=0;x<slot->bitmap.width;++x) pixels.append(int(row[x]));
                }
                glyphs.append(QJsonObject{{"code",code},{"width",int(slot->bitmap.width)},
                    {"height",int(slot->bitmap.rows)},{"left",slot->bitmap_left},{"top",-slot->bitmap_top},
                    {"advance",advance},{"pixels",pixels},{"outline",outline},{"tags",tags},{"contours",contours}});
            }
            captures.append(QJsonObject{{"mode",names[mode]},{"scale",scale},{"hint_dpi",dpi},
                {"x_ppem",int(face->size->metrics.x_ppem)},{"glyphs",glyphs}});
        }
        QJsonObject result{{"provider",QString::fromLocal8Bit(provider.dli_fname)},
            {"version",QString("%1.%2.%3").arg(major).arg(minor).arg(patch)},
            {"family",QString::fromUtf8(face->family_name)},{"style",QString::fromUtf8(face->style_name)},
            {"format",FT_Get_Font_Format(face)},{"points",points},{"target_dpi",96},{"captures",captures}};
        QFile output;
        if (!output.open(stdout,QIODevice::WriteOnly)) throw std::runtime_error("cannot open stdout");
        QByteArray encoded=QJsonDocument(result).toJson(QJsonDocument::Compact);
        if (output.write(encoded)!=encoded.size()) throw std::runtime_error("cannot write capture");
        FT_Done_Face(face);
        FT_Done_FreeType(library);
        return 0;
    } catch (const std::exception &error) {
        fprintf(stderr,"%s\n",error.what());
        return 1;
    }
}
