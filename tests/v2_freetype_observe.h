/* Passive adapter input recorder. This header is only used in test builds. */
#ifndef FONTREAL_V2_FREETYPE_OBSERVE_H
#define FONTREAL_V2_FREETYPE_OBSERVE_H
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>
#include <stdlib.h>
static void
fontreal_v2_test_observe(FT_GlyphSlot slot, const FT_Bitmap *high, unsigned profile)
{
    const char *path = getenv("FONTREAL_V2_OBSERVATION");
    FILE *file;
    unsigned y;
    if (!path) return;
    file = fopen(path, "wb");
    if (!file) abort();
    fprintf(file, "%u %u %u %d %d %u %u\n", profile, slot->bitmap.width,
            slot->bitmap.rows, slot->bitmap_left, slot->bitmap_top, high->width, high->rows);
    for (y = 0; y < slot->bitmap.rows; ++y)
        if (fwrite(slot->bitmap.buffer + (long)y * slot->bitmap.pitch, 1, slot->bitmap.width, file) != slot->bitmap.width) abort();
    for (y = 0; y < high->rows; ++y)
        if (fwrite(high->buffer + (long)y * high->pitch, 1, high->width, file) != high->width) abort();
    if (fclose(file)) abort();
}
#endif
