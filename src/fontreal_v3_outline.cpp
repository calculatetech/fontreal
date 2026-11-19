#include "fontreal_v3_outline.h"

#include <algorithm>
#include <limits>

namespace fontreal_v3 {
namespace {

constexpr int scale = 4;
constexpr int pad = 3 * scale;

Coverage shifted(unsigned near, unsigned far)
{
    const unsigned sum = 2 * near + far;
    const unsigned area = scale * scale * 3;
    const unsigned remainder = sum % area;
    const unsigned value = sum / area;
    return static_cast<Coverage>(value + (remainder * 2 > area || (remainder * 2 == area && (value & 1))));
}

} // namespace

OutlineSamples sampleOutline(FT_Library library, const FT_Outline &outline, GlyphFrame frame)
{
    if (frame.width <= 0 || frame.height <= 0 || outline.n_points <= 0)
        return {};

    constexpr int maxSide = (std::numeric_limits<int>::max() - 2 * pad) / scale;
    if (frame.width > maxSide || frame.height > maxSide)
        return {};
    const int pitch = frame.width * scale + 2 * pad;
    const int rows = frame.height * scale + 2 * pad;
    OutlineSamples result{frame, pitch, std::vector<Coverage>(static_cast<std::size_t>(pitch) * rows)};
    std::vector<FT_Vector> points(outline.points, outline.points + outline.n_points);
    const FT_Pos left = FT_Pos(frame.left) * scale - pad;
    const FT_Pos bottom = (FT_Pos(frame.top) - frame.height) * scale - pad;
    for (FT_Vector &point : points) {
        point.x = scale * point.x - left * 64;
        point.y = scale * point.y - bottom * 64;
    }
    FT_Outline expanded = outline;
    expanded.points = points.data();

    FT_Bitmap bitmap{};
    bitmap.width = pitch;
    bitmap.rows = rows;
    bitmap.pitch = pitch;
    bitmap.buffer = result.pixels.data();
    bitmap.num_grays = 256;
    bitmap.pixel_mode = FT_PIXEL_MODE_GRAY;
    if (FT_Outline_Get_Bitmap(library, &expanded, &bitmap))
        return {};
    return result;
}

Coverage OutlineSamples::highPixel(int x, int y) const
{
    return pixels[static_cast<std::size_t>(y + pad) * pitch + x + pad];
}

unsigned OutlineSamples::blockSum(int x, int y, int dx, int dy) const
{
    const int startX = x * scale + pad + dx;
    const int startY = y * scale + pad + dy;
    unsigned sum = 0;
    for (int row = 0; row < scale; ++row) {
        const auto *first = pixels.data() + static_cast<std::size_t>(startY + row) * pitch + startX;
        for (int col = 0; col < scale; ++col)
            sum += first[col];
    }
    return sum;
}

Coverage OutlineSamples::center(int x, int y) const
{
    constexpr int area = scale * scale;
    return static_cast<Coverage>((blockSum(x, y) + area / 2) / area);
}

Channels OutlineSamples::stripes(int x, int y, StripeLayout layout) const
{
    const Coverage gray = center(x, y);
    if (layout == StripeLayout::None)
        return {gray, gray, gray};

    const bool vertical = layout == StripeLayout::VerticalRgb || layout == StripeLayout::VerticalBgr;
    const int dx = vertical ? 0 : 1;
    const int dy = vertical ? 1 : 0;
    Coverage first = shifted(blockSum(x, y, -dx, -dy), blockSum(x, y, -2 * dx, -2 * dy));
    Coverage last = shifted(blockSum(x, y, dx, dy), blockSum(x, y, 2 * dx, 2 * dy));
    if (layout == StripeLayout::Bgr || layout == StripeLayout::VerticalBgr)
        std::swap(first, last);
    return {first, gray, last};
}

} // namespace fontreal_v3
