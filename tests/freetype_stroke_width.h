/* Test-only width policy. One physical pixel is 64 FreeType units. */
#ifndef FONTREAL_TEST_STROKE_WIDTH_H
#define FONTREAL_TEST_STROKE_WIDTH_H

static FT_Pos
fontreal_test_stroke_width(FT_Pos width, int half_minimum)
{
    FT_Pos distance = width < 0 ? -width : width;
    if (!distance)
        return 0;
    if (half_minimum && distance < 32)
        distance = 32;
    else {
        distance = (distance + 32) & ~63L;
        if (!distance)
            distance = 64;
    }
    return width < 0 ? -distance : distance;
}

#endif
