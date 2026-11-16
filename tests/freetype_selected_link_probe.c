/* Exercise the selected property from an ordinary C/static or i386 caller. */
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MODULE_H
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    FT_Library library;
    FT_Face face;
    FT_Bool selected = 1;
    FT_F26Dot6 pixels;
    unsigned x, y;
    if (argc != 4 || FT_Init_FreeType(&library)) return 1;
    if ((!getenv("FONTREAL_TEST_LINK_STOCK")
         && FT_Property_Set(library, "autofitter", "fontreal-selected-v1", &selected))
        || FT_New_Face(library, argv[1], 0, &face)) return 1;
    pixels = (FT_F26Dot6)lround(strtod(argv[2], NULL) * 64);
    if (FT_Set_Char_Size(face, pixels, pixels, 0, 0)
        || FT_Load_Char(face, strtoul(argv[3], NULL, 0), FT_LOAD_NO_AUTOHINT | FT_LOAD_NO_BITMAP)
        || FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL)) return 2;
    printf("%u %u %d %d\n", face->glyph->bitmap.width, face->glyph->bitmap.rows,
           face->glyph->bitmap_left, face->glyph->bitmap_top);
    for (y = 0; y < face->glyph->bitmap.rows; ++y)
        for (x = 0; x < face->glyph->bitmap.width; ++x)
            printf("%02x", face->glyph->bitmap.buffer[y * face->glyph->bitmap.pitch + x]);
    puts("");
    return FT_Done_Face(face) || FT_Done_FreeType(library);
}
