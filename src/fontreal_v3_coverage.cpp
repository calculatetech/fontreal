#include "fontreal_v3_coverage.h"

#include <algorithm>
#include <cmath>

namespace fontreal_v3 {
namespace {

constexpr std::array<double, 3> luminanceWeights{0.2126, 0.7152, 0.0722};
constexpr double stripeStrength = 0.90;

double encodeSrgb(double linear)
{
    return linear <= 0.0031308 ? 12.92 * linear : 1.055 * std::pow(linear, 1.0 / 2.4) - 0.055;
}

Coverage roundCoverage(double value)
{
    const int low = static_cast<int>(value);
    const double remainder = value - low;
    return static_cast<Coverage>(low + (remainder > 0.5 || (remainder == 0.5 && (low % 2))));
}

double darkInkCore(double raw)
{
    const double area = raw / 255;
    const double linearInk = 255 * (1 - encodeSrgb(1 - area));
    return linearInk + (raw - linearInk) * (0.20 + 0.60 * area);
}

double lightInkLift(int raw, double sizeTaper)
{
    constexpr std::array<int, 7> input{0, 43, 85, 128, 170, 213, 255};
    constexpr std::array<int, 7> output{0, 95, 139, 174, 204, 231, 255};
    const auto hi = std::lower_bound(input.begin() + 1, input.end(), raw) - input.begin();
    const double full = output[hi - 1] + double(output[hi] - output[hi - 1])
            * (raw - input[hi - 1]) / (input[hi] - input[hi - 1]);
    const double edgeCut = 0.60 * sizeTaper * std::clamp((160.0 - raw) / 96, 0.0, 1.0);
    return raw + (full - raw) * (1 - edgeCut);
}

double brightness(double pixelSize)
{
    constexpr double small = 32.0 / 3;
    constexpr double lower = 40.0 / 3;
    constexpr double upper = 56.0 / 3;
    constexpr double large = 64.0 / 3;
    const double smallLift = std::clamp((lower - pixelSize) / (lower - small), 0.0, 1.0);
    const double largeLift = std::clamp((pixelSize - upper) / (large - upper), 0.0, 1.0);
    return 0.125 + (0.30 - 0.125) * smallLift + (0.40 - 0.125) * largeLift;
}

const std::array<double, 256> &linearSrgb()
{
    static const auto values = [] {
        std::array<double, 256> table{};
        for (std::size_t i = 0; i < table.size(); ++i) {
            const double encoded = i / 255.0;
            table[i] = encoded <= 0.04045 ? encoded / 12.92 : std::pow((encoded + 0.055) / 1.055, 2.4);
        }
        return table;
    }();
    return values;
}

} // namespace

CoverageTable toneCurve(double pixelSize, Ink ink)
{
    CoverageTable base{};
    const double taper = std::clamp((pixelSize - 40.0 / 3) / 8, 0.0, 1.0);
    for (int raw = 0; raw <= 255; ++raw) {
        base[raw] = roundCoverage(ink == Ink::Dark ? darkInkCore(raw) : lightInkLift(raw, taper));
    }

    const double low = base[64];
    const double span = base[160] - low;
    const double lift = brightness(pixelSize);
    for (Coverage &value : base) {
        const double position = std::clamp((value - low) / span, 0.0, 1.0);
        const double gate = position * position * (3 - 2 * position);
        value = roundCoverage(value + lift * gate * (255 - value));
    }
    return base;
}

double linearInk(Coverage coverage, Ink ink)
{
    const auto &linear = linearSrgb();
    return ink == Ink::Dark ? 1 - linear[255 - coverage] : linear[coverage];
}

Coverage encodedInk(double coverage, Ink ink)
{
    coverage = std::clamp(coverage, 0.0, 1.0);
    const double encoded = ink == Ink::Dark ? 1 - encodeSrgb(1 - coverage) : encodeSrgb(coverage);
    return roundCoverage(255 * encoded);
}

Channels projectChannels(Coverage neutral, Channels samples, Ink ink)
{
    if (neutral == 0 || neutral == 255)
        return {neutral, neutral, neutral};

    const auto &linear = linearSrgb();
    const bool dark = ink == Ink::Dark;
    const double base = linear[dark ? 255 - neutral : neutral];
    std::array<double, 3> shift{};
    double luminance = 0;
    for (std::size_t i = 0; i < shift.size(); ++i) {
        shift[i] = linear[dark ? 255 - samples[i] : samples[i]];
        luminance += luminanceWeights[i] * shift[i];
    }

    // Preserve luminance and limit all channels by the same amount to stay in gamut.
    double limit = 1;
    for (double &channel : shift) {
        channel = stripeStrength * (channel - luminance);
        if (channel > 0)
            limit = std::min(limit, (1 - base) / channel);
        else if (channel < 0)
            limit = std::min(limit, -base / channel);
    }
    for (std::size_t i = 0; i < shift.size(); ++i) {
        const Coverage value = roundCoverage(255 * encodeSrgb(std::clamp(base + limit * shift[i], 0.0, 1.0)));
        samples[i] = dark ? 255 - value : value;
    }
    return samples;
}

} // namespace fontreal_v3
