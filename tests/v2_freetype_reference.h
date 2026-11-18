#pragma once
#include "freetype_reference.h"
#include <QJsonArray>
#include <QVector>
#include <type_traits>
#include FT_OUTLINE_H

// Extend the existing independent provider only for the V2 package probes.
inline bool fontrealV2ReferenceSelected()
{
    const auto profile = qgetenv("FONTREAL_PROFILE");
    return fontrealReference().selected() && (profile == "o" || profile == "k3");
}

inline FT_Error fontrealV2ReferenceInit(FT_Library *output)
{
    auto &reference = fontrealReference();
    const auto error = reference.init(output);
    if (!error && fontrealV2ReferenceSelected()) {
        FT_Bool off = true;
        if (reference.FT_Property_Set_reference(*output, "cff", "no-stem-darkening", &off))
            throw std::runtime_error("Cannot set independent V2 CFF source policy");
    }
    return error;
}

inline FT_Error fontrealV2ReferenceRender(FT_GlyphSlot slot, FT_Render_Mode mode)
{
    auto &reference = fontrealReference();
    if (!fontrealV2ReferenceSelected()) return reference.render(slot, mode);
    FT_Outline outline = slot->outline;
    QVector<FT_Vector> points(outline.n_points);
    QVector<std::remove_pointer_t<decltype(outline.tags)>> tags(outline.n_points);
    QVector<std::remove_pointer_t<decltype(outline.contours)>> contours(outline.n_contours);
    std::copy_n(outline.points, points.size(), points.data());
    std::copy_n(outline.tags, tags.size(), tags.data());
    std::copy_n(outline.contours, contours.size(), contours.data());
    outline.points = points.data(); outline.tags = tags.data(); outline.contours = contours.data();
    const auto error = reference.FT_Render_Glyph_reference(slot, mode);
    if (error || !slot->bitmap.width || !slot->bitmap.rows) return error;
    auto &bitmap = slot->bitmap;
    if (mode != FT_RENDER_MODE_NORMAL || bitmap.pixel_mode != FT_PIXEL_MODE_GRAY)
        throw std::runtime_error("Expected independent V2 NORMAL source");
    const unsigned width = 4 * (bitmap.width + 6), rows = 4 * (bitmap.rows + 6);
    const FT_Pos left = slot->bitmap_left - 3, bottom = slot->bitmap_top - FT_Pos(bitmap.rows) - 3;
    for (auto &point : points) { point.x = point.x * 4 - left * 256; point.y = point.y * 4 - bottom * 256; }
    QByteArray high(int(width * rows), 0);
    FT_Bitmap raster{};
    raster.width = width; raster.rows = rows; raster.pitch = int(width);
    raster.buffer = reinterpret_cast<unsigned char *>(high.data());
    raster.pixel_mode = FT_PIXEL_MODE_GRAY; raster.num_grays = 256;
    const auto rasterize = reinterpret_cast<decltype(&FT_Outline_Get_Bitmap)>(reference.library.resolve("FT_Outline_Get_Bitmap"));
    if (!rasterize || rasterize(slot->library, &outline, &raster))
        throw std::runtime_error("Cannot rasterize independent V2 outline");
    QJsonArray rawPixels, highPixels;
    for (unsigned y = 0; y < bitmap.rows; ++y)
        for (unsigned x = 0; x < bitmap.width; ++x) rawPixels.append(int(bitmap.buffer[y * bitmap.pitch + x]));
    for (unsigned char value : high) highPixels.append(int(value));
    const auto record = QJsonDocument(QJsonObject{
        {"raw", QJsonObject{{"left", slot->bitmap_left}, {"top", -slot->bitmap_top},
            {"width", int(bitmap.width)}, {"height", int(bitmap.rows)}, {"pixels", rawPixels}}},
        {"high", QJsonObject{{"left", int(left * 4)}, {"top", (-slot->bitmap_top - 3) * 4},
            {"width", int(width)}, {"height", int(rows)}, {"pixels", highPixels}}}}).toJson(QJsonDocument::Compact);
    const auto key = qgetenv("FONTREAL_PROFILE") + ':' + record;
    if (!reference.masks.contains(key)) {
        if (reference.processor.state() == QProcess::NotRunning) {
            reference.processor.start(QStringLiteral("python3"), {QStringLiteral("-B"),
                QString::fromLocal8Bit(qgetenv("FONTREAL_TEST_SELECTED_REFERENCE"))});
            if (!reference.processor.waitForStarted()) throw std::runtime_error("Cannot start frozen V2 reference");
        }
        reference.processor.write(record + '\n');
        if (!reference.processor.waitForBytesWritten() || !reference.processor.waitForReadyRead())
            throw std::runtime_error("Independent V2 reference failed");
        while (!reference.processor.canReadLine())
            if (!reference.processor.waitForReadyRead()) throw std::runtime_error("Incomplete independent V2 result");
        const auto processed = QByteArray::fromHex(reference.processor.readLine().trimmed());
        if (processed.size() != int(bitmap.width * bitmap.rows)) throw std::runtime_error("Independent V2 result size changed");
        reference.masks.insert(key, processed);
    }
    const auto &processed = reference.masks[key];
    for (unsigned y = 0; y < bitmap.rows; ++y)
        std::copy_n(reinterpret_cast<const unsigned char *>(processed.constData()) + y * bitmap.width,
                    bitmap.width, bitmap.buffer + y * bitmap.pitch);
    return error;
}
#undef FT_Init_FreeType
#undef FT_Render_Glyph
#define FT_Init_FreeType fontrealV2ReferenceInit
#define FT_Render_Glyph fontrealV2ReferenceRender
