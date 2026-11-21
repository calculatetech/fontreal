#pragma once

#include <QtCore/QScopeGuard>
#include <QtCore/QVarLengthArray>
#include <fontconfig/fontconfig.h>
#include <memory>
#include <QtGui/private/qfontengine_ft_p.h>
#include FT_MULTIPLE_MASTERS_H
#include FT_TRUETYPE_TABLES_H

#include "fontreal_v3_outline.h"

namespace fontreal_qt {

class FreeTypeFields : public QFontEngineFT {
public:
    static constexpr auto layout() { return &FreeTypeFields::subpixelType; }
    static constexpr auto faceData() { return &FreeTypeFields::freetype; }
};

inline fontreal_v3::StripeLayout effectiveLayout(const QFontEngineFT &engine)
{
    using fontreal_v3::StripeLayout;
    switch (engine.*FreeTypeFields::layout()) {
    case QFontEngine::Subpixel_RGB: return StripeLayout::Rgb;
    case QFontEngine::Subpixel_BGR: return StripeLayout::Bgr;
    case QFontEngine::Subpixel_VRGB: return StripeLayout::VerticalRgb;
    case QFontEngine::Subpixel_VBGR: return StripeLayout::VerticalBgr;
    case QFontEngine::Subpixel_None: return StripeLayout::None;
    }
    return StripeLayout::None;
}

inline bool fontconfigAllowsAntialiasing(const QFontEngine &engine)
{
    using Pattern = std::unique_ptr<FcPattern, decltype(&FcPatternDestroy)>;
    Pattern query(FcPatternCreate(), FcPatternDestroy);
    if (!query)
        return true;

    const auto face = engine.faceId();
    const auto family = engine.fontDef.families.value(0).toUtf8();
    if (!family.isEmpty())
        FcPatternAddString(query.get(), FC_FAMILY, reinterpret_cast<const FcChar8 *>(family.constData()));
    if (!face.filename.isEmpty()) {
        FcPatternAddString(query.get(), FC_FILE, reinterpret_cast<const FcChar8 *>(face.filename.constData()));
        FcPatternAddInteger(query.get(), FC_INDEX, face.index);
    }
    const qreal pixels = engine.fontDef.pixelSize;
    const qreal points = engine.fontDef.pointSize;
    if (pixels > 0)
        FcPatternAddDouble(query.get(), FC_PIXEL_SIZE, pixels);
    if (points > 0)
        FcPatternAddDouble(query.get(), FC_SIZE, points);

    FcConfigSubstitute(nullptr, query.get(), FcMatchPattern);
    FcDefaultSubstitute(query.get());
    // Keep Qt's actual sizes when Fontconfig derives a new value from DPI.
    if (pixels > 0) {
        FcPatternDel(query.get(), FC_PIXEL_SIZE);
        FcPatternAddDouble(query.get(), FC_PIXEL_SIZE, pixels);
    }
    if (points > 0) {
        FcPatternDel(query.get(), FC_SIZE);
        FcPatternAddDouble(query.get(), FC_SIZE, points);
    }
    FcResult result;
    Pattern match(FcFontMatch(nullptr, query.get(), &result), FcPatternDestroy);
    const auto allowed = [](FcPattern *pattern) {
        FcBool antialias = FcTrue;
        return !pattern || FcPatternGetBool(pattern, FC_ANTIALIAS, 0, &antialias) != FcResultMatch || antialias;
    };
    return allowed(query.get()) && allowed(match.get());
}

inline bool lightFace(const QFontEngineFT &engine, FT_Face face)
{
    if (engine.synthesized() & QFontEngine::SynthesizedBold)
        return false;
    const auto *axes = (engine.*FreeTypeFields::faceData())->mm_var;
    FT_MM_Var *ownedAxes = nullptr;
    // Qt can apply variation coordinates without retaining the axis metadata.
    if (!axes && FT_IS_VARIATION(face) && !FT_Get_MM_Var(face, &ownedAxes))
        axes = ownedAxes;
    const auto releaseAxes = qScopeGuard([&] {
        if (ownedAxes)
            FT_Done_MM_Var(face->glyph->library, ownedAxes);
    });
    if (axes) {
        for (FT_UInt i = 0; i < axes->num_axis; ++i) {
            if (axes->axis[i].tag != FT_MAKE_TAG('w', 'g', 'h', 't'))
                continue;
            QVarLengthArray<FT_Fixed, 8> coordinates(axes->num_axis);
            if (!FT_Get_Var_Design_Coordinates(face, axes->num_axis, coordinates.data()))
                return coordinates.at(i) <= 350L * 65536;
            break;
        }
    }
    const auto *os2 = static_cast<const TT_OS2 *>(FT_Get_Sfnt_Table(face, ft_sfnt_os2));
    return engine.fontDef.weight <= QFont::Light || (os2 && os2->usWeightClass <= 350);
}

}
