std::vector<bool> exteriorMask(const fontreal_v3::OutlineSamples &samples, unsigned background)
{
    const int pitch = samples.pitch;
    const int rows = samples.pixels.size() / pitch;
    const auto &source = samples.pixels;
    std::vector<bool> exterior(source.size());
    std::vector<int> visit{0};
    exterior[0] = true;
    for (std::size_t i = 0; i < visit.size(); ++i) {
        const int at = visit[i];
        const int x = at % pitch, y = at / pitch;
        const int neighbors[] = {
            x > 0 ? at - 1 : at, x + 1 < pitch ? at + 1 : at,
            y > 0 ? at - pitch : at, y + 1 < rows ? at + pitch : at,
        };
        for (int next : neighbors) {
            if (!exterior[next] && source[next] <= background) {
                exterior[next] = true;
                visit.push_back(next);
            }
        }
    }
    return exterior;
}

// Trial: give closed counters clearance while keeping narrow walls intact.
void deepenCores(std::vector<fontreal_v3::Coverage> &values, const fontreal_v3::OutlineSamples &samples, fontreal_v3::Ink ink)
{
    const int width = samples.frame.width, height = samples.frame.height;
    const auto at = [&](int x, int y) {
        return x >= 0 && y >= 0 && x < width && y < height ? int(samples.center(x, y)) : 0;
    };
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int raw = at(x, y);
            if (raw <= 157 || std::max({at(x - 1, y), at(x + 1, y), at(x, y - 1), at(x, y + 1)}) < 170)
                continue;
            auto &value = values[y * width + x];
            const double t = std::clamp((raw - 157) / 70.0, 0.0, 1.0);
            const double strength = ink == fontreal_v3::Ink::Dark ? 0.44 : 0.34;
            value += std::lround((255 - value) * strength * t * t * (3 - 2 * t));
        }
    }
}

bool continuousInk(const fontreal_v3::OutlineSamples &samples, int x, int y, int dx, int dy)
{
    constexpr int scale = 4;
    const int startX = x * scale + (dx > 0 ? scale - 1 : 0);
    const int startY = y * scale + (dy > 0 ? scale - 1 : 0);
    constexpr int contact = 52;
    if (dx && dy) {
        for (int offset = 0; offset < 2; ++offset) {
            const auto acrossX = std::min(samples.highPixel(startX, startY - offset * dy),
                                          samples.highPixel(startX + dx, startY + dy + offset * dy));
            const auto acrossY = std::min(samples.highPixel(startX - offset * dx, startY),
                                          samples.highPixel(startX + dx + offset * dx, startY + dy));
            if (std::max(acrossX, acrossY) >= contact)
                return true;
        }
        return false;
    }

    for (int i = 0; i < scale; ++i) {
        const int px = startX + (dy ? i : 0);
        const int py = startY + (dx ? i : 0);
        if (samples.highPixel(px, py) >= contact && samples.highPixel(px + dx, py + dy) >= contact)
            return true;
    }
    return false;
}

void liftBridges(std::vector<fontreal_v3::Coverage> &values,
                 const std::vector<fontreal_v3::Coverage> &source, const fontreal_v3::OutlineSamples &samples,
                 fontreal_v3::Ink ink, const fontreal_v3::OutlineSamples *native = nullptr)
{
    const int width = samples.frame.width, height = samples.frame.height;
    const auto inside = [&](int x, int y) { return x >= 0 && y >= 0 && x < width && y < height; };
    const auto raw = [&](int x, int y) { return inside(x, y) ? int(samples.center(x, y)) : 0; };
    const auto coverage = [&](int x, int y) { return int(source[y * width + x]); };
    const auto center = [&](int x, int y, int dx, int dy) {
        constexpr int scale = 4;
        double total = 0, position = 0;
        for (int cross = -scale; cross < 2 * scale; ++cross) {
            const int peer = cross < 0 ? -1 : cross >= scale ? 1 : 0;
            if (peer && (raw(x + peer * dy, y + peer * dx) > raw(x,y) ||
                         !continuousInk(samples, x, y, peer * dy, peer * dx)))
                continue;
            for (int along = 0; along < scale; ++along) {
                const int ink = samples.highPixel(x * scale + along * dx + cross * dy,
                                                  y * scale + along * dy + cross * dx);
                total += ink;
                position += (cross + .5) * ink;
            }
        }
        return dy * x + dx * y + (total ? position / total / scale : .5);
    };
    struct Anchor { int ink = 0, distance = 1; double center = 0; };
    const auto trace = [&](int x, int y, int dx, int dy) {
        Anchor anchor;
        for (int step = 1; step <= 3; ++step) {
            int best = 0, across = 0;
            for (int edge : {0, -1, 1}) {
                const int deltaX = dx + edge * dy, deltaY = dy + edge * dx;
                const int support = raw(x + deltaX, y + deltaY);
                const bool repaired = native && support >= 92 && raw(x, y) >= 92
                        && coverage(x, y) >= 60 && coverage(x + deltaX, y + deltaY) >= 60;
                if (support > best && (repaired || continuousInk(samples, x, y, deltaX, deltaY))) {
                    best = support;
                    across = edge;
                }
            }
            if (best < 48)
                break;
            x += dx + across * dy;
            y += dy + across * dx;
            if (coverage(x,y) > anchor.ink)
                anchor = {coverage(x,y), step, center(x,y,std::abs(dx),std::abs(dy))};
        }
        return anchor;
    };
    const bool dark = ink == fontreal_v3::Ink::Dark;
    const double amount = dark ? 0.70 : 0.30;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int shape = raw(x, y);
            const int before = coverage(x, y);
            if (native && (native->center(x, y) > 41 || shape - native->center(x, y) < 47))
                continue;
            if (shape < 62 || before < 57 || before > (dark ? 200 : 229))
                continue;
            double lift = 0;
            for (int dx : {0, 1}) {
                const int dy = 1 - dx;
                if (shape <= std::max(raw(x + dy, y + dx), raw(x - dy, y - dx)) + 4)
                    continue;
                const auto left = trace(x, y, -dx, -dy);
                const auto right = trace(x, y, dx, dy);
                if (std::min(left.ink, right.ink) < before + 14)
                    continue;
                const double at = center(x, y, dx, dy);
                const double bend = std::abs((left.center - at) / left.distance +
                                             (right.center - at) / right.distance);
                // A bridge recovered from the outline already has a visible pixel on this path.
                const double gate = native ? 1.0 : std::clamp((bend - 0.12) / 0.30, 0.0, 1.0);
                const double target = (left.ink * right.distance + right.ink * left.distance) /
                                      double(left.distance + right.distance);
                lift = std::max(lift, std::min(dark ? 54.0 : 18.0, amount * gate * (target - before)));
            }
            auto &value = values[y * width + x];
            value = std::max(int(value), int(before + std::lround(lift)));
        }
    }
}

