// Keep the unchanged processor's FreeType allocation ABI out of the Skia port.
#include "fontreal_coverage.h"
#include <cstdlib>

static void* allocate(FT_Memory,long bytes) { return std::malloc(bytes); }
static void release(FT_Memory,void* pointer) { std::free(pointer); }

extern "C" int fontreal_chromium_mask(unsigned char* pixels,unsigned width,unsigned height,int pitch) {
    FT_MemoryRec_ memory{nullptr,allocate,release,nullptr};
    return fontreal_selected_coverage(&memory,pixels,width,height,pitch);
}
