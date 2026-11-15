// Passive fixture observation. Pixels and rendering configuration stay untouched.
#ifndef FONTREAL_SKIA_OWNER_TRACE_H
#define FONTREAL_SKIA_OWNER_TRACE_H
#include "include/core/SkString.h"
#include "include/core/SkTypeface.h"
#include "src/core/SkGlyph.h"
#include "src/core/SkScalerContext.h"
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <unistd.h>

static inline void fontreal_owner_trace(const char *owner,const SkGlyph &glyph,
                                       const SkScalerContextRec &record,SkTypeface *face,
                                       const void *pixels,bool preblend) {
    const char *enabled=std::getenv("FONTREAL_SKIA_TRACE");
    if (!enabled || std::strcmp(enabled,"1")) return;
    SkString family; face->getFamilyName(&family); SkString encoded;
    for (size_t i=0;i<family.size();++i) encoded.appendf("%02x",static_cast<unsigned char>(family.c_str()[i]));
    unsigned width=pixels ? glyph.width():0, height=pixels ? glyph.height():0;
    SkString line;
    line.appendf("FONTREAL_SKIA {\"pid\":%d,\"owner\":\"%s\",\"font\":%u,\"family\":\"%s\",\"glyph\":%u,\"size\":%.8g,\"flags\":%u,\"hinting\":%d,\"format\":%d,\"width\":%u,\"height\":%u,\"left\":%d,\"top\":%d,\"preblend\":%s,\"mask\":\"",
                 int(getpid()),owner,face->uniqueID(),encoded.c_str(),unsigned(glyph.getGlyphID()),
                 double(record.fTextSize),unsigned(record.fFlags),int(record.getHinting()),int(glyph.maskFormat()),
                 width,height,pixels ? int(glyph.left()):0,pixels ? int(glyph.top()):0,preblend ? "true":"false");
    // Restrict observation volume, not rendering, to the fixture's small A8 masks.
    if (pixels && glyph.maskFormat()==SkMask::kA8_Format && glyph.width()<=48 && glyph.height()<=32) {
        auto bytes=static_cast<const unsigned char *>(pixels);
        for (int y=0;y<glyph.height();++y)
            for (int x=0;x<glyph.width();++x) line.appendf("%02x",bytes[y*glyph.rowBytes()+x]);
    }
    line.append("\"}\n"); std::fwrite(line.c_str(),1,line.size(),stderr);
}
#endif
