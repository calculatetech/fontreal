#pragma once

#include <QImage>
#include <array>
#include <cmath>
#include <optional>

namespace {
using Frame = fontreal_v3::GlyphFrame;

#include "white-text/counters.h"
#include "white-text/crossbar.h"
#include "white-text/vertical-ink.h"
#include "white-text/loop-coverage.h"
#include "white-text/outline-rgb.h"
#include "white-text/open-bend.h"
#include "white-text/light-stroke-fit.h"

// Only aligned light ink uses this mask. The providers keep neutral coverage separate.
template <typename Load>
QImage whiteTextStripes(QFontEngineFT *engine, FT_Face face, FT_Outline &contour,
                        const fontreal_v3::OutlineSamples &originalHinted,
                        const std::vector<fontreal_v3::Coverage> &neutralCoverage,
                        qreal pixels, fontreal_v3::StripeLayout layout, const Load &load)
{
    using namespace fontreal_v3;
    const auto frame = originalHinted.frame;
    const auto slot = face->glyph;
    const bool lightFace = fontreal_qt::lightFace(*engine, face);
    const bool naturalFace = !(engine->synthesized() & (QFontEngine::SynthesizedItalic | QFontEngine::SynthesizedBold));
    const bool italicFace = face->style_flags & FT_STYLE_FLAG_ITALIC;
    const bool lightItalic = italicFace && lightFace;
    const auto fullWhite = naturalFace ? sampleOutline(slot->library, contour, frame) : OutlineSamples{};
    OutlineSamples trimmedItalicWhite;
    if(lightItalic) {
        std::vector<FT_Vector> points(contour.points,contour.points+contour.n_points);
        FT_Outline trimmed=contour;
        trimmed.points=points.data();
        constexpr FT_Pos trim=8;
        if(!FT_Outline_EmboldenXY(&trimmed,-trim,-trim)) {
            FT_Outline_Translate(&trimmed,trim/2,trim/2);
            trimmedItalicWhite=sampleOutline(slot->library,trimmed,frame);
        }
    }
    if (!lightItalic && (!lightFace || naturalFace)) {
        constexpr FT_Pos trim = 8;
        if (FT_Outline_EmboldenXY(&contour, -trim, -trim) == 0)
            FT_Outline_Translate(&contour, trim / 2, trim / 2);
    }
    const auto native = sampleOutline(slot->library, contour, frame);
    if (native.pixels.empty())
        return {};

    const bool italic = (engine->synthesized() & QFontEngine::SynthesizedItalic) || italicFace;
    constexpr auto ink = Ink::Light;
    CoverageTable tone{};
    OutlineSamples hinted, unhinted, original;
    std::vector<Coverage> values, originalCoverage;
    QByteArray aligned;
    bool separateBowls = false;
    bool useInkResponse = false;
    if (lightFace || !naturalFace) {
        const FT_Pos opening = lightFace ? 20 : 24;
        hinted = sampleWithClearance(slot->library, contour, frame, opening);
        separateBowls = lightFace && contour.n_contours >= 3 && hasSeveralCounters(hinted);
        if (separateBowls)
            hinted = sampleWithClearance(slot->library, contour, frame, opening / 2);
        if (lightFace && (!separateBowls || naturalFace) && load(FT_LOAD_NO_HINTING))
            unhinted = sampleOutline(slot->library, slot->outline, frame);

        useInkResponse = separateBowls;
        if (!naturalFace || (lightItalic && !separateBowls)) {
            tone = toneCurve(pixels, ink);
            values = glyphCoverage(hinted, &unhinted, tone, pixels, ink, italic);
            if (separateBowls)
                values = balanceBowlInk(hinted, ink, 54);
            else
                deepenCores(values, hinted, ink);
            if (lightFace && !separateBowls) {
                const auto source = values;
                liftBridges(values, source, hinted, ink);
                if (!unhinted.pixels.empty())
                    liftBridges(values, source, unhinted, ink, &hinted);
            }
            original = hinted;
            originalCoverage = values;
            if (!separateBowls) {
                const auto anchors = fitCrossbar(hinted, unhinted, values, tone, ink);
                if (italic && anchors.isEmpty()) {
                    useInkResponse = true;
                    if (!naturalFace) {
                        const auto *post = static_cast<const TT_Postscript *>(FT_Get_Sfnt_Table(face, ft_sfnt_post));
                        const double slant = post && post->italicAngle
                            ? std::tan(post->italicAngle * (3.14159265 / (180.0 * 65536))) : -.18;
                        QByteArray exactStems;
                        QByteArray savedJoins;
                        strengthenItalicStems(values, original, ink, anchors, slant, &hinted, aligned, exactStems,
                                              16, &savedJoins, false);
                    }
                }
            }
        }
    }

    int restoredFirst = 0, restoredEnd = 0;
    auto correctedLight=OutlineSamples{};
    auto correctedWhite=OutlineSamples{};
    const bool repairWhiteItalic = lightItalic && useInkResponse;
    if (naturalFace && lightFace && (!italic || repairWhiteItalic) && !unhinted.pixels.empty()) {
        correctedLight=fullWhite.pixels.empty() ? native : fullWhite;
        const auto source=correctedLight;
        restoreCompressedTurn(correctedLight,unhinted,repairWhiteItalic ? 33 : 54,restoredFirst,restoredEnd);
        restoreThinRuns(correctedLight,unhinted,restoredFirst,restoredEnd,.86,true);
        if (restoredEnd == 0)
            restoreWeakCrossings(correctedLight,unhinted);
        if (pixels < 13.5 && separateBowls)
            fitLowerCounterRoof(correctedLight,true);
        if(!fullWhite.pixels.empty()) {
            correctedWhite=trimmedItalicWhite.pixels.empty() ? native : trimmedItalicWhite;
            for(std::size_t i=0;i<correctedWhite.pixels.size();++i) {
                const int difference=int(correctedLight.pixels[i])-source.pixels[i];
                correctedWhite.pixels[i]=std::clamp(int(correctedWhite.pixels[i])+int(std::lround((repairWhiteItalic ? .92 : .82)*difference)),0,255);
            }
        }
    }

    QImage stripes(frame.width, frame.height, QImage::Format_RGB32);
    const bool directInk = naturalFace && (!lightItalic || useInkResponse);
    const auto &baseOutline = trimmedItalicWhite.pixels.empty() ? native : trimmedItalicWhite;
    const auto &regularOutline = correctedLight.pixels.empty() ? baseOutline
        : correctedWhite.pixels.empty() ? correctedLight : correctedWhite;
    const auto &coreOutline = correctedLight.pixels.empty() ? fullWhite : correctedLight;
    const bool smallItalic = repairWhiteItalic && pixels < 13.5;
    for (int y = 0; y < frame.height; ++y) {
        auto *row = reinterpret_cast<QRgb *>(stripes.scanLine(y));
        for (int x = 0; x < frame.width; ++x) {
            const int i = y * frame.width + x;
            if (!directInk) {
                const bool fitted = !aligned.isEmpty() && aligned[i];
                const bool keep = !fitted && !separateBowls && originalCoverage[i] == values[i];
                auto samples = (keep ? original : hinted).stripes(x, y, layout);
                for (auto &value : samples)
                    value = tone[value];
                const auto rgb = projectChannels(values[i], samples, ink);
                row[x] = qRgb(rgb[0], rgb[1], rgb[2]);
                continue;
            }

            const auto samples = regularOutline.stripes(x, y, layout);
            const auto core = coreOutline.pixels.empty() ? Channels{} : coreOutline.stripes(x, y, layout);
            const auto &tipOutline = coreOutline.pixels.empty() ? regularOutline : coreOutline;
            const double tip = smallItalic ? 0. : terminalSupport(tipOutline, x, y);
            std::array<double, 3> repair{};
            if (!correctedLight.pixels.empty()) {
                const auto originalChannels = fullWhite.stripes(x, y, layout);
                for (std::size_t n = 0; n < repair.size(); ++n) {
                    const int gain = int(core[n]) - originalChannels[n];
                    const double strength = std::clamp((gain - 5.) / 33., 0., 1.);
                    repair[n] = y >= restoredFirst && y < restoredEnd ? std::max(.74, strength) : strength;
                }
                const int center = correctedLight.center(x, y);
                if (smallItalic && restoredEnd == 0 && center >= 44 && center <= 145) {
                    for (const int dy : {-1, 1}) {
                        for (int dx = -1; dx <= 1; ++dx) {
                            const int nx = x + dx, ny = y + dy;
                            if (nx < 0 || nx >= frame.width || ny < 0 || ny >= frame.height
                                    || !continuousInk(correctedLight, x, y, dx, dy))
                                continue;
                            const int gain = correctedLight.center(nx, ny) - fullWhite.center(nx, ny);
                            const double peer = .72 * std::clamp((gain - 10.) / 52., 0., 1.);
                            for (auto &channel : repair)
                                channel = std::max(channel, peer);
                        }
                    }
                }
                if (smallItalic) {
                    const double end = terminalSupport(correctedLight, x, y);
                    for (auto &channel : repair)
                        channel = std::max(channel, end);
                }
            }
            for (auto &channel : repair)
                channel = std::max(channel, tip);
            const auto rgb = whiteInkRgb(samples, coreOutline.pixels.empty() && tip > 0. ? samples : core,
                                         repair, repairWhiteItalic ? .38 : .21,
                                         smallItalic || tip > 0. ? .49 : 0.);
            row[x] = qRgb(rgb[0], rgb[1], rgb[2]);
        }
    }
    if (lightItalic && pixels < 13.5) {
        const auto originalTone = toneCurve(pixels, Ink::Light);
        for (int y = 0; y < frame.height; ++y) {
            auto *row = reinterpret_cast<QRgb *>(stripes.scanLine(y));
            for (int x = 0; x < frame.width; ++x) {
                auto samples = originalHinted.stripes(x, y, layout);
                for (auto &sample : samples)
                    sample = originalTone[sample];
                const auto prior = projectChannels(neutralCoverage[y * frame.width + x], samples, Ink::Light);
                const auto rgb = row[x];
                const double red = .65 * qRed(rgb) + .35 * prior[0];
                const double green = .65 * qGreen(rgb) + .35 * prior[1];
                const double blue = .65 * qBlue(rgb) + .35 * prior[2];
                const double neutral = .2126 * red + .7152 * green + .0722 * blue;
                const double tip = neutral >= 24. && neutral < 180. ? terminalSupport(originalHinted, x, y) : 0.;
                // Add equal coverage to preserve the reduced channel spread.
                const double lift = std::min(255. - std::max({red, green, blue}), 34 * tip);
                row[x] = qRgb(std::lround(.80 * red + .20 * neutral + lift),
                              std::lround(.80 * green + .20 * neutral + lift),
                              std::lround(.80 * blue + .20 * neutral + lift));
            }
        }
    }
    return stripes;
}
} // namespace
