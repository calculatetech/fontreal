// Keep the processors' FreeType allocation ABI out of the Skia port.
#include "fontreal_coverage.h"
#include "fontreal_v2_coverage.h"
#include <cstdlib>
#include <cstring>

static void* allocate(FT_Memory,long bytes) { return std::malloc(bytes); }
static void release(FT_Memory,void* pointer) { std::free(pointer); }
static const int profile=[] {
    const char* value=std::getenv("FONTREAL_PROFILE");
    return value && !std::strcmp(value,"o") ? 1 : value && !std::strcmp(value,"k3") ? 2 : 0;
}();

extern "C" int fontreal_chromium_profile() { return profile; }
extern "C" int fontreal_chromium_mask(unsigned char* pixels,unsigned width,unsigned height,int pitch,
                                       const unsigned char* high,unsigned highWidth,unsigned highHeight) {
    FT_MemoryRec_ memory{nullptr,allocate,release,nullptr};
    if (!profile) return fontreal_selected_coverage(&memory,pixels,width,height,pitch);
    FT_Bitmap raw{},support{};
    raw.width=width;raw.rows=height;raw.pitch=pitch;raw.buffer=pixels;
    raw.pixel_mode=FT_PIXEL_MODE_GRAY;raw.num_grays=256;
    support.width=highWidth;support.rows=highHeight;support.pitch=int(highWidth);
    support.buffer=const_cast<unsigned char*>(high);support.pixel_mode=FT_PIXEL_MODE_GRAY;support.num_grays=256;
    return fontreal_v2_coverage(&memory,&raw,&support,profile==1?FONTREAL_V2_O:FONTREAL_V2_K3);
}