// Move the outline of an enclosed space before the renderer samples any ink.
bool expandInnerContours(FT_Outline &outline, FT_Vector strength)
{
    if (outline.n_contours < 2 || (outline.flags & FT_OUTLINE_EVEN_ODD_FILL))
        return false;
    const auto fill = FT_Outline_Get_Orientation(&outline);
    if (fill == FT_ORIENTATION_NONE)
        return false;

    // Each view borrows one contour from the private glyph outline.
    bool changed = false;
    int first = 0;
    for (int i = 0; i < outline.n_contours; ++i) {
        const int next = outline.contours[i] + 1;
        auto last = static_cast<std::remove_pointer_t<decltype(outline.contours)>>(next - first - 1);
        FT_Outline contour{1, static_cast<decltype(outline.n_points)>(last + 1), outline.points + first, outline.tags + first, &last, 0};
        first = next;
        const auto winding = FT_Outline_Get_Orientation(&contour);
        if (last < 2 || winding == fill || winding == FT_ORIENTATION_NONE)
            continue;
        FT_BBox bounds{};
        FT_Outline_Get_CBox(&contour, &bounds);
        if (bounds.xMax - bounds.xMin < 24 || bounds.yMax - bounds.yMin < 24)
            continue;
        if (!FT_Outline_EmboldenXY(&contour, strength.x, strength.y)) {
            FT_Outline_Translate(&contour, -strength.x / 2, -strength.y / 2);
            changed = true;
        }
    }
    return changed;
}

fontreal_v3::OutlineSamples sampleWithClearance(FT_Library library, const FT_Outline &outline,
                                                Frame frame, FT_Pos strength)
{
    using namespace fontreal_v3;
    auto original = sampleOutline(library, outline, frame);
    if (original.pixels.empty() || outline.n_contours < 2)
        return original;

    constexpr unsigned threshold = 64;
    const auto originalExterior = exteriorMask(original, threshold);
    FT_Outline candidate = outline;
    std::vector<FT_Vector> points(outline.n_points);
    candidate.points = points.data();

    const FT_Vector adjustments[] = {
        {strength, strength}, {strength, strength / 3}, {strength, 0},
        {strength * 2 / 3, strength * 2 / 3}, {strength * 2 / 3, 0}, {strength / 3, 0},
    };
    for (const auto request : adjustments) {
        std::copy_n(outline.points, outline.n_points, points.begin());
        if (!expandInnerContours(candidate, request))
            break;
        auto fitted = sampleOutline(library, candidate, frame);
        if (fitted.pixels.empty())
            continue;
        const auto fittedExterior = exteriorMask(fitted, threshold);
        bool valid = true;
        for (std::size_t p = 0; p < original.pixels.size(); ++p) {
            const bool enclosed = original.pixels[p] <= threshold && !originalExterior[p];
            if (fitted.pixels[p] > original.pixels[p] + 2 || (enclosed && fittedExterior[p])) {
                valid = false;
                break;
            }
        }
        if (valid)
            return fitted;
    }
    return original;
}
