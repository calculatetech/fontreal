#include <QApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFontDatabase>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QQuickItem>
#include <QQuickStyle>
#include <QQuickView>
#include <QRawFont>
#include <QScreen>
#include <QSGRendererInterface>
#include <QTimer>
#include <QWidget>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_FONT_FORMATS_H
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <stdexcept>

namespace {
void require(bool ok, const char *message) { if (!ok) throw std::runtime_error(message); }
QByteArray digest(const QByteArray &bytes) { return QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex(); }
QString imageHash(const QImage &image) {
    const auto rgb = image.convertToFormat(QImage::Format_RGB32);
    return QString::fromLatin1(digest(QByteArray(reinterpret_cast<const char *>(rgb.constBits()),rgb.sizeInBytes())));
}
QString maskHash(const QImage &image) {
    QByteArray bytes=QByteArray::number(image.width())+"x"+QByteArray::number(image.height())+":";
    for(int y=0;y<image.height();++y) for(int x=0;x<image.width();++x) {
        const auto p=image.pixel(x,y);
        bytes.append(char(qRed(p))); bytes.append(char(qGreen(p))); bytes.append(char(qBlue(p))); bytes.append(char(qAlpha(p)));
    }
    return QString::fromLatin1(digest(bytes));
}
void writeJson(const QString &path, const QJsonObject &value) {
    QFile file(path); require(file.open(QIODevice::WriteOnly),"Cannot write result");
    require(file.write(QJsonDocument(value).toJson()) > 0,"Cannot write JSON");
}
QJsonObject identity() {
    QFile maps("/proc/self/maps"); require(maps.open(QIODevice::ReadOnly),"Cannot read maps");
    QString gui;
    for (const auto &line: maps.readAll().split('\n'))
        if (line.contains("/libQt6Gui.so.")) { gui=QString::fromUtf8(line.mid(line.indexOf('/'))); break; }
    return {{"pid",QCoreApplication::applicationPid()},{"qtGui",gui},{"qtVersion",qVersion()}};
}
QFont loadFont(const QString &path) {
    require(QFontDatabase::addApplicationFont(path)>=0,"Cannot register font");
    QRawFont raw(path,15); require(raw.isValid(),"Cannot load font");
    QFont font(raw.familyName()); font.setStyleName(raw.styleName()); font.setPixelSize(15);
    require(QRawFont::fromFont(font).fontTable("head")==raw.fontTable("head"),"Wrong font selected");
    return font;
}
struct Face {
    FT_Library library=nullptr;
    FT_Face face=nullptr;
    Face(const QString &path, double pixels) {
        require(!FT_Init_FreeType(&library),"FT init failed");
        require(!FT_New_Face(library,QFile::encodeName(path).constData(),0,&face),"FT face failed");
        require(!FT_Set_Char_Size(face,0,FT_F26Dot6(std::lround(pixels*64)),72,72),"FT size failed");
    }
    ~Face() { FT_Done_Face(face); FT_Done_FreeType(library); }
    QImage mask(QChar c) {
        require(!FT_Load_Char(face,c.unicode(),FT_LOAD_FORCE_AUTOHINT|FT_LOAD_TARGET_MONO|FT_LOAD_NO_BITMAP),"FT glyph failed");
        require(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL),"FT raster failed");
        const auto &b=face->glyph->bitmap;
        require(b.pixel_mode==FT_PIXEL_MODE_GRAY,"Expected grayscale reference");
        QImage image(int(b.width),int(b.rows),QImage::Format_Grayscale8);
        for(int y=0;y<image.height();++y) for(int x=0;x<image.width();++x) image.scanLine(y)[x]=b.buffer[y*b.pitch+x];
        return image;
    }
};
double decode(double x) { return x<=0.04045 ? x/12.92 : std::pow((x+0.055)/1.055,2.4); }
double encode(double x) { return x<=0.0031308 ? x*12.92 : 1.055*std::pow(x,1/2.4)-0.055; }
int channel(int fg,int bg,int a,bool linear) {
    double f=fg/255.,b=bg/255.,alpha=a/255.;
    return std::clamp(int(std::lround(255*(linear ? encode(alpha*decode(f)+(1-alpha)*decode(b)) : alpha*f+(1-alpha)*b))),0,255);
}
QImage pattern(const QImage &mask,QColor fg,QColor bg,bool mild,bool linear) {
    QImage image(mask.size()+QSize(2,2),QImage::Format_RGB32); image.fill(bg);
    for(int y=0;y<mask.height();++y) for(int x=0;x<mask.width();++x) {
        int a=mask.constScanLine(y)[x];
        if(mild) a=int(std::lround(255*std::clamp((a-32)/191.,0.,1.)));
        image.setPixel(x+1,y+1,qRgb(channel(fg.red(),bg.red(),a,linear),channel(fg.green(),bg.green(),a,linear),channel(fg.blue(),bg.blue(),a,linear)));
    }
    return image;
}
QJsonObject locate(const QImage &source,const QRect &region,const QImage &wanted) {
    int best=256; QPoint position(-1,-1);
    for(int y=region.top();y+wanted.height()<=region.bottom()+1;++y)
        for(int x=region.left();x+wanted.width()<=region.right()+1;++x) {
            int error=0;
            for(int j=0;j<wanted.height() && error<best;++j) for(int i=0;i<wanted.width();++i) {
                const auto a=source.pixel(x+i,y+j),b=wanted.pixel(i,j);
                error=std::max({error,qAbs(qRed(a)-qRed(b)),qAbs(qGreen(a)-qGreen(b)),qAbs(qBlue(a)-qBlue(b))});
                if(error>=best) break;
            }
            if(error<best) { best=error; position=QPoint(x,y); }
        }
    return {{"error",best},{"x",position.x()},{"y",position.y()},{"matches",best<=1}};
}
QJsonObject classify(const QImage &image,const QRect &region,Face &face,QChar c,QColor fg,QColor bg) {
    QJsonObject result;
    const auto mask=face.mask(c);
    for(bool mild:{false,true}) for(bool linear:{false,true})
        result[QString(mild ? "mild/" : "none/")+(linear ? "linear" : "encoded")]=locate(image,region,pattern(mask,fg,bg,mild,linear));
    return result;
}
QQuickItem *textItem(QQuickItem *item) {
    if(item->property("renderType").isValid() && item->property("text").isValid()) return item;
    for(auto *child:item->childItems()) if(auto *found=textItem(child)) return found;
    return nullptr;
}
void collectCells(QQuickItem *item,QList<QQuickItem *> &cells) {
    if(item->objectName().startsWith("cell/")) cells.append(item);
    for(auto *child:item->childItems()) collectCells(child,cells);
}
class Widget:public QWidget {
public:
    QFont face;
    QString text="lmnogWVwv";
    void paintEvent(QPaintEvent *) override {
        QPainter p(this); p.fillRect(rect(),Qt::white); p.setFont(face); p.setPen(Qt::black);
        p.fillRect(QRect(0,70,width(),70),QColor(219,197,181));
        const auto letters=text.toUcs4();
        for(int i=0;i<letters.size();++i) {
            const char32_t character=letters[i];
            p.setPen(Qt::black); p.drawText(QPointF(24+i*64,42),QString::fromUcs4(&character,1));
            p.setPen(QColor(73,121,167)); p.drawText(QPointF(24+i*64,112),QString::fromUcs4(&character,1));
        }
    }
};
}

