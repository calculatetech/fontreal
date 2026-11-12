/* Test-only observation of real browser glyphs; compiled into a private library. */
#ifndef FONTREAL_BROWSER_TRACE_H
#define FONTREAL_BROWSER_TRACE_H
#ifdef FT2_BUILD_LIBRARY
#include <ft2build.h>
#include FT_FREETYPE_H
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static inline int
fontreal_trace_name(char *out, const char *name)
{
    static const char hex[] = "0123456789abcdef";
    int n = 0;
    if (name)
        for (int i = 0; name[i] && i < 96; ++i) {
            unsigned char c = (unsigned char)name[i];
            out[n++] = hex[c >> 4];
            out[n++] = hex[c & 15];
        }
    return n;
}

static inline void
fontreal_test_trace(FT_GlyphSlot slot, FT_Render_Mode mode, FT_Error error,
                    FT_Glyph_Format previous, FT_Int32 flags)
{
    static const char hex[] = "0123456789abcdef";
    char line[8192];
    FT_Bitmap *b = &slot->bitmap;
    int n;
    /* The bounded experiment uses small gray text, not large/color glyph dumps. */
    if (error || b->pixel_mode != FT_PIXEL_MODE_GRAY ||
        b->width > 2000 || b->rows > 2000 || b->width * b->rows > 2000 ||
        b->pitch < (int)b->width)
        return;
    n = snprintf(line, sizeof(line), "FONTREAL_MASK {\"pid\":%ld,\"family\":\"",
                 (long)getpid());
    n += fontreal_trace_name(line + n, slot->face->family_name);
    n += snprintf(line + n, sizeof(line) - n, "\",\"style\":\"");
    n += fontreal_trace_name(line + n, slot->face->style_name);
    n += snprintf(line + n, sizeof(line) - n,
        "\",\"glyph\":%u,\"x_ppem\":%u,\"y_ppem\":%u,\"y_scale\":%ld,"
        "\"units\":%u,\"flags\":%ld,\"mode\":%d,\"previous\":%lu,"
        "\"width\":%u,\"height\":%u,\"left\":%d,\"top\":%d,\"mask\":\"",
        slot->glyph_index,
        slot->face->size ? slot->face->size->metrics.x_ppem : 0,
        slot->face->size ? slot->face->size->metrics.y_ppem : 0,
        slot->face->size ? slot->face->size->metrics.y_scale : 0,
        slot->face->units_per_EM, (long)flags, (int)mode, (unsigned long)previous,
        b->width, b->rows, slot->bitmap_left, slot->bitmap_top);
    for (unsigned y = 0; y < b->rows; ++y)
        for (unsigned x = 0; x < b->width; ++x) {
            unsigned char a = b->buffer[y * b->pitch + x];
            line[n++] = hex[a >> 4];
            line[n++] = hex[a & 15];
        }
    memcpy(line + n, "\"}\n", 3);
    /* One write keeps records from raster workers together. Missing records fail checks. */
    (void)write(STDERR_FILENO, line, (size_t)n + 3);
}
#endif
#endif
