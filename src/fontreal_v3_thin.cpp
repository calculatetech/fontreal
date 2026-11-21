#include "fontreal_v3_outline.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <tuple>
#include <utility>

namespace fontreal_v3 {
namespace {

struct Offset {
    int x;
    int y;
};

constexpr std::array<Offset, 2> directions{{{1, 0}, {0, 1}}};
constexpr int sampling = 4;

template<class Value>
struct Grid {
    int width;
    int height;
    std::vector<Value> values;

    Grid(int w, int h) : width(w), height(h), values(static_cast<std::size_t>(w) * h) {}

    std::size_t index(int x, int y) const { return static_cast<std::size_t>(y) * width + x; }
    Value at(int x, int y) const
    {
        return x >= 0 && x < width && y >= 0 && y < height ? values[index(x, y)] : Value{};
    }
    Value &pixel(int x, int y) { return values[index(x, y)]; }
};

using Mask = Grid<Coverage>;

double smooth(double low, double high, double value)
{
    const double t = std::clamp((value - low) / (high - low), 0.0, 1.0);
    return t * t * (3 - 2 * t);
}

Coverage rounded(double value)
{
    return static_cast<Coverage>(std::nearbyint(std::clamp(value, 0.0, 255.0)));
}

Mask centeredMask(const OutlineSamples &samples)
{
    Mask mask(samples.frame.width, samples.frame.height);
    for (int y = 0; y < mask.height; ++y) {
        for (int x = 0; x < mask.width; ++x)
            mask.pixel(x, y) = samples.center(x, y);
    }
    return mask;
}

Mask alignedMask(const Mask &raw, const OutlineSamples &reference)
{
    double weight = 0;
    for (Coverage pixel : raw.values)
        weight += smooth(52, 195, pixel);
    weight = std::max(1.0, weight);

    Offset best{0, 0};
    double bestScore = std::numeric_limits<double>::infinity();
    const auto phaseOrder = [](Offset offset) {
        return std::make_tuple(offset.x * offset.x + offset.y * offset.y,
                               std::abs(offset.x), std::abs(offset.y), offset.x, offset.y);
    };
    for (int dy = -2; dy <= 2; ++dy) {
        for (int dx = -2; dx <= 2; ++dx) {
            double error = 0;
            for (int y = 0; y < raw.height; ++y) {
                for (int x = 0; x < raw.width; ++x) {
                    const double before = raw.at(x, y);
                    const double delta = reference.blockSum(x, y, dx, dy) / 16.0 - before;
                    error += smooth(52, 195, before) * delta * delta;
                }
            }
            const double score = error / weight + 52 * (dx * dx + dy * dy);
            if (score < bestScore || (score == bestScore && phaseOrder({dx, dy}) < phaseOrder(best))) {
                bestScore = score;
                best = {dx, dy};
            }
        }
    }

    Mask result(raw.width, raw.height);
    for (int y = 0; y < raw.height; ++y) {
        for (int x = 0; x < raw.width; ++x)
            result.pixel(x, y) = rounded(reference.blockSum(x, y, best.x, best.y) / 16.0);
    }
    return result;
}

int continuation(const Mask &mask, int x, int y, Offset axis)
{
    const auto side = [&](int along) {
        int largest = 0;
        for (int across = -1; across <= 1; ++across) {
            largest = std::max(largest, int(mask.at(x + along * axis.x + across * axis.y,
                                                     y + along * axis.y + across * axis.x)));
        }
        return largest;
    };
    return std::min(side(-1), side(1));
}

Coverage bridge(const Mask &raw, const Mask &reference, int x, int y, double taper, bool strong)
{
    const double native = raw.at(x, y);
    const Coverage sampled = reference.at(x, y);
    const double source = sampled;
    const auto originalGate = [sampled](int low, int high) {
        // The accepted bridge subtracts these two thresholds in a byte array.
        return smooth(0, high - low, static_cast<Coverage>(sampled - low));
    };
    double lift = 0;
    for (Offset axis : directions) {
        const double near = raw.at(x - axis.y, y - axis.x);
        const double far = raw.at(x + axis.y, y + axis.x);
        const double referenceNear = reference.at(x - axis.y, y - axis.x);
        const double referenceFar = reference.at(x + axis.y, y + axis.x);
        const double sourceSide = std::max(referenceNear, referenceFar);
        const double nativeSide = std::max(near, far);
        const double loss = source + referenceNear + referenceFar - native - near - far;
        const double anchor = continuation(reference, x, y, axis);
        const double nativeAnchor = continuation(raw, x, y, axis);

        if (strong) {
            double gate = smooth(17, 74, loss) * smooth(24, 94, anchor)
                        * (1 - smooth(118, 205, nativeSide))
                        * (1 - smooth(30, 105, sourceSide - source));
            if (native == 0) {
                gate *= smooth(28, 72, nativeAnchor) * smooth(58, 133, source)
                      * (1 - smooth(35, 101, nativeSide));
            }
            const double target = std::min(242.0, source + .36 * std::max(anchor - source, 0.0));
            lift = std::max(lift, std::max(target - native, 0.0) * gate * smooth(30, 80, source));
        } else {
            double gate = smooth(26, 103, anchor) * (1 - smooth(20, 93, sourceSide - source))
                        * (1 - smooth(120, 205, nativeSide)) * smooth(16, 76, loss);
            if (native == 0)
                gate *= .80 * smooth(42, 115, nativeAnchor) * originalGate(85, 142);
            lift = std::max(lift, std::max(source - native - 14, 0.0) * originalGate(34, 89) * gate);
        }
    }
    return rounded(native + taper * lift);
}

Mask sharpenedMask(const Mask &raw, const CoverageTable &tone, Ink ink)
{
    Grid<double> linear(raw.width, raw.height);
    std::array<Grid<double>, 2> weight{Grid<double>(raw.width, raw.height),
                                      Grid<double>(raw.width, raw.height)};
    for (int y = 0; y < raw.height; ++y) {
        for (int x = 0; x < raw.width; ++x) {
            linear.pixel(x, y) = linearInk(tone[raw.at(x, y)], ink);
            std::array<double, 2> support{};
            for (std::size_t i = 0; i < directions.size(); ++i) {
                const Offset axis = directions[i];
                double strokeWidth = 0;
                for (int offset = -2; offset <= 2; ++offset)
                    strokeWidth += raw.at(x + offset * axis.x, y + offset * axis.y) / 255.0;
                support[i] = (1 - smooth(.80, 1.65, strokeWidth))
                            * smooth(.15, .42, continuation(raw, x, y, {axis.y, axis.x}) / 255.0);
            }
            const double total = support[0] + support[1];
            if (total > 0) {
                for (std::size_t i = 0; i < directions.size(); ++i)
                    weight[i].pixel(x, y) = support[i] * support[i] / total;
            }
        }
    }
    auto sharpened = linear;
    for (std::size_t i = 0; i < directions.size(); ++i) {
        const Offset axis = directions[i];
        for (int y = 0; y < raw.height - axis.y; ++y) {
            for (int x = 0; x < raw.width - axis.x; ++x) {
                const int nextX = x + axis.x;
                const int nextY = y + axis.y;
                const double a = linear.at(x, y);
                const double b = linear.at(nextX, nextY);
                const auto [low, high] = std::minmax(a, b);
                const double normal = std::min(weight[i].at(x, y), weight[i].at(nextX, nextY));
                const double transfer = std::copysign(normal * std::min({.70 * (high - low), .43 * low,
                                                                         .45 * (1 - high)}), b - a);
                sharpened.pixel(x, y) -= transfer;
                sharpened.pixel(nextX, nextY) += transfer;
            }
        }
    }
    Mask result(raw.width, raw.height);
    for (std::size_t i = 0; i < raw.values.size(); ++i) {
        const Coverage original = tone[raw.values[i]];
        result.values[i] = original == 0 || original == 255 ? original
                         : std::clamp<Coverage>(encodedInk(sharpened.values[i], ink), 1, 254);
    }
    return result;
}

int radialArms(const OutlineSamples &samples)
{
    const int width = samples.pitch;
    const int height = static_cast<int>(samples.pixels.size() / width);
    const auto at = [&](int x, int y) {
        return samples.pixels[static_cast<std::size_t>(y) * width + x];
    };
    double mass = 0;
    double cx = 0;
    double cy = 0;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const int ink = at(x, y);
            if (ink >= 120) {
                mass += ink;
                cx += x * ink;
                cy += y * ink;
            }
        }
    }
    if (mass == 0)
        return 0;
    cx /= mass;
    cy /= mass;
    if (at(int(std::nearbyint(cx)), int(std::nearbyint(cy))) < 125)
        return 0;