int main(int argc,char **argv) {
    try {
        QQuickStyle::setStyle("org.kde.breeze");
        QApplication app(argc,argv);
        const QStringList args=app.arguments();
        require(args.size()>=2,"Supply quick, widget, root, match, client, or view");
        const auto mode=args[1];
        if(mode=="root") {
            require(args.size()==3,"root output.png");
            require(app.primaryScreen()->grabWindow(0).save(args[2]),"Root capture failed"); return 0;
        }
        if(mode=="view") {
            require(args.size()==3,"view image.png");
            QImage image(args[2]); require(!image.isNull(),"Cannot read image");
            class Viewer:public QWidget { public: QImage image; void paintEvent(QPaintEvent *) override { QPainter p(this); p.scale(1/devicePixelRatioF(),1/devicePixelRatioF()); p.drawImage(QPoint(0,0),image); } } viewer;
            viewer.image=image; viewer.resize(image.size()/viewer.devicePixelRatioF()); viewer.setWindowTitle("Fontreal 1:1 capture: " + args[2]);
            viewer.show(); return app.exec();
        }
        if(mode=="board") {
            require(args.size()==3,"board results-directory");
            QImage board(1100,890,QImage::Format_RGB32); board.fill(QColor(230,230,230));
            QPainter painter(&board); QFont label("Noto Sans"); label.setPixelSize(15); painter.setFont(label); painter.setPen(Qt::black);
            int y=24;
            const auto caption=[&](const QString &text) { painter.drawText(8,y,text); y+=26; };
            const auto strip=[&](const QString &path,const QRect &region) {
                QImage source(args[2]+"/"+path); require(!source.isNull(),"Missing board capture");
                painter.drawImage(QPoint(0,y),source,region); y+=region.height()+24;
            };
            caption("Noto Sans 15px, 100% scale. Captured pixels, no image scaling.");
            caption("QWidget reference: mild contrast, linear blend");
            strip("spillover-Noto-Sans-linear.png",QRect(0,0,760,64));
            caption("KWin title: stock"); strip("nested-stock-1-default/screen.png",QRect(0,0,1100,32));
            caption("KWin title: mild contrast, linear blend"); strip("nested-linear-1-default/screen.png",QRect(0,0,1100,32));
            caption("Actual Plasma applet, OpenGL: requested linear; measured encoded edges");
            for(int row:{0,4,5}) strip("nested-linear-1-default/plasma.png",QRect(0,16+row*56,760,52));
            caption("Qt Quick software control: mild contrast, linear blend (diagnostic only)");
            for(int row:{0,4,5}) strip("quick-software-linear-1-0-default/frame-0.png",QRect(0,16+row*56,760,52));
            require(y<=board.height(),"Board is too short"); painter.end(); require(board.save(args[2]+"/comparison.png"),"Cannot save board"); return 0;
        }
        if(mode=="match") {
            require(args.size()==13,"match image font scale left top width height letters foreground background output.json");
            QImage image(args[2]); require(!image.isNull(),"Cannot read capture");
            const QRect region(args[5].toInt(),args[6].toInt(),args[7].toInt(),args[8].toInt());
            require(image.rect().contains(region),"Capture region outside image");
            Face face(args[3],15*args[4].toDouble()); QJsonObject result;
            for(const auto c:args[9]) result[QString(c)]=classify(image,region,face,c,QColor(args[10]),QColor(args[11]));
            writeJson(args[12],result); return 0;
        }
        if(mode=="grid") {
            require(args.size()==6 || args.size()==8,"grid image font scale output.json [offset-x offset-y]");
            QImage image(args[2]); require(!image.isNull(),"Cannot read Plasma capture");
            const double scale=args[4].toDouble();
            const QPoint offset=args.size()==8 ? QPoint(args[6].toInt(),args[7].toInt()) : QPoint();
            if(args.size()==6) require(image.width()==qRound(760*scale) && image.height()>=qRound(370*scale),"Unexpected Plasma image scale");
            Face face(args[3],15*scale); QJsonArray cells;
            const QString letters="lmnogWVwv";
            for(int path=0;path<6;++path) for(int i=0;i<letters.size();++i) {
                const QRect region(offset+QPoint(qRound((122+i*68)*scale),qRound((16+path*56)*scale)),QSize(int(64*scale),int(52*scale)));
                require(image.rect().contains(region),"Final grid region outside capture");
                cells.append(QJsonObject{{"path",path},{"glyph",QString(letters[i])},
                    {"hypotheses",classify(image,region,face,letters[i],Qt::black,Qt::white)}});
            }
            writeJson(args[5],QJsonObject{{"scale",scale},{"cells",cells}}); return 0;
        }
        if(mode=="composite") {
            require(args.size()==5,"composite screen image output.json");
            QImage screen(args[2]),item(args[3]); require(!screen.isNull() && !item.isNull(),"Missing composite captures");
            const QRect region=QRect(0,0,item.width()+16,item.height()+80).intersected(screen.rect());
            writeJson(args[4],locate(screen,region,item)); return 0;
        }
        require(args.size()>=4,"Supply font file and output path");
        const auto font=loadFont(args[2]);
        if(mode=="widget" || mode=="client") {
            Widget widget; widget.face=font; widget.resize(760,370);
            if(mode=="widget" && args.size()>4) widget.text=args[4];
            if(mode=="widget" && args.size()>5 && args[5]=="gray") widget.face.setStyleStrategy(QFont::NoSubpixelAntialias);
            widget.setWindowTitle("l m n o g W V w v"); widget.show();
            QTimer::singleShot(500,&app,[&] {
              try {
                const auto image=widget.grab().toImage();
                require(image.save(args[3]+".png"),"Widget capture failed");
                auto result=identity(); result["imageHash"]=imageHash(image); result["font"]=widget.face.toString();
                QRawFont raw=QRawFont::fromFont(widget.face); QJsonArray masks;
                for(const auto glyph:raw.glyphIndexesForString(widget.text)) masks.append(maskHash(raw.alphaMapForGlyph(glyph,QRawFont::PixelAntialiasing)));
                result["masks"]=masks; writeJson(args[3]+".json",result);
                if(mode=="widget") app.quit();
              } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); app.exit(2); }
            });
            return app.exec();
        }
        require(mode=="quick" && args.size()==5,"quick font output-directory phase");
        QQuickView view; view.setResizeMode(QQuickView::SizeRootObjectToView);
        view.setSource(QUrl::fromLocalFile(QStringLiteral(FONTREAL_SOURCE_DIR "/tests/KdeTextGrid.qml")));
        require(view.status()==QQuickView::Ready,"QML fixture failed");
        view.rootObject()->setProperty("testFont",font); view.rootObject()->setProperty("phase",args[4].toDouble());
        view.resize(760,370); view.show();
        QJsonArray frames;
        int frame=0;
        QTimer timer; timer.setInterval(350);
        QObject::connect(&timer,&QTimer::timeout,&app,[&] {
          try {
            const auto image=view.grabWindow().convertToFormat(QImage::Format_RGB32);
            require(!image.isNull(),"Quick capture failed");
            const auto fg=view.rootObject()->property("ink").value<QColor>(),bg=view.rootObject()->property("paper").value<QColor>();
            Face face(args[2],15*view.devicePixelRatio()); QJsonArray cells;
            QList<QQuickItem *> allCells; collectCells(view.rootObject(),allCells);
            for(auto *cell:allCells) {
                const auto origin=cell->mapToScene(QPointF())*view.devicePixelRatio();
                QRect region(qRound(origin.x()),qRound(origin.y()),int(cell->width()*view.devicePixelRatio()),int(cell->height()*view.devicePixelRatio()));
                auto *text=textItem(cell); require(text,"Cannot identify actual text item");
                const auto actualFont=text->property("font").value<QFont>();
                require(QRawFont::fromFont(actualFont).fontTable("head")==QRawFont::fromFont(font).fontTable("head"),"Quick selected another font");
                const auto glyphOrigin=text->mapToScene(QPointF())*view.devicePixelRatio();
                cells.append(QJsonObject{{"cell",cell->objectName()},{"path",cell->property("path").toInt()},
                    {"glyph",cell->property("character").toString()},{"renderType",text->property("renderType").toInt()},
                    {"font",actualFont.toString()},{"originX",glyphOrigin.x()},{"originY",glyphOrigin.y()},
                    {"hypotheses",classify(image,region,face,cell->property("character").toString()[0],fg,bg)}});
            }
            require(cells.size()==54,"Fixture did not produce every cell");
            require(image.save(args[3]+QString("/frame-%1.png").arg(frame)),"Cannot save Quick frame");
            frames.append(QJsonObject{{"frame",frame},{"hash",imageHash(image)},{"cells",cells}});
            if(++frame==4) { auto result=identity(); result["frames"]=frames; result["scale"]=view.devicePixelRatio();
                result["graphicsApi"]=int(view.rendererInterface()->graphicsApi()); result["phase"]=args[4].toDouble();
                writeJson(args[3]+"/result.json",result); app.quit();
            } else if(frame==2) { view.rootObject()->setProperty("ink",QColor(Qt::white)); view.rootObject()->setProperty("paper",QColor(Qt::black)); }
            else if(frame==3) { view.rootObject()->setProperty("ink",QColor(73,121,167)); view.rootObject()->setProperty("paper",QColor(219,197,181)); }
            view.update();
          } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); app.exit(2); }
        });
        timer.start(); return app.exec();
    } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); return 2; }
}
