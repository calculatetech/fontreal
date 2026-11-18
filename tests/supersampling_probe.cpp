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

static QJsonObject stockCapture(FT_Library library, const char *font, int points,
                               const QString &name, const QString &policy, int target,
                               FT_Render_Mode render, int interpreter, bool darkening, int engine=1, int scale=4) {
    FT_UInt version=interpreter, hintingEngine=engine, effective=0;
    check(FT_Property_Set(library,"truetype","interpreter-version",&version));
    check(FT_Property_Get(library,"truetype","interpreter-version",&effective));
    check(FT_Property_Set(library,"cff","hinting-engine",&hintingEngine));
    check(FT_Property_Get(library,"cff","hinting-engine",&hintingEngine));
    QJsonObject properties;
    for (const char *module : {"cff","autofitter"}) {
        FT_Bool disabled=!darkening, actual=false;
        int set=FT_Property_Set(library,module,"no-stem-darkening",&disabled);
        check(set);
        int get=FT_Property_Get(library,module,"no-stem-darkening",&actual);
        check(get);
        properties.insert(module,QJsonObject{{"set_error",set},{"get_error",get},
                                             {"no_stem_darkening",bool(actual)}});
    }
    // Each variant starts with the same font input and explicit driver properties.
    FT_Face face;
    check(FT_New_Face(library,font,0,&face));
    FT_Int32 flags=FT_LOAD_NO_BITMAP | (target<<16);
    flags |= policy=="auto" ? FT_LOAD_FORCE_AUTOHINT : FT_LOAD_NO_AUTOHINT;
    if (policy=="off") flags |= FT_LOAD_NO_HINTING;
    check(FT_Set_Char_Size(face,0,points*64,96*scale,96*scale));
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
        if (bitmap.pixel_mode!=FT_PIXEL_MODE_GRAY && bitmap.pixel_mode!=FT_PIXEL_MODE_MONO)
            throw std::runtime_error("expected scalar bitmap");
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
    int ppem=face->size->metrics.x_ppem;
    check(FT_Done_Face(face));
    return {{"mode",name},{"scale",scale},{"hint_dpi",96*scale},{"x_ppem",ppem},
        {"policy",policy},{"target",target},{"render",int(render)},
        {"interpreter",interpreter},{"effective_interpreter",int(effective)},
        {"cff_hinting_engine",int(hintingEngine)},{"stem_darkening",darkening},
        {"darkening_properties",properties},{"load_flags",int(flags)},{"glyphs",glyphs}};
}

static QJsonObject stockOptions(FT_Library library, const char *font, int points, QJsonArray &captures) {
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
    auto pair=[&](const QString &name,const QString &policy,int target,FT_Render_Mode render,
                  int interpreter=40,int engine=1) {
        for (bool darkening : {false,true})
            captures.append(stockCapture(library,font,points,name+(darkening ? "_dark_on" : "_dark_off"),
                policy,target,render,interpreter,darkening,engine));
    };
    const char *targets[]={"normal","light","mono"};
    pair("off_gray","off",0,FT_RENDER_MODE_NORMAL);
    for (const QString &policy : {QString("native"),QString("auto")})
        for (int target=0;target<3;++target)
            pair(policy+"_"+targets[target]+"_gray",policy,target,FT_RENDER_MODE_NORMAL);
    for (const QString &policy : {QString("off"),QString("native"),QString("auto")})
        pair(policy+"_mono_source",policy,2,FT_RENDER_MODE_MONO);
    if (versions[0].toObject()["set_error"].toInt()==0) {
        pair("tt35_gray","native",0,FT_RENDER_MODE_NORMAL,35);
        pair("tt35_mono_source","native",2,FT_RENDER_MODE_MONO,35);
    }
    if (versions[1].toObject()["set_error"].toInt()==0 && versions[1].toObject()["effective"].toInt()!=40) {
        pair("tt38_gray","native",0,FT_RENDER_MODE_NORMAL,38);
        pair("tt38_mono_source","native",2,FT_RENDER_MODE_MONO,38);
    }
    if (engines[0].toObject()["set_error"].toInt()==0 && engines[0].toObject()["effective"].toInt()==0)
        pair("cff_old_gray","native",0,FT_RENDER_MODE_NORMAL,40,0);
    return {{"interpreters",versions},{"cff_engines",engines}};
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        bool stock=argc==4 && QString::fromLocal8Bit(argv[3])=="--stock4x";
        bool nativeMono=argc==4 && QString::fromLocal8Bit(argv[3])=="--native-mono";
        if (argc!=3 && !stock && !nativeMono)
            throw std::runtime_error("usage: supersampling-probe FONT POINTS [--stock4x|--native-mono]");
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
            result.insert("capabilities",stockOptions(library,argv[1],points,captures));
            result.insert("captures",captures);
        }
        if (nativeMono) {
            captures.append(stockCapture(library,argv[1],points,"native_mono1","native",2,
                                         FT_RENDER_MODE_NORMAL,40,true,1,1));
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