    constexpr int sectors = 96;
    constexpr double tau = 6.283185307179586;
    std::array<double, sectors> reach{};
    for (int sector = 0; sector < sectors; ++sector) {
        const double angle = sector * tau / sectors;
        const double dx = std::cos(angle);
        const double dy = std::sin(angle);
        for (double radius = 0; radius < std::max(width, height) / 2.0; radius += .5) {
            const int x = std::clamp(int(std::nearbyint(cx + radius * dx)), 0, width - 1);
            const int y = std::clamp(int(std::nearbyint(cy + radius * dy)), 0, height - 1);
            if (at(x, y) >= 108)
                reach[sector] = radius;
        }
    }
    std::array<double, sectors> smoothed{};
    for (int sector = 0; sector < sectors; ++sector) {
        for (int neighbor = -3; neighbor <= 3; ++neighbor)
            smoothed[sector] += reach[(sector + neighbor + sectors) % sectors];
        smoothed[sector] /= 7;
    }
    auto ordered = smoothed;
    std::sort(ordered.begin(), ordered.end());
    const auto quantile = [&](double q) {
        const double index = q * (sectors - 1);
        const int low = static_cast<int>(index);
        return ordered[low] + (ordered[low + 1] - ordered[low]) * (index - low);
    };
    const double low = quantile(.23);
    const double high = quantile(.82);
    if (high - low < std::max(1.7, .24 * low))
        return 0;

