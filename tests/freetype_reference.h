#pragma once
#include <QLibrary>
#include <QProcess>
#include <QHash>
#include <algorithm>
#include <QJsonDocument>
#include <QJsonObject>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MODULE_H
#include FT_MULTIPLE_MASTERS_H
#include <stdexcept>

// Load the independently built reference without replacing Qt's FreeType provider.
struct FontrealReference {
    QLibrary library;
    QProcess processor;
    QHash<QByteArray, QByteArray> masks;
#define FT_REFERENCE_MEMBER(name) decltype(&name) name##_reference = &name;
    FT_REFERENCE_MEMBER(FT_Init_FreeType)
    FT_REFERENCE_MEMBER(FT_Done_FreeType)
    FT_REFERENCE_MEMBER(FT_New_Face)
    FT_REFERENCE_MEMBER(FT_Done_Face)
    FT_REFERENCE_MEMBER(FT_Set_Char_Size)
    FT_REFERENCE_MEMBER(FT_Get_Char_Index)
    FT_REFERENCE_MEMBER(FT_Load_Glyph)
    FT_REFERENCE_MEMBER(FT_Load_Char)
    FT_REFERENCE_MEMBER(FT_Render_Glyph)
    FT_REFERENCE_MEMBER(FT_Select_Charmap)
    FT_REFERENCE_MEMBER(FT_Property_Set)
    FT_REFERENCE_MEMBER(FT_Get_MM_Var)
    FT_REFERENCE_MEMBER(FT_Set_Var_Design_Coordinates)
    FT_REFERENCE_MEMBER(FT_Done_MM_Var)
#undef FT_REFERENCE_MEMBER
    FontrealReference() {
        const auto path = qgetenv("FONTREAL_TEST_REFERENCE_FREETYPE");
        if (path.isEmpty()) return;
        library.setFileName(QString::fromLocal8Bit(path));
        library.setLoadHints(QLibrary::ResolveAllSymbolsHint | QLibrary::DeepBindHint | QLibrary::PreventUnloadHint);
        if (!library.load()) throw std::runtime_error("Cannot load independent FreeType reference");
#define FT_REFERENCE_LOAD(name) \
        name##_reference = reinterpret_cast<decltype(&name)>(library.resolve(#name)); \
        if (!name##_reference) throw std::runtime_error("Missing reference function " #name);
        FT_REFERENCE_LOAD(FT_Init_FreeType)
        FT_REFERENCE_LOAD(FT_Done_FreeType)
        FT_REFERENCE_LOAD(FT_New_Face)
        FT_REFERENCE_LOAD(FT_Done_Face)
        FT_REFERENCE_LOAD(FT_Set_Char_Size)
        FT_REFERENCE_LOAD(FT_Get_Char_Index)
        FT_REFERENCE_LOAD(FT_Load_Glyph)
        FT_REFERENCE_LOAD(FT_Load_Char)
        FT_REFERENCE_LOAD(FT_Render_Glyph)
        FT_REFERENCE_LOAD(FT_Select_Charmap)
        FT_REFERENCE_LOAD(FT_Property_Set)
        FT_REFERENCE_LOAD(FT_Get_MM_Var)
        FT_REFERENCE_LOAD(FT_Set_Var_Design_Coordinates)
        FT_REFERENCE_LOAD(FT_Done_MM_Var)
#undef FT_REFERENCE_LOAD
    }
    bool selected() const { return !qgetenv("FONTREAL_TEST_SELECTED_REFERENCE").isEmpty(); }
    FT_Error init(FT_Library *output) {
        const auto error = FT_Init_FreeType_reference(output);
        if (!error && selected()) {
            FT_Bool noDarkening = false;
            FT_UInt interpreter = 40;
            if (FT_Property_Set_reference(*output, "cff", "no-stem-darkening", &noDarkening)
                || FT_Property_Set_reference(*output, "truetype", "interpreter-version", &interpreter))
                throw std::runtime_error("Cannot mirror Qt reference driver properties");
        }
        return error;
    }
    FT_Int32 flags(FT_Int32 value) const {
        if (!selected()) return value;
        return (value & ~((15L << 16) | FT_LOAD_MONOCHROME | FT_LOAD_FORCE_AUTOHINT))
            | FT_LOAD_NO_AUTOHINT | FT_LOAD_NO_BITMAP;
    }
    FT_Error load(FT_Face face, FT_UInt glyph, FT_Int32 value) {
        return FT_Load_Glyph_reference(face, glyph, flags(value));
    }
    FT_Error character(FT_Face face, FT_ULong codepoint, FT_Int32 value) {
        return FT_Load_Char_reference(face, codepoint, flags(value));
    }
    FT_Error render(FT_GlyphSlot slot, FT_Render_Mode mode) {
        const auto error = FT_Render_Glyph_reference(slot, mode);
        if (error || !selected() || slot->bitmap.pixel_mode != FT_PIXEL_MODE_GRAY) return error;
        auto &bitmap = slot->bitmap;
        QByteArray raw;
        for (unsigned y = 0; y < bitmap.rows; ++y)
            raw.append(reinterpret_cast<const char *>(bitmap.buffer + y * bitmap.pitch), int(bitmap.width));
        if (raw.isEmpty()) return error;
        const auto key = QByteArray::number(bitmap.width) + ':' + raw;
        if (!masks.contains(key)) {
            if (processor.state() == QProcess::NotRunning) {
                processor.start(QStringLiteral("python3"), {QStringLiteral("-B"),
                    QString::fromLocal8Bit(qgetenv("FONTREAL_TEST_SELECTED_REFERENCE"))});
                if (!processor.waitForStarted()) throw std::runtime_error("Cannot start independent selected reference");
            }
            const auto request = QJsonDocument(QJsonObject{{"width", int(bitmap.width)},
                {"mask", QString::fromLatin1(raw.toHex())}}).toJson(QJsonDocument::Compact) + '\n';
            if (processor.write(request) != request.size() || !processor.waitForBytesWritten())
                throw std::runtime_error("Cannot send independent raster");
            while (!processor.canReadLine())
                if (!processor.waitForReadyRead(90000))
                    throw std::runtime_error(("Independent reference failed: " + processor.readAllStandardError()).constData());
            const auto processed = QByteArray::fromHex(processor.readLine().trimmed());
            if (processed.size() != raw.size()) throw std::runtime_error("Independent reference size changed");
            masks.insert(key, processed);
        }
        const auto &processed = masks[key];
        for (unsigned y = 0; y < bitmap.rows; ++y)
            std::copy_n(reinterpret_cast<const unsigned char *>(processed.constData()) + y * bitmap.width,
                        bitmap.width, bitmap.buffer + y * bitmap.pitch);
        return error;
    }
    ~FontrealReference() {
        if (processor.state() != QProcess::NotRunning) {
            processor.closeWriteChannel();
            processor.waitForFinished();
        }
    }
};
inline FontrealReference &fontrealReference() { static FontrealReference reference; return reference; }
#define FT_Init_FreeType fontrealReference().init
#define FT_Done_FreeType fontrealReference().FT_Done_FreeType_reference
#define FT_New_Face fontrealReference().FT_New_Face_reference
#define FT_Done_Face fontrealReference().FT_Done_Face_reference
#define FT_Set_Char_Size fontrealReference().FT_Set_Char_Size_reference
#define FT_Get_Char_Index fontrealReference().FT_Get_Char_Index_reference
#define FT_Load_Glyph fontrealReference().load
#define FT_Load_Char fontrealReference().character
#define FT_Render_Glyph fontrealReference().render
#define FT_Select_Charmap fontrealReference().FT_Select_Charmap_reference
#define FT_Property_Set fontrealReference().FT_Property_Set_reference
#define FT_Get_MM_Var fontrealReference().FT_Get_MM_Var_reference
#define FT_Set_Var_Design_Coordinates fontrealReference().FT_Set_Var_Design_Coordinates_reference
#define FT_Done_MM_Var fontrealReference().FT_Done_MM_Var_reference
