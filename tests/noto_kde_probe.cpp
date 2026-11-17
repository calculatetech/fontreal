#include <QApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFontDatabase>
#include <QGlyphRun>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QRawFont>
#include <QTextLayout>
#include <QTextOption>
#include <QWidget>
#include <algorithm>
#include <cmath>
#include <map>
#include <memory>
#include <vector>
#include <stdexcept>
#include "freetype_reference.h"

static void require(bool ok,const char *message) {if(!ok) throw std::runtime_error(message);}
static QJsonArray pixels(const QImage &image) {
    QJsonArray result;
    for(int y=0;y<image.height();++y) for(int x=0;x<image.width();++x)result.append(qAlpha(image.pixel(x,y)));
    return result;
}
struct Section {QString name;QStringList text;QJsonArray lines;QImage image;std::vector<std::unique_ptr<QTextLayout>> layouts;};
class TextWidget:public QWidget {
public:
    Section &section;QFont textFont;bool dark;int step;
    TextWidget(Section &s,const QFont &font,bool d,int lineStep):section(s),textFont(font),dark(d),step(lineStep) {resize(500,16+step*s.text.size());}
    void paintEvent(QPaintEvent *) override {
        QPainter painter(this);painter.fillRect(rect(),dark?Qt::black:Qt::white);painter.setPen(dark?Qt::white:Qt::black);painter.setFont(textFont);section.layouts.clear();
        for(int li=0;li<section.text.size();++li) {
            auto layout=std::make_unique<QTextLayout>(section.text[li],textFont,this);QTextOption option;option.setWrapMode(QTextOption::NoWrap);layout->setTextOption(option);layout->beginLayout();auto line=layout->createLine();line.setLineWidth(10000);layout->endLayout();
            const QPointF origin(12,8+li*step);painter.drawText(QPointF(origin.x(),origin.y()+line.ascent()),section.text[li]);section.layouts.push_back(std::move(layout));
        }
    }
};
int main(int argc,char **argv) {
    try {
        QApplication app(argc,argv);require(argc==5,"usage: noto-kde-probe POINTS POLARITY FONT PREFIX");
        const int points=QString(argv[1]).toInt();require(points==8||points==10||points==11||points==12,"unsupported points");
        const bool dark=QString(argv[2])=="dark";const QString fontFile=QString::fromLocal8Bit(argv[3]);const QString prefix=QString::fromLocal8Bit(argv[4]);
        QFont font("Noto Sans",points);font.setStyleName("Regular");
        QStringList body;body<<"The quick brown fox jumps over the lazy dog.";
        for(int first=32;first<=96;first+=32){QString line;for(int c=first;c<=std::min(first+31,126);++c)line+=QChar(c);body<<line;}
        body<<"Repeated spaces: A  B   C"<<"AV To office fi fl";
        std::vector<Section> sections;sections.push_back({"body",body,{},{}});sections.push_back({"focus",{"() O O i8! W"},{},{}});
        std::vector<std::unique_ptr<TextWidget>> widgets;
        const int step=int(std::ceil(points*96./72.))+12;std::map<quint32,QRawFont> rawFonts;std::map<quint32,bool> used;
        // Native RGB32 captures precede alpha queries and loading the independent FT reference.
        for(auto &section:sections) {
            section.image=QImage(500,16+step*section.text.size(),QImage::Format_RGB32);section.image.setDotsPerMeterX(3780);section.image.setDotsPerMeterY(3780);section.image.fill(dark?Qt::black:Qt::white);
            auto widget=std::make_unique<TextWidget>(section,font,dark,step);widget->ensurePolished();widget->render(&section.image);widgets.push_back(std::move(widget));require(section.image.save(prefix+"-"+section.name+".png"),"native image save failed");
        }
        QRawFont actual=QRawFont::fromFont(font),fileFont(fontFile,actual.pixelSize());
        require(actual.isValid()&&fileFont.isValid(),"invalid raw font");QJsonObject tables;
        for(const char *table:{"head","cmap","name"}) {require(actual.fontTable(table)==fileFont.fontTable(table),"native font table mismatch");tables.insert(table,QString::fromLatin1(QCryptographicHash::hash(actual.fontTable(table),QCryptographicHash::Sha256).toHex()));}
        for(auto &section:sections) {
            for(int li=0;li<section.text.size();++li) {
                const auto &layout=*section.layouts[li];const auto line=layout.lineAt(0);const QPointF origin(12,8+li*step);QJsonArray runs;
                for(const QGlyphRun &run:layout.glyphRuns()) {
                    const QRawFont rf=run.rawFont();require(rf.fontTable("head")==actual.fontTable("head")&&rf.pixelSize()==actual.pixelSize(),"fallback or raster-size mismatch");
                    auto ids=run.glyphIndexes();auto positions=run.positions();require(ids.size()==positions.size(),"missing native positions");QJsonArray placed;
                    for(int i=0;i<ids.size();++i) {require(ids[i]!=0,"missing shaped glyph");rawFonts.emplace(ids[i],rf);used[ids[i]]=true;placed.append(QJsonObject{{"id",int(ids[i])},{"x",origin.x()+positions[i].x()},{"y",origin.y()+positions[i].y()},{"local_x",positions[i].x()},{"local_y",positions[i].y()}});}
                    runs.append(QJsonObject{{"pixel_size",rf.pixelSize()},{"glyphs",placed}});
                }
                section.lines.append(QJsonObject{{"text",section.text[li]},{"origin",QJsonArray{origin.x(),origin.y()}},{"ascent",line.ascent()},{"descent",line.descent()},{"runs",runs}});
            }
        }
        FT_Library library=nullptr;require(!FT_Init_FreeType(&library),"reference init failed");
        using Getter=decltype(&FT_Property_Get);auto getter=reinterpret_cast<Getter>(fontrealReference().library.resolve("FT_Property_Get"));require(getter,"missing reference property getter");
        FT_UInt interpreter=40,effective=0;require(!FT_Property_Set(library,"truetype","interpreter-version",&interpreter)&&!getter(library,"truetype","interpreter-version",&effective),"interpreter property failed");QJsonObject properties;
        for(const char *module:{"cff","autofitter"}) {FT_Bool disabled=true,actualValue=false;require(!FT_Property_Set(library,module,"no-stem-darkening",&disabled)&&!getter(library,module,"no-stem-darkening",&actualValue),"darkening property failed");properties.insert(module,QJsonObject{{"no_stem_darkening",bool(actualValue)}});}
        FT_Face face=nullptr;require(!FT_New_Face(library,QFile::encodeName(fontFile).constData(),0,&face),"reference face failed");require(!FT_Set_Char_Size(face,0,FT_F26Dot6(std::lround(actual.pixelSize()*64)),72,72),"reference size failed");QJsonArray glyphs;
        for(const auto &[id,rf]:rawFonts) {
            const FT_Int32 flags=FT_LOAD_NO_AUTOHINT|FT_LOAD_NO_BITMAP|FT_LOAD_TARGET_NORMAL;require(!FT_Load_Glyph(face,id,flags),"reference glyph load failed");QJsonArray outline,contours;
            for(int i=0;i<face->glyph->outline.n_points;++i)outline.append(QJsonArray{double(face->glyph->outline.points[i].x),double(face->glyph->outline.points[i].y),int(static_cast<unsigned char>(face->glyph->outline.tags[i]))});
            for(int i=0;i<face->glyph->outline.n_contours;++i)contours.append(face->glyph->outline.contours[i]);
            const double advance=face->glyph->advance.x/64.;require(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL),"reference glyph raster failed");auto &bitmap=face->glyph->bitmap;require(bitmap.pixel_mode==FT_PIXEL_MODE_GRAY,"reference bitmap is not gray");QJsonArray coverage;
            for(unsigned y=0;y<bitmap.rows;++y)for(unsigned x=0;x<bitmap.width;++x)coverage.append(bitmap.buffer[ptrdiff_t(y)*bitmap.pitch+x]);
            QImage alpha=rf.alphaMapForGlyph(id,QRawFont::PixelAntialiasing);auto bounds=rf.boundingRect(id);
            glyphs.append(QJsonObject{{"id",int(id)},{"raw",QJsonObject{{"left",face->glyph->bitmap_left},{"top",-face->glyph->bitmap_top},{"width",int(bitmap.width)},{"height",int(bitmap.rows)},{"pixels",coverage}}},
                {"outline",outline},{"contours",contours},{"advance",advance},{"qt_alpha",QJsonObject{{"width",alpha.width()},{"height",alpha.height()},{"format",int(alpha.format())},{"pixels",pixels(alpha)}}},
                {"qt_bounds",QJsonArray{bounds.x(),bounds.y(),bounds.width(),bounds.height()}}});
        }
        QJsonArray images;for(const auto &section:sections)images.append(QJsonObject{{"kind",section.name},{"width",section.image.width()},{"height",section.image.height()},{"dpi",section.image.logicalDpiY()},{"device_pixel_ratio",section.image.devicePixelRatio()},{"lines",section.lines}});
        const auto space=actual.glyphIndexesForString(QStringLiteral(" "));require(space.size()==1&&space[0],"missing native space glyph");
        QJsonObject result{{"family",actual.familyName()},{"style",actual.styleName()},{"point_size",points},{"pixel_size",actual.pixelSize()},{"font_tables",tables},{"space_glyph_id",int(space[0])},
            {"image_format","RGB32"},{"sections",images},{"glyphs",glyphs},{"source",QJsonObject{{"family",QString::fromUtf8(face->family_name)},{"style",QString::fromUtf8(face->style_name)},{"x_ppem",int(face->size->metrics.x_ppem)},{"space_glyph_id",int(FT_Get_Char_Index(face,32))},{"dpi",72},{"char_size_26_6",int(std::lround(actual.pixelSize()*64))},{"load_flags",32776},{"target",0},{"render",0},{"interpreter",int(effective)},{"darkening_properties",properties},{"selected_reference",fontrealReference().selected()},{"reference_library",fontrealReference().library.fileName()}}}};
        QFile metadata(prefix+".json");require(metadata.open(QIODevice::WriteOnly),"metadata open failed");metadata.write(QJsonDocument(result).toJson(QJsonDocument::Compact));metadata.write("\n");
        QFile maps("/proc/self/maps"),proof(prefix+".maps");require(maps.open(QIODevice::ReadOnly)&&proof.open(QIODevice::WriteOnly),"maps open failed");proof.write(maps.readAll());
        require(!FT_Done_Face(face)&&!FT_Done_FreeType(library),"reference close failed");for(auto &section:sections)section.layouts.clear();return 0;
    }catch(const std::exception &error){qCritical("%s",error.what());return 1;}
}
