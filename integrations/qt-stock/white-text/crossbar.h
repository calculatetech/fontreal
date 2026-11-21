struct Wall {
    int first = -1;
    int last = -1;
};

std::vector<Wall> middleWalls(const fontreal_v3::OutlineSamples &samples)
{
    const int width = 4 * samples.frame.width, height = 4 * samples.frame.height;
    const int pad = (samples.pitch - width) / 2;
    constexpr int threshold = 64;
    const auto exterior = exteriorMask(samples, threshold);
    const auto outside = [&](int x, int y) { return exterior[(y+pad)*samples.pitch+x+pad]; };

    std::vector<Wall> walls(width);
    for (int x = 0; x < width; ++x) {
        for (int y = 2; y < height - 5; ++y) {
            if (outside(x,y) || samples.highPixel(x,y)>threshold || samples.highPixel(x,y+1)<=threshold)
                continue;
            int end = y + 1;
            while (end < height && samples.highPixel(x,end)>threshold)
                ++end;
            const double center = (y+1+end)/2.0;
            if (end-y-1 <= 5 && center >= .23*height && center <= .70*height && outside(x,end))
                walls[x] = {y+1,end};
        }
    }
    return walls;
}

struct WallSpan {
    int first = 0;
    int last = 0;
    int row = 0;
};

WallSpan longestWall(const std::vector<Wall> &walls)
{
    WallSpan result;
    for (int x = 0, width = walls.size(); x < width;) {
        if (walls[x].first < 0) {
            ++x;
            continue;
        }
        const int first = x++;
        double centers = (walls[first].first+walls[first].last)/2.0;
        while (x < width && walls[x].first >= 0
                && std::abs((walls[x].first+walls[x].last)-(walls[x-1].first+walls[x-1].last)) <= 3) {
            centers += (walls[x].first+walls[x].last)/2.0;
            ++x;
        }
        if (x-first > result.last-result.first)
            result = {first,x,int(centers/(x-first)/4)};
    }
    return result;
}

// Extend the outer arc at its widest visible point and taper back into the outline.
void supportOutsideTurn(fontreal_v3::OutlineSamples &samples, const fontreal_v3::OutlineSamples &original,
                        std::vector<fontreal_v3::Coverage> &coverage, const fontreal_v3::CoverageTable &tone,
                        int crossbarRow)
{
    constexpr int scale = 4;
    const int width = samples.frame.width;
    const int height = samples.frame.height;
    const int pad = (samples.pitch - scale * width) / 2;
    constexpr double reach = .95;
    const double apex = scale * (crossbarRow - 1.5);
    bool changed[3]{};
    for (int y = std::max(0,scale*(crossbarRow-3)); y < std::min(scale*height,scale*crossbarRow); ++y) {
        const double radial = std::clamp(1 - std::abs(y + .5 - apex)/3.05,0.0,1.0);
        if (!radial)
            continue;
        int last = scale*width-1;
        while (last >= 0 && original.highPixel(last,y) < 20)
            --last;
        if (last < scale*(width-1)-1)
            continue;
        const double edge = last + original.highPixel(last,y)/255.0;
        const double end = std::min(double(scale*width),edge + reach*radial*radial*(3-2*radial));
        for (int x = last; x < scale*width && x < end; ++x) {
            auto &value = samples.pixels[(y+pad)*samples.pitch+x+pad];
            const auto proposed = std::lround(255*std::clamp(end-x,0.0,1.0));
            if (proposed > value) {
                value = proposed;
                changed[y/scale-crossbarRow+3] = true;
            }
        }
    }
    for (int i=0; i<3; ++i) {
        const int y=crossbarRow-3+i;
        if (!changed[i] || y < 0)
            continue;
        auto &value=coverage[y*width+width-1];
        value=std::max(value,tone[samples.center(width-1,y)]);
    }
}

