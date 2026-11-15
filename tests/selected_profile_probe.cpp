// Exercise the production load/render entry points, not a replacement rasterizer.
#define main unused_single_glyph_entry
#include "freetype_mask_probe.cpp"
#undef main
#include <QDir>

int main(int argc, char **argv)
{
    QCoreApplication app(argc,argv);
    try {
        require(argc==3,"Expected input and output directory");
        QFile input(argv[1]); require(input.open(QIODevice::ReadOnly),"Input missing");
        QJsonParseError parse;
        auto jobs=QJsonDocument::fromJson(input.readAll(),&parse).array();
        require(parse.error==QJsonParseError::NoError,"Invalid job JSON");
        QString directory=argv[2]; require(QDir().mkpath(directory),"Cannot create output");
        FT_Library library=nullptr; require(!FT_Init_FreeType(&library),"FT init failed");
        for (auto value:jobs) {
            auto job=value.toObject(); FT_Face face=nullptr;
            require(!FT_New_Face(library,QFile::encodeName(job["file"].toString()),0,&face),"Cannot open source face");
            FT_F26Dot6 size=FT_F26Dot6(std::lround(job["pixels"].toDouble()*64));
            require(!FT_Set_Char_Size(face,size,size,0,0),"Cannot set source size");
            FT_Int32 flags=FT_Int32(job["flags"].toInt()); QJsonArray glyphs;
            for (int cp=32; cp<=126; ++cp) {
                FT_UInt gid=FT_Get_Char_Index(face,cp); require(gid,"Missing source character");
                require(!FT_Load_Glyph(face,gid,flags),"Deferred load failed");
                auto loaded=snapshot(face);
                require(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL),"Deferred render failed");
                auto rendered=snapshot(face);
                require(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL),"Repeat render failed");
                auto repeated=snapshot(face);
                require(!FT_Load_Glyph(face,gid,flags|FT_LOAD_RENDER),"Immediate render failed");
                auto immediate=snapshot(face);
                require(!FT_Load_Char(face,cp,flags|FT_LOAD_RENDER),"Character render failed");
                auto character=snapshot(face);
                glyphs.append(QJsonObject{{"codepoint",cp},{"glyph",int(gid)},{"loaded",loaded},
                    {"rendered",rendered},{"repeated",repeated},{"immediate",immediate},{"character",character}});
            }
            QFile output(directory+"/"+job["id"].toString()+".json");
            require(output.open(QIODevice::WriteOnly),"Cannot write result");
            auto bytes=QJsonDocument(QJsonObject{{"id",job["id"]},{"glyphs",glyphs}}).toJson();
            require(output.write(bytes)==bytes.size(),"Short result write");
            FT_Done_Face(face);
        }
        FT_Done_FreeType(library);
        QFile maps("/proc/self/maps"); require(maps.open(QIODevice::ReadOnly),"Cannot inspect mappings");
        QFile proof(directory+"/maps.txt"); require(proof.open(QIODevice::WriteOnly),"Cannot write mapping proof");
        proof.write(maps.readAll());
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr,"%s\n",e.what()); return 1;
    }
}
