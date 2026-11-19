#pragma once

#include <array>
#include <cstdint>

namespace fontreal_v3 {

using Coverage = std::uint8_t;
using CoverageTable = std::array<Coverage, 256>;
using Channels = std::array<Coverage, 3>;

enum class Ink { Dark, Light };

CoverageTable toneCurve(double pixelSize, Ink ink);
double linearInk(Coverage coverage, Ink ink);
Coverage encodedInk(double coverage, Ink ink);

// Pass samples in physical red, green, blue order. All values represent ink coverage.
Channels projectChannels(Coverage neutral, Channels samples, Ink ink);

} // namespace fontreal_v3
