#define main fontreal_supersampling_original_main
#include "supersampling_probe.cpp"
#undef main

int main(int argc,char **argv) {
    QCoreApplication app(argc,argv);
    try {
        if (argc!=3) throw std::runtime_error("usage: arial-hinting-probe FONT POINTS");
        bool valid=false;int points=QString::fromLocal8Bit(argv[2]).toInt(&valid);
        if (!valid || (points!=10 && points!=11)) throw std::runtime_error("points must be 10 or 11");
        FT_Library library;check(FT_Init_FreeType(&library));
        FT_Face face;check(FT_New_Face(library,argv[1],0,&face));
        int major,minor,patch;FT_Library_Version(library,&major,&minor,&patch);
        Dl_info provider{};
        if (!dladdr(reinterpret_cast<void *>(FT_Init_FreeType),&provider)) throw std::runtime_error("cannot identify loaded FreeType");
        QJsonArray captures;
        captures.append(stockCapture(library,argv[1],points,"native_mono","native",2,FT_RENDER_MODE_NORMAL,40,false,1,1));
        captures.append(stockCapture(library,argv[1],points,"native_normal","native",0,FT_RENDER_MODE_NORMAL,40,false,1,1));
        captures.append(stockCapture(library,argv[1],points,"auto_mono","auto",2,FT_RENDER_MODE_NORMAL,40,false,1,1));
        captures.append(stockCapture(library,argv[1],points,"off_mono","off",2,FT_RENDER_MODE_NORMAL,40,false,1,1));
        QJsonObject result{{"provider",QString::fromLocal8Bit(provider.dli_fname)},
            {"version",QString("%1.%2.%3").arg(major).arg(minor).arg(patch)},
            {"family",QString::fromUtf8(face->family_name)},{"style",QString::fromUtf8(face->style_name)},
            {"format",FT_Get_Font_Format(face)},{"points",points},{"target_dpi",96},{"captures",captures}};
        QFile output;if (!output.open(stdout,QIODevice::WriteOnly)) throw std::runtime_error("cannot open stdout");
        output.write(QJsonDocument(result).toJson(QJsonDocument::Compact));output.write("\n");
        check(FT_Done_Face(face));check(FT_Done_FreeType(library));return 0;
    } catch(const std::exception &error) {qCritical("%s",error.what());return 1;}
}
