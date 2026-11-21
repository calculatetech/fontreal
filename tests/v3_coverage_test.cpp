#include "fontreal_v3_coverage.h"

#include <algorithm>
#include <cstdio>
#include <cstring>

using namespace fontreal_v3;

namespace {

// Independent reference bytes and regeneration instructions are in v3_coverage_reference.py.
// Each set has the transfer table, physical RGB, physical BGR and independent-neutral hashes.
struct Reference {
    int points;
    std::array<std::uint64_t, 4> dark;
    std::array<std::uint64_t, 4> light;
};

constexpr Reference references[] = {
    { 8, {0x70848ab5ce2c5744, 0x14ed5d26ed50fbfa, 0x2290c15b6f469cd0, 0x4624b61f99a0d3d4},
         {0x8b48f0dbb3b2a957, 0x563a9e7b51f5056b, 0x2e60997962523075, 0x59913e74146bf5d7}},
    {10, {0x0b09c6db5d446aae, 0x2fdd3e1f88eabb37, 0x8761694ebfa37501, 0x815f45e32748c39d},
         {0xdb3f2784cf039f76, 0xcead462fed4184a5, 0x1da9a08e17a859cf, 0xfee04f13878b8318}},
    {11, {0x0b09c6db5d446aae, 0x2fdd3e1f88eabb37, 0x8761694ebfa37501, 0x815f45e32748c39d},
         {0xcba1d6cdf27f849b, 0xbf256e464d2a4acf, 0xd124871b9deb7101, 0x7025f82825287a80}},
    {12, {0x0b09c6db5d446aae, 0x2fdd3e1f88eabb37, 0x8761694ebfa37501, 0x815f45e32748c39d},
         {0x746d8e140bf15b0a, 0x6c96267ca4694050, 0xb847bf80aa043c02, 0x3825aab97ef30a76}},
    {14, {0x0b09c6db5d446aae, 0x2fdd3e1f88eabb37, 0x8761694ebfa37501, 0x815f45e32748c39d},
         {0x8eeb92cff89bc489, 0x06464b926db247c2, 0x5843aaa0148fb0c4, 0xbdf812ed5eec29e0}},
    {16, {0xec2e76c2955fa3b6, 0x388b8e2402a7f778, 0xe820d9012f4a5380, 0x16efe9940950b3ee},
         {0x331390e22c86816c, 0xa1ce61d76aaba41b, 0x4035704d5f8366ad, 0x8f994691d359adf8}},
};

constexpr std::uint64_t hashStart = 14695981039346656037ULL;

std::uint64_t append(std::uint64_t hash, Coverage value)
{
    return (hash ^ value) * 1099511628211ULL;
}

std::array<std::uint64_t, 4> evaluate(const CoverageTable &table, Ink ink, bool dump)
{
    std::array<std::uint64_t, 4> hashes{hashStart, hashStart, hashStart, hashStart};
    for (Coverage value : table)
        hashes[0] = append(hashes[0], value);
    if (dump)
        std::fwrite(table.data(), 1, table.size(), stdout);
    constexpr Coverage samples[]{0, 1, 17, 52, 86, 125, 171, 199, 216, 251, 254, 255};
    for (std::size_t mode = 1; mode < hashes.size(); ++mode) {
        for (Coverage first : samples) {
            for (Coverage center : samples) {
                for (Coverage last : samples) {
                    Channels channels{table[first], table[center], table[last]};
                    if (mode == 2)
                        std::swap(channels.front(), channels.back());
                    const Coverage neutral = table[mode == 3 ? 255 - center : center];
                    const Channels result = projectChannels(neutral, channels, ink);
                    for (Coverage value : result)
                        hashes[mode] = append(hashes[mode], value);
                    if (dump)
                        std::fwrite(result.data(), 1, result.size(), stdout);
                }
            }
        }
    }
    return hashes;
}

} // namespace

int main(int argc, char **argv)
{
    const bool dump = argc == 2 && std::strcmp(argv[1], "--dump") == 0;
    if (!dump && argc != 1)
        return 2;
    bool passed = true;
    for (const Reference &reference : references) {
        for (Ink ink : {Ink::Dark, Ink::Light}) {
            const auto table = toneCurve(reference.points * 96.0 / 72, ink);
            const auto expected = ink == Ink::Dark ? reference.dark : reference.light;
            const auto actual = evaluate(table, ink, dump);
            if (table.front() != 0 || table.back() != 255 || !std::is_sorted(table.begin(), table.end())
                || actual != expected) {
                std::fprintf(stderr, "%d pt %s ink changed (transfer %016llx, RGB %016llx, BGR %016llx, neutral %016llx)\n",
                             reference.points, ink == Ink::Dark ? "dark" : "light",
                             static_cast<unsigned long long>(actual[0]),
                             static_cast<unsigned long long>(actual[1]),
                             static_cast<unsigned long long>(actual[2]),
                             static_cast<unsigned long long>(actual[3]));
                passed = false;
            }
        }
    }
    return passed && (!dump || (std::fflush(stdout) == 0 && !std::ferror(stdout))) ? 0 : 1;
}
