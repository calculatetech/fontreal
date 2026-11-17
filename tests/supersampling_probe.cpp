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
#include FT_LCD_FILTER_H
#include <dlfcn.h>
#include <stdexcept>

static void check(FT_Error error) {
    if (error) throw std::runtime_error("FreeType error " + std::to_string(error));
}

static QJsonObject stockCapture(FT_Face face, int points, const QString &name,
                               const QString &policy, int target, FT_Render_Mode render,
                               const QString &filter, int interpreter) {
    FT_UInt version=interpreter;
    check(FT_Property_Set(face->glyph->library,"truetype","interpreter-version",&version));
    FT_UInt effective=0,engine=0;
    check(FT_Property_Get(face->glyph->library,"truetype","interpreter-version",&effective));
    check(FT_Property_Get(face->glyph->library,"cff","hinting-engine",&engine));
    FT_Int32 flags=FT_LOAD_NO_BITMAP | (target<<16);
    flags |= policy=="auto" ? FT_LOAD_FORCE_AUTOHINT : FT_LOAD_NO_AUTOHINT;
    if (policy=="off") flags |= FT_LOAD_NO_HINTING;
    check(FT_Set_Char_Size(face,0,points*64,384,384));
    FT_Set_Transform(face,nullptr,nullptr);
    QJsonArray glyphs;
    for (int code=32;code<=126;++code) {
        FT_UInt index=FT_Get_Char_Index(face,code);
        if (!index) throw std::runtime_error("missing ASCII glyph");
        check(FT_Load_Glyph(face,index,flags));
        FT_GlyphSlot slot=face->glyph;
        QJsonArray outline,tags,contours;
        for (int i=0;i<slot->outline.n_points;++i) {
            outline.append(QJsonArray{double(slot->outline.points[i].x),double(slot->outline.points[i].y)});
            tags.append(int(static_cast<unsigned char>(slot->outline.tags[i])));
        }
        for (int i=0;i<slot->outline.n_contours;++i) contours.append(slot->outline.contours[i]);
        double advance=double(slot->advance.x)/64;
        check(FT_Render_Glyph(slot,render));
        const FT_Bitmap &bitmap=slot->bitmap;
        QByteArray bytes;
        int stride=std::abs(bitmap.pitch);
        for (unsigned y=0;y<bitmap.rows;++y)
            bytes.append(reinterpret_cast<const char *>(bitmap.buffer+ptrdiff_t(y)*bitmap.pitch),stride);
        QJsonObject raw{{"width",int(bitmap.width)},{"rows",int(bitmap.rows)},
            {"pitch",bitmap.pitch},{"pixel_mode",bitmap.pixel_mode},
            {"rows_hex",QString::fromLatin1(bytes.toHex())}};
        glyphs.append(QJsonObject{{"code",code},{"left",slot->bitmap_left},{"top",-slot->bitmap_top},
            {"advance",advance},{"bitmap",raw},{"outline",outline},{"tags",tags},{"contours",contours}});
    }
    return {{"mode",name},{"scale",4},{"hint_dpi",384},{"x_ppem",int(face->size->metrics.x_ppem)},
        {"policy",policy},{"target",target},{"render",int(render)},{"filter",filter},
        {"interpreter",interpreter},{"effective_interpreter",int(effective)},
        {"cff_hinting_engine",int(engine)},{"load_flags",int(flags)},{"glyphs",glyphs}};
}

