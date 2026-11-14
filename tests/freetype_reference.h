#pragma once
#include <QLibrary>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MODULE_H
#include FT_MULTIPLE_MASTERS_H
#include <stdexcept>

// Load the independently built reference without replacing Qt's FreeType provider.
struct FontrealReference {
    QLibrary library;
#define FT_REFERENCE_MEMBER(name) decltype(&name) name##_reference = &name;
    FT_REFERENCE_MEMBER(FT_Init_FreeType)
    FT_REFERENCE_MEMBER(FT_Done_FreeType)
    FT_REFERENCE_MEMBER(FT_New_Face)
    FT_REFERENCE_MEMBER(FT_Done_Face)
    FT_REFERENCE_MEMBER(FT_Set_Char_Size)
    FT_REFERENCE_MEMBER(FT_Get_Char_Index)
    FT_REFERENCE_MEMBER(FT_Load_Glyph)
    FT_REFERENCE_MEMBER(FT_Load_Char)
    FT_REFERENCE_MEMBER(FT_Render_Glyph)
    FT_REFERENCE_MEMBER(FT_Select_Charmap)
    FT_REFERENCE_MEMBER(FT_Property_Set)
    FT_REFERENCE_MEMBER(FT_Get_MM_Var)
    FT_REFERENCE_MEMBER(FT_Set_Var_Design_Coordinates)
    FT_REFERENCE_MEMBER(FT_Done_MM_Var)
#undef FT_REFERENCE_MEMBER
    FontrealReference() {
        const auto path = qgetenv("FONTREAL_TEST_REFERENCE_FREETYPE");
        if (path.isEmpty()) return;
        library.setFileName(QString::fromLocal8Bit(path));
        library.setLoadHints(QLibrary::ResolveAllSymbolsHint | QLibrary::DeepBindHint | QLibrary::PreventUnloadHint);
        if (!library.load()) throw std::runtime_error("Cannot load independent FreeType reference");
#define FT_REFERENCE_LOAD(name) \
        name##_reference = reinterpret_cast<decltype(&name)>(library.resolve(#name)); \
        if (!name##_reference) throw std::runtime_error("Missing reference function " #name);
        FT_REFERENCE_LOAD(FT_Init_FreeType)
        FT_REFERENCE_LOAD(FT_Done_FreeType)
        FT_REFERENCE_LOAD(FT_New_Face)
        FT_REFERENCE_LOAD(FT_Done_Face)
        FT_REFERENCE_LOAD(FT_Set_Char_Size)
        FT_REFERENCE_LOAD(FT_Get_Char_Index)
        FT_REFERENCE_LOAD(FT_Load_Glyph)
        FT_REFERENCE_LOAD(FT_Load_Char)
        FT_REFERENCE_LOAD(FT_Render_Glyph)
        FT_REFERENCE_LOAD(FT_Select_Charmap)
        FT_REFERENCE_LOAD(FT_Property_Set)
        FT_REFERENCE_LOAD(FT_Get_MM_Var)
        FT_REFERENCE_LOAD(FT_Set_Var_Design_Coordinates)
        FT_REFERENCE_LOAD(FT_Done_MM_Var)
#undef FT_REFERENCE_LOAD
    }
};
inline FontrealReference &fontrealReference() { static FontrealReference reference; return reference; }
#define FT_Init_FreeType fontrealReference().FT_Init_FreeType_reference
#define FT_Done_FreeType fontrealReference().FT_Done_FreeType_reference
#define FT_New_Face fontrealReference().FT_New_Face_reference
#define FT_Done_Face fontrealReference().FT_Done_Face_reference
#define FT_Set_Char_Size fontrealReference().FT_Set_Char_Size_reference
#define FT_Get_Char_Index fontrealReference().FT_Get_Char_Index_reference
#define FT_Load_Glyph fontrealReference().FT_Load_Glyph_reference
#define FT_Load_Char fontrealReference().FT_Load_Char_reference
#define FT_Render_Glyph fontrealReference().FT_Render_Glyph_reference
#define FT_Select_Charmap fontrealReference().FT_Select_Charmap_reference
#define FT_Property_Set fontrealReference().FT_Property_Set_reference
#define FT_Get_MM_Var fontrealReference().FT_Get_MM_Var_reference
#define FT_Set_Var_Design_Coordinates fontrealReference().FT_Set_Var_Design_Coordinates_reference
#define FT_Done_MM_Var fontrealReference().FT_Done_MM_Var_reference
