// Call the private processor with FreeType-owned temporary allocations.
#include "../src/fontreal_coverage.h"
#include <cstdlib>

static void *allocate(FT_Memory memory, long bytes) {
    void *result=std::malloc(bytes);
    if (result) ++*static_cast<int *>(memory->user);
    return result;
}
static void release(FT_Memory memory, void *pointer) {
    if (pointer) --*static_cast<int *>(memory->user);
    std::free(pointer);
}
extern "C" __attribute__((visibility("default"))) int
fontreal_test_mask(unsigned char *pixels, unsigned width, unsigned height, int pitch) {
    int outstanding=0;
    FT_MemoryRec_ memory{&outstanding,allocate,release,nullptr};
    int result=fontreal_selected_coverage(&memory,pixels,width,height,pitch);
    return outstanding ? 9 : result;
}
