#ifndef FONTREAL_COVERAGE_H
#define FONTREAL_COVERAGE_H

#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_SYSTEM_H

#ifdef __cplusplus
extern "C" {
#endif

/* Private entry. Zero succeeds; allocation and argument failures return 1/2. */
__attribute__((visibility("hidden"))) int
fontreal_selected_coverage(FT_Memory memory, FT_Byte *pixels,
                          FT_UInt width, FT_UInt rows, FT_Int pitch);

#ifdef __cplusplus
}
#endif
#endif
