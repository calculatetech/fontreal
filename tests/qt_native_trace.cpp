#include <ft2build.h>
#include FT_FREETYPE_H
#include <atomic>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

namespace {
bool fromQt(void *caller)
{
    Dl_info info{};
    return dladdr(caller, &info) && info.dli_fname && std::strstr(info.dli_fname, "libQt6Gui");
}
std::atomic<unsigned> loads{0}, rasters{0}, sizes{0};
}

extern "C" FT_Error FT_Set_Char_Size(FT_Face face, FT_F26Dot6 width, FT_F26Dot6 height,
                                    FT_UInt horizontal, FT_UInt vertical)
{
    static const auto original = reinterpret_cast<decltype(&FT_Set_Char_Size)>(dlsym(RTLD_NEXT, "FT_Set_Char_Size"));
    if (fromQt(__builtin_return_address(0)) && sizes.fetch_add(1) < 64)
        std::fprintf(stderr, "FONTREAL_TRACE size width=%ld height=%ld dpi=%u,%u family=%s\n",
                     width, height, horizontal, vertical, face->family_name ? face->family_name : "");
    return original(face, width, height, horizontal, vertical);
}

extern "C" FT_Error FT_Load_Glyph(FT_Face face, FT_UInt glyph, FT_Int32 flags)
{
    static const auto original = reinterpret_cast<decltype(&FT_Load_Glyph)>(dlsym(RTLD_NEXT, "FT_Load_Glyph"));
    if (fromQt(__builtin_return_address(0)) && loads.fetch_add(1) < 64)
        std::fprintf(stderr, "FONTREAL_TRACE load flags=0x%x family=%s glyph=%u\n",
                     unsigned(flags), face->family_name ? face->family_name : "", glyph);
    return original(face, glyph, flags);
}

extern "C" FT_Error FT_Render_Glyph(FT_GlyphSlot slot, FT_Render_Mode mode)
{
    static const auto original = reinterpret_cast<decltype(&FT_Render_Glyph)>(dlsym(RTLD_NEXT, "FT_Render_Glyph"));
    if (fromQt(__builtin_return_address(0)) && rasters.fetch_add(1) < 64)
        std::fprintf(stderr, "FONTREAL_TRACE raster mode=%d family=%s\n", int(mode),
                     slot->face->family_name ? slot->face->family_name : "");
    return original(slot, mode);
}