// Fit an existing thin wall between a counter and an opening to one pixel row.
QByteArray fitCrossbar(fontreal_v3::OutlineSamples &samples, const fontreal_v3::OutlineSamples &reference,
                       std::vector<fontreal_v3::Coverage> &coverage, const fontreal_v3::CoverageTable &tone,
                       fontreal_v3::Ink ink)
{
    const int width=samples.frame.width, height=samples.frame.height;
    if (width < 4 || height < 5)
        return {};
    auto walls = middleWalls(samples);
    auto span = longestWall(walls);
    const bool needsReference = span.last-span.first < 10 && !reference.pixels.empty();
    if (needsReference) {
        walls = middleWalls(reference);
        span = longestWall(walls);
    }
    if (span.last-span.first < 10 || span.row < 1 || span.row >= height - 2)
        return {};
    const int coreBegin = (span.first + 4) / 4;
    int coreEnd = (span.last - 1) / 4;
    const double targetCenter = 4 * span.row + 2;
    while (coreEnd - coreBegin > 2) {
        double center = 0;
        for (int x = 4*(coreEnd-1); x < 4*coreEnd; ++x)
            center += (walls[x].first + walls[x].last) / 8.0;
        if (targetCenter - center < 1.45)
            break;
        --coreEnd;
    }
    if (coreEnd - coreBegin < 2)
        return {};
    int weak = 0;
    for (int x = coreBegin; x < coreEnd; ++x)
        weak += coverage[span.row*width+x] < 203;
    if (weak + 1 < coreEnd-coreBegin || !weak)
        return {};

    const bool rises = coreEnd < width && !coverage[span.row*width+coreEnd]
            && coverage[(span.row-1)*width+coreEnd] > 70 && span.last > 4*coreEnd;
    const int riseBegin = 4*(coreEnd-1);
    const auto original = samples;
    const int pad = (samples.pitch - 4*width)/2;
    const auto set = [&](int x, int y, fontreal_v3::Coverage value) {
        samples.pixels[(y+pad)*samples.pitch+x+pad] = value;
    };

    const auto &guide = needsReference ? reference : original;
    for (int x = span.first; x < span.last; ++x) {
        const auto &wall = walls[x];
        const int target = 4*span.row;
        const bool insideCore = x >= 4*coreBegin && x < 4*coreEnd;
        const double distance = std::clamp(double(span.last-x-.5) / std::max(1,span.last-4*coreEnd),0.0,1.0);
        const double curvedEnd = distance*distance*(3-2*distance);
        const double taper = insideCore ? 1.0 :
                x >= 4*coreEnd ? curvedEnd : std::clamp(.14 + .10 * (x-span.first),0.0,.40);
        const double first = wall.first + .5*(1-guide.highPixel(x,wall.first)/255.0);
        const double last = wall.last - .5*(1-guide.highPixel(x,wall.last-1)/255.0);
        const bool turn = rises && x >= riseBegin;
        double newFirst = first + taper*(target-first);
        double newLast = last + taper*(target+4-last);
        if (turn) {
            const double progress = (x-riseBegin+.5)/(span.last-riseBegin);
            const double curve = progress*progress*(3-2*progress);
            const double center = target + 2 - 4*curve;
            const double half = 2 - .38*curve;
            newFirst = center - half;
            newLast = center + half;
        }
        for (int y = std::max(0,std::min(wall.first-1,int(std::floor(newFirst))));
             y < std::min(4*height,std::max(wall.last+1,int(std::ceil(newLast)))); ++y) {
            const auto value=original.highPixel(x,y);
            const auto fitted=std::lround(255*std::clamp(std::min(newLast,y+1.0)-std::max(newFirst,double(y)),0.0,1.0));
            const bool oldWall = insideCore && ((y >= wall.first && y < wall.last) || value <= 64);
            set(x,y,oldWall ? fitted : std::max(int(value),int(fitted)));
        }
    }

    QByteArray anchors(width*height,'\0');
    for (int y = 0; y < height; ++y) {
        for (int x = span.first/4; x <= (span.last-1)/4; ++x) {
            auto &value=coverage[y*width+x];
            const int before=original.center(x,y);
            const int after=samples.center(x,y);
            const bool insideCore = x >= coreBegin && x < coreEnd;
            if (rises && x == coreEnd-1 && (y == span.row || y == span.row-1)) {
                value = std::clamp(int(tone[after]) + (y == span.row-1 ? 19 : 0), 0, 242);
                continue;
            }
            if (y == span.row) {
                const int lift = std::max(0,int(tone[after])-value);
                if (insideCore) {
                    value += lift;
                } else if (x < coreBegin) {
                    value += std::min(lift,32);
                } else if (x == coreEnd && value && 4*x < span.last) {
                    const int amount = ink == fontreal_v3::Ink::Dark ? 45 : 34;
                    const int room = std::max(0,185 - int(value));
                    value += std::min(room,amount);
                }
                if (after >= 250 && x >= coreBegin && x < coreEnd) {
                    value=255;
                    anchors[y*width+x]=char(255);
                }
            } else if (insideCore && std::abs(y-span.row)<=1 && before > after) {
                value=std::min(value,tone[after]);
            } else if (y == span.row-1 && x == coreEnd && value &&
                       !coverage[span.row*width+x] && 4*x < span.last) {
                const int amount = ink == fontreal_v3::Ink::Dark ? 43 : 34;
                value += std::min(amount,std::max(0,225 - int(value)));
            }
        }
    }
    if (rises)
        supportOutsideTurn(samples, original, coverage, tone, span.row);
    return anchors;
}
