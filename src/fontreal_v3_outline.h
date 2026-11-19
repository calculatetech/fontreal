#pragma once

#include "fontreal_v3_coverage.h"

#include <ft2build.h>
#include FT_OUTLINE_H

#include <vector>

namespace fontreal_v3 {

enum class StripeLayout { None, Rgb, Bgr, VerticalRgb, VerticalBgr };

// Bearings use FreeType coordinates. Top increases upward.
struct GlyphFrame {
    int left = 0;
    int top = 0;
    int width = 0;
    int height = 0;
};

struct OutlineSamples {
    GlyphFrame frame;
    int pitch = 0;
    std::vector<Coverage> pixels;

    Coverage highPixel(int x, int y) const;
    unsigned blockSum(int x, int y, int dx = 0, int dy = 0) const;
    Coverage center(int x, int y) const;
    Channels stripes(int x, int y, StripeLayout layout) const;
};

// The frame comes from a native-size grayscale raster of the same outline.
OutlineSamples sampleOutline(FT_Library library, const FT_Outline &outline, GlyphFrame frame);

// For light faces the unhinted reference is registered in the hinted frame.
std::vector<Coverage> glyphCoverage(const OutlineSamples &hinted, const OutlineSamples *unhinted,
                                    const CoverageTable &tone, double pixelSize, Ink ink, bool italic);

} // namespace fontreal_v3
