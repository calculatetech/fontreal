/* Test-only snapshots; expand inside aflatin.c after its types are defined. */
#define FONTREAL_CURVE_POINTS(hints, glyph, dim, stage)                    \
  do {                                                                  \
    FT_Int fr_i;                                                        \
    FT_TRACE6(( "FR_STAGE glyph=%u dim=%d stage=%s count=%d\n",            \
                glyph, dim, stage, (hints)->num_points ));               \
    for (fr_i = 0; fr_i < (hints)->num_points; fr_i++) {                  \
      AF_Point fr_p = (hints)->points + fr_i;                            \
      FT_TRACE6(( "FR_POINT id=%d x=%ld y=%ld ox=%ld oy=%ld flags=%u "    \
                  "prev=%td next=%td\n",                                \
                  fr_i, fr_p->x, fr_p->y, fr_p->ox, fr_p->oy,             \
                  fr_p->flags, fr_p->prev - (hints)->points,             \
                  fr_p->next - (hints)->points ));                       \
    }                                                                   \
  } while (0)
