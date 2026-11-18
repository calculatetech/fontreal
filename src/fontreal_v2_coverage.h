#ifndef FONTREAL_V2_COVERAGE_H
#define FONTREAL_V2_COVERAGE_H
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_SYSTEM_H
#ifdef __cplusplus
extern "C" {
#endif
typedef enum { FONTREAL_V2_O=0, FONTREAL_V2_K3=1 } FontrealV2Profile;
/* High is registered at (raw.left-3, raw.top-3)*4 with dimensions
   4*(raw.width+6), 4*(raw.rows+6). Buffer points to logical row zero;
   pitch is the signed offset to the next row. Raw and high require separate
   owned storage. Only raw pixels are written.
   Both formats must be GRAY/256. Returns success/allocation/invalid as 0/1/2. */
__attribute__((visibility("hidden"))) int
fontreal_v2_coverage(FT_Memory memory, FT_Bitmap *raw, const FT_Bitmap *high,
                     FontrealV2Profile profile);
#ifdef __cplusplus
}
#endif
#endif