static QJsonObject stockOptions(FT_Library library, FT_Face face, int points, QJsonArray &captures) {
    QJsonObject filters;
    const char *filterNames[]={"none","default","light","legacy1","legacy"};
    const int filterValues[]={0,1,2,3,16};
    for (int i=0;i<5;++i)
        filters.insert(filterNames[i],FT_Library_SetLcdFilter(library,FT_LcdFilter(filterValues[i])));
    QJsonArray versions,engines;
    for (FT_UInt requested : {35u,38u,40u}) {
        FT_UInt effective=0;
        int error=FT_Property_Set(library,"truetype","interpreter-version",&requested);
        int get=FT_Property_Get(library,"truetype","interpreter-version",&effective);
        versions.append(QJsonObject{{"requested",int(requested)},{"set_error",error},
            {"get_error",get},{"effective",int(effective)}});
    }
    for (FT_UInt requested : {0u,1u}) {
        FT_UInt effective=0;
        int error=FT_Property_Set(library,"cff","hinting-engine",&requested);
        int get=FT_Property_Get(library,"cff","hinting-engine",&effective);
        engines.append(QJsonObject{{"requested",int(requested)},{"set_error",error},
            {"get_error",get},{"effective",int(effective)}});
    }
    FT_UInt version=40;
    check(FT_Property_Set(library,"truetype","interpreter-version",&version));
    FT_Bool cff=false,automatic=true;
    check(FT_Property_Get(library,"cff","no-stem-darkening",&cff));
    check(FT_Property_Get(library,"autofitter","no-stem-darkening",&automatic));
    const char *targets[]={"normal","light","mono","lcd","lcd_v"};
    captures.append(stockCapture(face,points,"off_gray","off",0,FT_RENDER_MODE_NORMAL,"n/a",40));
    for (const QString &policy : {QString("native"),QString("auto")})
        for (int target=0;target<5;++target)
            captures.append(stockCapture(face,points,policy+"_"+targets[target]+"_gray",policy,
                                         target,FT_RENDER_MODE_NORMAL,"n/a",40));
    for (const QString &policy : {QString("off"),QString("native"),QString("auto")}) {
        captures.append(stockCapture(face,points,policy+"_mono_source",policy,2,FT_RENDER_MODE_MONO,"n/a",40));
        for (int target : {3,4})
            for (int i=0;i<5;++i) {
                if (filters[filterNames[i]].toInt()!=0) continue;
                check(FT_Library_SetLcdFilter(library,FT_LcdFilter(filterValues[i])));
                captures.append(stockCapture(face,points,policy+"_"+targets[target]+"_"+filterNames[i],
                    policy,target,FT_Render_Mode(target),filterNames[i],40));
            }
    }
    if (versions[0].toObject()["set_error"].toInt()==0) {
        captures.append(stockCapture(face,points,"tt35_gray","native",0,FT_RENDER_MODE_NORMAL,"n/a",35));
        captures.append(stockCapture(face,points,"tt35_mono_source","native",2,FT_RENDER_MODE_MONO,"n/a",35));
    }
    if (versions[1].toObject()["set_error"].toInt()==0 && versions[1].toObject()["effective"].toInt()!=40) {
        captures.append(stockCapture(face,points,"tt38_gray","native",0,FT_RENDER_MODE_NORMAL,"n/a",38));
        captures.append(stockCapture(face,points,"tt38_mono_source","native",2,FT_RENDER_MODE_MONO,"n/a",38));
    }
    if (engines[0].toObject()["set_error"].toInt()==0 && engines[0].toObject()["effective"].toInt()==0) {
        FT_UInt old=0;
        check(FT_Property_Set(library,"cff","hinting-engine",&old));
        captures.append(stockCapture(face,points,"cff_old_gray","native",0,FT_RENDER_MODE_NORMAL,"n/a",40));
    }
    return {{"lcd_filters",filters},{"interpreters",versions},{"cff_engines",engines},
        {"cff_no_stem_darkening",bool(cff)},{"auto_no_stem_darkening",bool(automatic)}};
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        bool stock=argc==4 && QString::fromLocal8Bit(argv[3])=="--stock4x";
        if (argc!=3 && !stock) throw std::runtime_error("usage: supersampling-probe FONT POINTS [--stock4x]");
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
        if (stock) {
            result.insert("capabilities",stockOptions(library,face,points,captures));
            result.insert("captures",captures);
        }
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
