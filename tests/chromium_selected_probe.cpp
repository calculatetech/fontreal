// Independent oracle: pristine Fontations interpreter paths and stock Skia A8 raster.
#include "include/core/SkData.h"
#include "base/compiler_specific.h"
#include "include/core/SkPath.h"
#include "include/core/SkPathBuilder.h"
#include "include/core/SkPaint.h"
#include "include/core/SkFont.h"
#include "include/core/SkFontTypes.h"
#include "include/core/SkFontArguments.h"
#include "include/core/SkSurfaceProps.h"
#include "include/ports/SkTypeface_fontations.h"
#include "src/core/SkArenaAlloc.h"
#include "src/core/SkStrikeSpec.h"
#include "include/core/SkString.h"
#include "include/core/SkStrokeRec.h"
#include "src/core/SkGlyph.h"
#include "src/core/SkMask.h"
#include "src/core/SkScalerContext.h"
#include "src/ports/fontations/src/ffi.rs.h"
#include <cmath>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <vector>

struct StockRaster : SkScalerContext {
    using SkScalerContext::GenerateImageFromPath;
    using SkScalerContext::GenerateMetricsFromPath;
};

static void hex(const void* data, size_t length) {
    auto* bytes=static_cast<const unsigned char*>(data);
    UNSAFE_BUFFERS(for (size_t i=0;i<length;++i) std::printf("%02x",bytes[i]));
}

