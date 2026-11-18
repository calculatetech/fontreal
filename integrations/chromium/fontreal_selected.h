// Fixed selected integration. Both numerical processors remain unchanged.
#ifndef FONTREAL_SKIA_SELECTED_H
#define FONTREAL_SKIA_SELECTED_H
#include "src/core/SkDescriptor.h"
#include "src/core/SkGlyph.h"
#include "src/core/fontreal_build.h"
#include "include/core/SkData.h"
#include "include/core/SkString.h"
#include "include/core/SkPaint.h"
#include "include/core/SkPathBuilder.h"
#include "include/core/SkStrokeRec.h"
#include <cstdlib>
#include <memory>
#include <memory>
#if FONTREAL_SELECTED_TRACE
#include <cstdio>
#include <unistd.h>
#endif

static bool fontreal_eligible(const SkTypeface& face, bool outlines, const SkScalerContextRec& rec) {
    if (!outlines || rec.getHinting()==SkFontHinting::kNone) return false;
    // EBDT is grayscale; Fontations' has_any_color_table also includes that table.
    for (auto tag : {SkSetFourByteTag('C','O','L','R'),SkSetFourByteTag('S','V','G',' '),
                     SkSetFourByteTag('s','b','i','x'),SkSetFourByteTag('C','B','D','T')})
        if (face.getTableSize(tag)) return false;
    return true;
}
extern "C" int fontreal_chromium_profile();
extern "C" int fontreal_chromium_mask(unsigned char*,unsigned,unsigned,int,const unsigned char*,unsigned,unsigned);
using FontrealRaster=void (*)(SkMaskBuilder&,const SkPath&,const SkMaskGamma::PreBlend&,bool,bool,bool,bool);

#if FONTREAL_SELECTED_TRACE
static SkString fontreal_hex(const void* data,size_t size) {
    SkString result;auto bytes=static_cast<const unsigned char*>(data);
    for (size_t i=0;i<size;++i) result.appendf("%02x",bytes[i]);
    return result;
}
static SkString fontreal_mask(const SkGlyph& glyph,const void* pixels) {
    if (!glyph.width() || !glyph.height()) return SkString();
    SkString result;auto bytes=static_cast<const unsigned char*>(pixels);
    for (unsigned y=0;y<glyph.height();++y) result.append(fontreal_hex(bytes+y*glyph.rowBytes(),glyph.width()));
    return result;
}
static SkString fontreal_family(SkTypeface* face) {
    SkString family;face->getFamilyName(&family);return fontreal_hex(family.c_str(),family.size());
}
static void fontreal_target(SkTypeface* face,const SkScalerContextRec& rec,bool eligible,bool reliant,float scale,int control,bool mono,bool light,bool lcd,bool vertical) {
    SkString line;
    line.appendf("FONTREAL_SKIA {\"pid\":%d,\"owner\":\"selected-target\",\"font\":%u,\"family\":\"%s\",\"size\":%.9g,\"scale\":%.9g,\"post\":[%.9g,%.9g,%.9g,%.9g],\"flags\":%u,\"hinting\":%d,\"format\":%d,\"eligible\":%s,\"hintingReliant\":%s,\"control\":%d,\"mono\":%s,\"light\":%s,\"lcd\":%s,\"vertical\":%s,\"linear\":%s,\"subpixel\":%s}\n",
                 int(getpid()),face->uniqueID(),fontreal_family(face).c_str(),double(rec.fTextSize),double(scale),double(rec.fPost2x2[0][0]),double(rec.fPost2x2[0][1]),double(rec.fPost2x2[1][0]),double(rec.fPost2x2[1][1]),unsigned(rec.fFlags),int(rec.getHinting()),int(rec.fMaskFormat),
                 eligible?"true":"false",reliant?"true":"false",control,mono?"true":"false",light?"true":"false",lcd?"true":"false",vertical?"true":"false",
                 rec.fFlags&SkScalerContext::kLinearMetrics_Flag?"true":"false",rec.fFlags&SkScalerContext::kSubpixelPositioning_Flag?"true":"false");
    std::fwrite(line.c_str(),1,line.size(),stderr);
}
#endif

