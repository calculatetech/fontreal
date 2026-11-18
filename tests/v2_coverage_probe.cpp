// Test bridge: the only numerical entry called is the real private V2 entry.
#include "../src/fontreal_v2_coverage.h"
#include <cstdlib>
#include <cstring>
#include <cstddef>
#include <cstdint>

struct Counts { long live=0, allocated=0, freed=0, corrupt=0; };
struct alignas(std::max_align_t) Block { std::size_t bytes; std::uint64_t guard; };
static constexpr std::uint64_t GUARD=0xa184c73e9b20d65fULL;
static void *allocate(FT_Memory owner,long bytes) {
    auto *block=static_cast<Block *>(std::malloc(sizeof(Block)+bytes+sizeof(GUARD)));
    if (!block) return nullptr;
    *block={static_cast<std::size_t>(bytes),GUARD};
    std::memcpy(reinterpret_cast<unsigned char *>(block+1)+bytes,&GUARD,sizeof(GUARD));
    auto &c=*static_cast<Counts *>(owner->user); ++c.live; ++c.allocated;
    return block+1;
}
static void release(FT_Memory owner,void *pointer) {
    if (!pointer) return;
    auto *block=static_cast<Block *>(pointer)-1; std::uint64_t end;
    std::memcpy(&end,static_cast<unsigned char *>(pointer)+block->bytes,sizeof(end));
    auto &c=*static_cast<Counts *>(owner->user);
    if (block->guard!=GUARD || end!=GUARD) ++c.corrupt;
    --c.live; ++c.freed; std::free(block);
}
#ifdef FONTREAL_V2_OBSERVE_D
struct Observation { unsigned char *output; std::size_t size; long calls=0; bool valid=true; };
static thread_local Observation *observation=nullptr;
extern "C" void fontreal_v2_observe_d(const unsigned char *d,unsigned width,unsigned height) {
    auto &o=*observation; ++o.calls;
    if (static_cast<std::size_t>(width)*height!=o.size) { o.valid=false; return; }
    if (o.size) std::memcpy(o.output,d,o.size);
}
#endif
extern "C" __attribute__((visibility("default"))) int
fontreal_v2_test(FT_Bitmap *raw,const FT_Bitmap *high,int mode,unsigned char *d,
                 std::size_t size,long *stats,int null_memory) {
    Counts counts; FT_MemoryRec_ owner{&counts,allocate,release,nullptr};
#ifdef FONTREAL_V2_OBSERVE_D
    Observation current{d,size}; observation=&current;
#else
    (void)d; (void)size;
#endif
    int status=fontreal_v2_coverage(null_memory ? nullptr:&owner,raw,high,static_cast<FontrealV2Profile>(mode));
    stats[0]=counts.live; stats[1]=counts.allocated; stats[2]=counts.freed; stats[3]=counts.corrupt;
#ifdef FONTREAL_V2_OBSERVE_D
    stats[4]=current.calls; stats[5]=current.valid; observation=nullptr;
#else
    stats[4]=0; stats[5]=1;
#endif
    return status;
}
