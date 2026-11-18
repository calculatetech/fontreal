/* Test-only access to private state. Rendering uses public FreeType calls. */
#include <freetype/internal/ftobjs.h>
int fontreal_test_darkening(FT_Face face) { return face->internal->no_stem_darkening; }
long fontreal_test_load_flags(FT_GlyphSlot slot) { return slot->internal->load_flags; }