static void fontreal_complete(const SkGlyph& glyph,void* imageBuffer,const SkPath& devPath,
                              const SkIRect& bounds,bool hairline,FontrealRaster raster,bool direct,SkTypeface* face,
                              const SkScalerContextRec& rec,float scale,const SkMatrix& matrix,uint32_t descriptor,bool preblend) {
    const int profile=fontreal_chromium_profile();
    unsigned highWidth=0,highHeight=0;
    SkIRect highBounds=SkIRect::MakeEmpty();
    std::unique_ptr<unsigned char,decltype(&std::free)> high(nullptr,&std::free);
    if (profile && glyph.width() && glyph.height()) {
        highWidth=4*(unsigned(glyph.width())+6);highHeight=4*(unsigned(glyph.height())+6);
        highBounds=SkIRect::MakeLTRB(4*(bounds.left()-3),4*(bounds.top()-3),
                                       4*(bounds.right()+3),4*(bounds.bottom()+3));
        high.reset(static_cast<unsigned char*>(std::malloc(size_t(highWidth)*highHeight)));
        if (!high) SK_ABORT("fontreal_selected_coverage failed: %d",1);
        SkPath source=devPath;
        if (hairline) {
            // Match GenerateImageFromPath's default A8 paint at one native pixel.
            SkPaint paint;paint.setStyle(SkPaint::kStroke_Style);paint.setStrokeWidth(1);
            SkStrokeRec stroke(paint);SkPathBuilder builder;
            if (!stroke.applyToPath(&builder,source)) SK_ABORT("fontreal_selected_coverage failed: %d",2);
            source=builder.detach();
        }
        source=source.makeTransform(SkMatrix::Scale(4,4));
        SkMaskBuilder mask(high.get(),highBounds,highWidth,SkMask::kA8_Format);
        raster(mask,source,SkMaskGamma::PreBlend{},false,false,false,false);
    }
#if FONTREAL_SELECTED_TRACE
    SkString raw=fontreal_mask(glyph,imageBuffer),highBytes;
    if (high) highBytes=fontreal_hex(high.get(),size_t(highWidth)*highHeight);
#endif
    int status=0;
    if (glyph.width() && glyph.height())
        status=fontreal_chromium_mask(static_cast<unsigned char*>(imageBuffer),glyph.width(),glyph.height(),int(glyph.rowBytes()),high.get(),highWidth,highHeight);
    if (status) SK_ABORT("fontreal_selected_coverage failed: %d",status);
#if FONTREAL_SELECTED_TRACE
    SkString encodedPath;
    { auto data=devPath.serialize();encodedPath=fontreal_hex(data->data(),data->size()); }
    SkString line;
    line.appendf("FONTREAL_SKIA {\"pid\":%d,\"owner\":\"selected\",\"font\":%u,\"family\":\"%s\",\"glyph\":%u,\"packed\":%u,\"size\":%.9g,\"scale\":%.9g,\"flags\":%u,\"hinting\":%d,\"format\":%d,\"width\":%u,\"height\":%u,\"left\":%d,\"top\":%d,\"advance\":[%.9g,%.9g],\"preblend\":%s,\"direct\":%s,\"descriptor\":%u,\"image\":\"%p\",\"matrix\":[%.9g,%.9g,%.9g,%.9g],\"frame\":%.9g,\"status\":%d,\"profile\":%d,\"hairline\":%s,\"highBounds\":[%d,%d,%d,%d],\"highWidth\":%u,\"highHeight\":%u,\"high\":\"%s\",\"path\":\"%s\",\"raw\":\"%s\",\"mask\":\"%s\"}\n",
                 int(getpid()),face->uniqueID(),fontreal_family(face).c_str(),unsigned(glyph.getGlyphID()),glyph.getPackedID().value(),double(rec.fTextSize),double(scale),
                 unsigned(rec.fFlags),int(rec.getHinting()),int(glyph.maskFormat()),unsigned(glyph.width()),unsigned(glyph.height()),glyph.left(),glyph.top(),double(glyph.advanceX()),double(glyph.advanceY()),
                 preblend?"true":"false",direct?"true":"false",descriptor,imageBuffer,
                 double(matrix.getScaleX()),double(matrix.getSkewX()),double(matrix.getSkewY()),double(matrix.getScaleY()),double(rec.fFrameWidth),status,profile,hairline?"true":"false",highBounds.left(),highBounds.top(),highBounds.right(),highBounds.bottom(),highWidth,highHeight,highBytes.c_str(),
                 encodedPath.c_str(),raw.c_str(),fontreal_mask(glyph,imageBuffer).c_str());
    std::fwrite(line.c_str(),1,line.size(),stderr);
#else
    (void)direct;(void)face;(void)rec;(void)scale;(void)matrix;(void)descriptor;(void)preblend;
#endif
}

#endif