    const double threshold = (low + high) / 2;
    int arms = 0;
    for (int sector = 0; sector < sectors; ++sector) {
        if (smoothed[sector] > threshold && smoothed[(sector + sectors - 1) % sectors] <= threshold)
            ++arms;
    }
    return arms;
}

double slantConfidence(const OutlineSamples &hinted, int x, int y)
{
    const int highX = x * sampling;
    const int highY = y * sampling;
    double dx = 0;
    double dy = 0;
    for (int row = highY; row < highY + sampling; ++row) {
        for (int col = highX; col < highX + sampling; ++col) {
            dx += std::abs(hinted.highPixel(col + 1, row) - hinted.highPixel(col - 1, row));
            dy += std::abs(hinted.highPixel(col, row + 1) - hinted.highPixel(col, row - 1));
        }
    }
    if (dx == 0)
        return 0;
    const double slope = dy / dx;
    return smooth(.045, .24, slope) * (1 - smooth(1.1, 2.6, slope)) * smooth(.15, 1.2, dx / 510);
}

double edgeFlux(const OutlineSamples &hinted, int x, int y)
{
    const int fringex = (x + 1) * sampling;
    int difference = 0;
    for (int row = y * sampling; row < (y + 1) * sampling; ++row)
        difference += hinted.highPixel(fringex - 1, row) - hinted.highPixel(fringex, row);
    return difference / (32.0 * 255);
}

void centerSpan(Grid<double> &ink, const OutlineSamples &hinted, int y, int start, int stop, double confidence)
{
    double coverage = 0;
    double moment = 0;
    double mass = 0;
    double inkMoment = 0;
    for (int x = start; x < stop; ++x) {
        for (int i = 0; i < sampling; ++i) {
            for (int j = 0; j < sampling; ++j) {
                const int sample = hinted.highPixel(x * sampling + i, y * sampling + j);
                coverage += sample;
                moment += sample * (x + (i + .5) / sampling - .5);
            }
        }
        mass += ink.at(x, y);
        inkMoment += ink.at(x, y) * x;
    }
    if (coverage == 0 || mass == 0)
        return;
    const double reference = moment / coverage;
    const double shift = std::clamp(reference - inkMoment / mass, -.20, .20);
    const int x = std::clamp(static_cast<int>(std::floor(reference)), start, stop - 2);
    const int donor = shift > 0 ? x : x + 1;
    const int receiver = shift > 0 ? x + 1 : x;
    const double move = std::min({.74 * confidence * mass * std::abs(shift), .23 * ink.at(donor, y),
                                  .23 * (1 - ink.at(receiver, y))});
    ink.pixel(donor, y) -= move;
    ink.pixel(receiver, y) += move;
}