// All CLI and mask spans below are bounded by argc, validated ranges and owning containers.
#pragma clang unsafe_buffer_usage begin
int main(int argc,char** argv) {
    if (argc<12 || (argc-12)%2) return 2;
    auto data=SkData::MakeFromFileName(argv[1]);
    if (!data) return 3;
    auto face=fontations_ffi::make_font_ref({data->bytes(),data->size()},0);
    if (!fontations_ffi::font_ref_is_valid(*face)) return 4;
    float size=std::strtof(argv[2],nullptr);
    unsigned first=std::strtoul(argv[3],nullptr,10),last=std::strtoul(argv[4],nullptr,10);
    if (!std::isfinite(size) || size<=0 || first>last || last>0x10ffff) return 2;
    int control=std::atoi(argv[5]);int light_value=std::atoi(argv[6]);
    if (control<0 || control>3 || (light_value!=0 && light_value!=1)) return 2;
    bool light=light_value;
    SkMatrix post=SkMatrix::MakeAll(std::strtof(argv[7],nullptr),std::strtof(argv[8],nullptr),0,
                                    std::strtof(argv[9],nullptr),std::strtof(argv[10],nullptr),0,0,0,1);
    float stroke=std::strtof(argv[11],nullptr);
    if (!post.isFinite() || !std::isfinite(stroke)) return 2;
    std::vector<fontations_ffi::SkiaDesignCoordinate> variation;
    for (int i=12;i<argc;i+=2) {
        if (std::strlen(argv[i])!=4) return 5;
        auto* tag=reinterpret_cast<const unsigned char*>(argv[i]);
        variation.push_back({uint32_t(tag[0])<<24|uint32_t(tag[1])<<16|uint32_t(tag[2])<<8|tag[3],std::strtof(argv[i+1],nullptr)});
    }
    auto coords=fontations_ffi::resolve_into_normalized_coords(*face,{variation.data(),variation.size()});
    auto outlines=fontations_ffi::get_outline_collection(*face);
    bool hasOutlines=fontations_ffi::outline_format(*outlines)!=fontations_ffi::OutlineFormat::NoOutlines;
    auto styles=fontations_ffi::get_bridge_glyph_styles();
    SkFontArguments arguments;
    arguments.setVariationDesignPosition({reinterpret_cast<const SkFontArguments::VariationPosition::Coordinate*>(variation.data()),int(variation.size())});
    auto nativeFace=SkTypeface_Make_Fontations(data,arguments);
    if (!nativeFace) return 7;
    SkFont nativeFont(nativeFace,size);nativeFont.setHinting(SkFontHinting::kNormal);
    nativeFont.setEdging(SkFont::Edging::kAntiAlias);nativeFont.setEmbeddedBitmaps(false);
    nativeFont.setSubpixel(false);nativeFont.setForceAutoHinting(false);nativeFont.setLinearMetrics(false);
    SkPaint paint;
    if (stroke>=0) {paint.setStyle(SkPaint::kStroke_Style);paint.setStrokeWidth(stroke);paint.setStrokeMiter(10);}
    SkScalerContextRec record;SkScalerContextEffects effects;
    SkScalerContext::MakeRecAndEffects(nativeFont,paint,SkSurfaceProps(),SkScalerContextFlags::kNone,post,&record,&effects);
    SkVector scale;SkMatrix matrix;
    record.computeMatrices(SkScalerContextRec::PreMatrixScale::kVertical,&scale,&matrix);
    bool reliant=fontations_ffi::hinting_reliant(*outlines);
    auto hint=reliant ? fontations_ffi::make_mono_hinting_instance(*outlines,scale.y(),*coords) :
                       fontations_ffi::make_hinting_instance(*outlines,*styles,scale.y(),*coords,light,false,false,
                                                           static_cast<fontations_ffi::AutoHintingControl>(control));
    auto native=SkStrikeSpec::MakeMask(nativeFont,paint,SkSurfaceProps(),SkScalerContextFlags::kNone,post).createScalerContext();
    if (!native) return 8;
    SkArenaAlloc arena(4096);
    auto mapping=fontations_ffi::make_mapping_index(*face);
    std::printf("[");
    for (unsigned codepoint=first;codepoint<=last;++codepoint) {
        uint16_t id=0;uint32_t cp=codepoint;
        fontations_ffi::lookup_glyph_or_zero(*face,*mapping,{&cp,1},{&id,1});
        rust::Vec<uint8_t> verbs;rust::Vec<fontations_ffi::FfiPoint> points;
        fontations_ffi::BridgeScalerMetrics metrics{};
        if (!fontations_ffi::get_path_verbs_points(*outlines,id,scale.y(),*coords,*hint,verbs,points,metrics) && hasOutlines) return 6;
        SkPath path=SkPath::Make({reinterpret_cast<const SkPoint*>(points.data()),points.size()},verbs,{},SkPathFillType::kWinding);
        path=path.makeTransform(matrix);
        float advance=fontations_ffi::unhinted_advance_width_or_zero(*face,scale.y(),*coords,id);
        if (metrics.has_adjusted_advance && std::round(metrics.adjusted_advance)!=0) advance=std::round(metrics.adjusted_advance);
        SkPoint translatedAdvance=matrix.mapPoint({advance,0});
        if (stroke>=0) {
            auto inverse=post.invert();if (!inverse) return 9;
            path=path.makeTransform(*inverse);
            SkStrokeRec rec(SkStrokeRec::kFill_InitStyle);
            rec.setStrokeStyle(stroke,false);
            rec.setStrokeParams(SkPaint::kButt_Cap,SkPaint::kMiter_Join,10);
            SkPathBuilder builder;
            if (rec.applyToPath(&builder,path)) path=builder.detach();
            path=path.makeTransform(post);
        }
        SkIRect bounds=path.getBounds().roundOut();
        unsigned width=unsigned(bounds.width()),height=unsigned(bounds.height());
        std::vector<uint8_t> image(width*height);
        SkMaskBuilder mask(image.data(),bounds,width,SkMask::kA8_Format);
        if (width && height) StockRaster::GenerateImageFromPath(mask,path,SkMaskGamma::PreBlend{},false,false,false,false);
        auto serialized=path.serialize();
        std::printf("%s{\"char\":%u,\"glyph\":%u,\"size\":%.9g,\"advance\":[%.9g,%.9g],\"width\":%u,\"height\":%u,\"left\":%d,\"top\":%d,\"path\":\"",
                    codepoint==first?"":",",codepoint,unsigned(id),double(size),double(translatedAdvance.x()),double(translatedAdvance.y()),
                    width,height,bounds.left(),bounds.top());
        hex(serialized->data(),serialized->size());std::printf("\",\"mask\":\"");
        for (unsigned y=0;y<height;++y) hex(image.data()+y*width,width);
        auto nativeGlyph=native->makeGlyph(SkPackedGlyphID(id),&arena);
        nativeGlyph.setImage(&arena,native.get());nativeGlyph.setPath(&arena,native.get());
        std::printf("\",\"hasOutlines\":%s,\"hasBitmap\":%s,\"nativeRepresentation\":%u,\"nativeFormat\":%d,\"hintingReliant\":%s,\"scale\":%.9g,\"matrix\":[%.9g,%.9g,%.9g,%.9g],\"native\":{\"width\":%u,\"height\":%u,\"left\":%d,\"top\":%d,\"advance\":[%.9g,%.9g],\"path\":\"",
                    hasOutlines?"true":"false",fontations_ffi::has_bitmap_glyph(*face,id)?"true":"false",unsigned(nativeGlyph.extraBits()),int(nativeGlyph.maskFormat()),
                    reliant?"true":"false",double(scale.y()),double(matrix.getScaleX()),double(matrix.getSkewX()),double(matrix.getSkewY()),double(matrix.getScaleY()),
                    unsigned(nativeGlyph.width()),unsigned(nativeGlyph.height()),nativeGlyph.left(),nativeGlyph.top(),double(nativeGlyph.advanceX()),double(nativeGlyph.advanceY()));
        if (const auto* nativePath=nativeGlyph.path()) {auto bytes=nativePath->serialize();hex(bytes->data(),bytes->size());}
        std::printf("\",\"mask\":\"");
        if (const auto* bytes=static_cast<const uint8_t*>(nativeGlyph.image()))
            for (unsigned y=0;y<nativeGlyph.height();++y) hex(bytes+y*nativeGlyph.rowBytes(),nativeGlyph.width());
        std::printf("\"}}");
    }
    std::printf("]\n");
    return 0;
}

#pragma clang unsafe_buffer_usage end