void fitSlant(Mask &result, const Mask &raw, const Mask &protectedInk, const OutlineSamples &hinted, Ink polarity)
{
    Grid<double> linear(raw.width, raw.height);
    Grid<double> confidence(raw.width, raw.height);
    for (int y = 0; y < raw.height; ++y) {
        for (int x = 0; x < raw.width; ++x) {
            linear.pixel(x, y) = linearInk(result.at(x, y), polarity);
            confidence.pixel(x, y) = slantConfidence(hinted, x, y);
        }
    }

    auto fitted = linear;
    for (int y = 0; y < raw.height; ++y) {
        for (int x = 0; x < raw.width - 1; ++x) {
            const double left = linear.at(x, y);
            const double right = linear.at(x + 1, y);
            const double flux = edgeFlux(hinted, x, y);
            if (flux * (left - right) <= 0 || protectedInk.at(x, y) || protectedInk.at(x + 1, y))
                continue;
            const double recipient = raw.at(flux > 0 ? x + 1 : x, y);
            const double slope = std::max(confidence.at(x, y), confidence.at(x + 1, y));
            const double capacity = std::min(.17 * std::max(left, right), .27 * (1 - std::min(left, right)));
            const double transfer = std::min(std::abs(flux) * slope * smooth(5, 49, recipient), capacity);
            fitted.pixel(x, y) -= std::copysign(transfer, flux);
            fitted.pixel(x + 1, y) += std::copysign(transfer, flux);
        }
        for (int x = 0; x < raw.width;) {
            if (raw.at(x, y) < 5) {
                ++x;
                continue;
            }
            const int start = x;
            bool protectedSpan = false;
            double slope = 0;
            while (x < raw.width && raw.at(x, y) >= 5) {
                protectedSpan |= protectedInk.at(x, y) != 0;
                slope = std::max(slope, confidence.at(x, y));
                ++x;
            }
            if (x - start >= 2 && x - start <= 4 && !protectedSpan && slope >= .18)
                centerSpan(fitted, hinted, y, start, x, slope);
        }
    }
    for (std::size_t i = 0; i < result.values.size(); ++i)
        result.values[i] = encodedInk(fitted.values[i], polarity);
}

} // namespace

std::vector<Coverage> glyphCoverage(const OutlineSamples &hinted, const OutlineSamples *unhinted,
                                    const CoverageTable &tone, double pixelSize, Ink ink, bool italic)
{
    if (hinted.pixels.empty())
        return {};
    Mask raw = centeredMask(hinted);
    if (!unhinted || unhinted->pixels.empty()) {
        for (Coverage &pixel : raw.values)
            pixel = tone[pixel];
        return std::move(raw.values);
    }

    const Mask originalReference = centeredMask(*unhinted);
    const Mask alignedReference = alignedMask(raw, *unhinted);
    Mask result = sharpenedMask(raw, tone, ink);
    Mask protectedInk(raw.width, raw.height);
    const double taper = std::clamp((64.0 / 3 - pixelSize) * 3 / 8, 0.0, 1.0);
    for (int y = 0; y < raw.height; ++y) {
        for (int x = 0; x < raw.width; ++x) {
            const Coverage source = raw.at(x, y);
            const Coverage early = bridge(raw, originalReference, x, y, taper, false);
            const Coverage aligned = bridge(raw, alignedReference, x, y, taper, true);
            const Coverage registered = bridge(raw, originalReference, x, y, taper, true);
            const Coverage fill = source ? std::max(aligned, registered) : std::min(aligned, registered);
            const Coverage bridged = std::max(early, fill);
            protectedInk.pixel(x, y) = bridged != source;
            const int boost = tone[bridged] - tone[source];
            result.pixel(x, y) = static_cast<Coverage>(std::min(255, result.at(x, y) + boost));
        }
    }
    if (italic) {
        const int arms = std::max(raw.width, raw.height) <= 9 ? radialArms(*unhinted) : 0;
        if (arms < 5 || arms > 7)
            fitSlant(result, raw, protectedInk, hinted, ink);
    }
    return std::move(result.values);
}

} // namespace fontreal_v3
