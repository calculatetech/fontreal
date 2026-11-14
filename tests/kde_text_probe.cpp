#include <QApplication>
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QElapsedTimer>
#include <QEvent>
#include <QFile>
#include <QFontDatabase>
#include <QFontMetricsF>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QPainter>
#include <QQuickItem>
#include <QQuickStyle>
#include <QQuickView>
#include <QQuickRenderControl>
#include <QQuickRenderTarget>
#include <QQmlComponent>
#include <QQmlEngine>
#include <rhi/qrhi.h>
#include <QRawFont>
#include <QScreen>
#include <QSet>
#include <QSGRendererInterface>
#include <QTimer>
#include <QStaticText>
#include <QWidget>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_FONT_FORMATS_H
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <memory>
#include "freetype_reference.h"

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
class SurfaceObserver:public QObject {
    QWindow *window;
    QString path;
public:
    SurfaceObserver(QWindow *target, const QString &output):QObject(target),window(target),path(output) {
        window->installEventFilter(this); publish();
    }
    void publish() {
        writeJson(path,{{"pid",QCoreApplication::applicationPid()},{"scale",window->devicePixelRatio()}});
    }
    bool eventFilter(QObject *object,QEvent *event) override {
        if(event->type()==QEvent::DevicePixelRatioChange) publish();
        return QObject::eventFilter(object,event);
    }
};
QJsonObject identity() {
    QFile maps("/proc/self/maps"); require(maps.open(QIODevice::ReadOnly),"Cannot read maps");
    QString gui,quick; QStringList freetype;
    for (const auto &line: maps.readAll().split('\n')) {
        if (line.contains("/libQt6Gui.so.")) gui=QString::fromUtf8(line.mid(line.indexOf('/')));
        if (line.contains("/libQt6Quick.so.")) quick=QString::fromUtf8(line.mid(line.indexOf('/')));
        if (line.contains("/libfreetype.so.")) freetype.append(QString::fromUtf8(line.mid(line.indexOf('/'))));
    }
    freetype.removeDuplicates();
    return {{"pid",QCoreApplication::applicationPid()},{"qtGui",gui},{"qtQuick",quick},{"qtVersion",qVersion()},
            {"freetypeLibraries",QJsonArray::fromStringList(freetype)}};
}
QFont loadFont(const QString &path) {
    require(QFontDatabase::addApplicationFont(path)>=0,"Cannot register font");
    QRawFont raw(path,15); require(raw.isValid(),"Cannot load font");
    QFont font(raw.familyName()); font.setStyleName(raw.styleName()); font.setPixelSize(15);
    font.setWeight(QFont::Weight(raw.weight())); font.setStyle(raw.style());
    if(!qgetenv("FONTREAL_TEST_WEIGHT").isEmpty())
        font.setVariableAxis("wght",qgetenv("FONTREAL_TEST_WEIGHT").toFloat());
    require(QRawFont::fromFont(font).fontTable("head")==raw.fontTable("head"),"Wrong font selected");
    return font;
}
struct Face {
    FT_Library library=nullptr;
    FT_Face face=nullptr;
    Face(const QString &path, double pixels) {
        require(!FT_Init_FreeType(&library),"FT init failed");
        require(!FT_New_Face(library,QFile::encodeName(path).constData(),0,&face),"FT face failed");
        if(FT_HAS_MULTIPLE_MASTERS(face) && !qgetenv("FONTREAL_TEST_WEIGHT").isEmpty()) {
            FT_MM_Var *axes=nullptr;
            require(!FT_Get_MM_Var(face,&axes),"Variable axes missing");
            QVector<FT_Fixed> coordinates(axes->num_axis);
            for(FT_UInt i=0;i<axes->num_axis;++i)
                coordinates[i]=axes->axis[i].tag==FT_MAKE_TAG('w','g','h','t')
                    ? std::lround(qgetenv("FONTREAL_TEST_WEIGHT").toDouble()*65536) : axes->axis[i].def;
            require(!FT_Set_Var_Design_Coordinates(face,axes->num_axis,coordinates.data()),"Variable weight failed");
            FT_Done_MM_Var(library,axes);
        }
        require(!FT_Set_Char_Size(face,0,FT_F26Dot6(std::lround(pixels*64)),72,72),"FT size failed");
    }
    ~Face() { FT_Done_Face(face); FT_Done_FreeType(library); }
    QImage mask(QChar c) {
        require(FT_Get_Char_Index(face,c.unicode())!=0,"Missing primary reference glyph");
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
int channel(int fg,int bg,double a,bool linear) {
    double f=fg/255.,b=bg/255.,alpha=a/255.;
    return std::clamp(int(std::lround(255*(linear ? encode(alpha*decode(f)+(1-alpha)*decode(b)) : alpha*f+(1-alpha)*b))),0,255);
}
QImage pattern(const QImage &mask,QColor fg,QColor bg,bool mild,bool linear,double opacity=1) {
    QImage image(mask.size()+QSize(2,2),QImage::Format_RGB32); image.fill(bg);
    for(int y=0;y<mask.height();++y) for(int x=0;x<mask.width();++x) {
        int a=mask.constScanLine(y)[x];
        if(mild) a=int(std::lround(255*std::clamp((a-32)/191.,0.,1.)));
        const double effective=a*fg.alphaF()*opacity;
        image.setPixel(x+1,y+1,qRgb(channel(fg.red(),bg.red(),effective,linear),channel(fg.green(),bg.green(),effective,linear),channel(fg.blue(),bg.blue(),effective,linear)));
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
QJsonObject classify(const QImage &image,const QRect &region,Face &face,QChar c,QColor fg,QColor bg,double opacity=1) {
    QJsonObject result;
    const auto mask=face.mask(c);
    for(bool mild:{false,true}) for(bool linear:{false,true})
        result[QString(mild ? "mild/" : "none/")+(linear ? "linear" : "encoded")]=locate(image,region,pattern(mask,fg,bg,mild,linear,opacity));
    return result;
}
QJsonObject classifySunken(const QImage &image,Face &face,QChar c) {
    const auto mask=face.mask(c);
    const QColor foreground(73,121,167,128),style(161,75,63,181),background(219,197,181);
    const auto coverage=[&](int x,int y,bool mild) {
        if(x<0 || y<0 || x>=mask.width() || y>=mask.height()) return 0.;
        return mild ? std::lround(255*std::clamp((mask.constScanLine(y)[x]-32)/191.,0.,1.))/255.
                    : mask.constScanLine(y)[x]/255.;
    };
    QJsonObject result;
    for(bool mild:{false,true}) for(bool linear:{false,true}) {
        QImage wanted(mask.size()+QSize(4,4),QImage::Format_RGB32); wanted.fill(background);
        for(int y=0;y<wanted.height();++y) for(int x=0;x<wanted.width();++x) {
            const double glyph=coverage(x-2,y-2,mild);
            const double shifted=std::max(0.,coverage(x-2,y-1,mild)-glyph);
            const double a=glyph*foreground.alphaF()*.75,b=shifted*style.alphaF()*.75;
            int channels[3];
            for(int channelIndex=0;channelIndex<3;++channelIndex) {
                const double f=(channelIndex==0 ? foreground.redF() : channelIndex==1 ? foreground.greenF() : foreground.blueF());
                const double s=(channelIndex==0 ? style.redF() : channelIndex==1 ? style.greenF() : style.blueF());
                const double bg=(channelIndex==0 ? background.redF() : channelIndex==1 ? background.greenF() : background.blueF());
                const double mixed=linear ? encode(a*decode(f)+b*decode(s)+(1-a-b)*decode(bg)) : a*f+b*s+(1-a-b)*bg;
                channels[channelIndex]=std::clamp(int(std::lround(255*mixed)),0,255);
            }
            wanted.setPixel(x,y,qRgb(channels[0],channels[1],channels[2]));
        }
        result[QString(mild ? "mild/" : "none/")+(linear ? "linear" : "encoded")]=locate(image,image.rect(),wanted);
    }
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
void collectRegions(QQuickItem *item,QList<QQuickItem *> &regions) {
    if(item->objectName().startsWith("region/")) regions.append(item);
    for(auto *child:item->childItems()) collectRegions(child,regions);
}
QImage readTarget(QQuickRenderControl &control,QRhiTexture *texture) {
    QRhiReadbackResult readback; QImage image;
    readback.completed=[&] {
        const QImage raw(reinterpret_cast<const uchar *>(readback.data.constData()),
                         readback.pixelSize.width(),readback.pixelSize.height(),QImage::Format_RGBA8888_Premultiplied);
        image=control.rhi()->isYUpInFramebuffer() ? raw.mirrored(false,true) : raw.copy();
    };
    auto *batch=control.rhi()->nextResourceUpdateBatch();
    batch->readBackTexture(texture,&readback);
    control.commandBuffer()->resourceUpdate(batch);
    control.endFrame();
    require(!image.isNull(),"Target readback did not finish");
    return image.convertToFormat(QImage::Format_RGB32);
}
void nonindexedCheck(QQuickRenderControl &control,QRhiTextureRenderTarget *target,QRhiTexture *texture,bool compatible) {
    auto *rhi=control.rhi();
    const auto shader=[](const char *name) {
        QFile file(QStringLiteral(":/qt-project.org/scenegraph/shaders_ng/flatcolor.")+QLatin1String(name)+QStringLiteral(".qsb"));
        require(file.open(QIODevice::ReadOnly),"Cannot load existing Qt color shader");
        auto result=QShader::fromSerialized(file.readAll()); require(result.isValid(),"Invalid color shader"); return result;
    };
    const float vertices[]={-1,-1,3,-1,-1,3};
    std::unique_ptr<QRhiBuffer> vertex(rhi->newBuffer(QRhiBuffer::Immutable,QRhiBuffer::VertexBuffer,sizeof(vertices)));
    const int stride=rhi->ubufAligned(80);
    std::unique_ptr<QRhiBuffer> uniform(rhi->newBuffer(QRhiBuffer::Dynamic,QRhiBuffer::UniformBuffer,stride+80));
    require(vertex->create() && uniform->create(),"Cannot create RHI draw buffers");
    std::unique_ptr<QRhiShaderResourceBindings> bindings[2];
    std::unique_ptr<QRhiGraphicsPipeline> pipeline[2];
    const QColor foreground(73,121,167),background(219,197,181);
    QByteArray uniforms(stride+80,0); QMatrix4x4 matrix;
    for(int i=0;i<2;++i) {
        memcpy(uniforms.data()+i*stride,matrix.constData(),64);
        QVector4D color;
        for(int channelIndex=0;channelIndex<3;++channelIndex) {
            const double c=(channelIndex==0 ? foreground.redF() : channelIndex==1 ? foreground.greenF() : foreground.blueF());
            color[channelIndex]=float((compatible && i==0 ? decode(c) : c)*.4);
        }
        color[3]=.4; memcpy(uniforms.data()+i*stride+64,&color,16);
        bindings[i].reset(rhi->newShaderResourceBindings());
        bindings[i]->setBindings({QRhiShaderResourceBinding::uniformBuffer(0,QRhiShaderResourceBinding::VertexStage|QRhiShaderResourceBinding::FragmentStage,uniform.get(),i*stride,80)});
        require(bindings[i]->create(),"Cannot create draw bindings");
        pipeline[i].reset(rhi->newGraphicsPipeline());
        QRhiGraphicsPipeline::Flags flags=QRhiGraphicsPipeline::UsesScissor;
        if(compatible && i==0) flags|=static_cast<QRhiGraphicsPipeline::Flag>(1<<5);
        pipeline[i]->setFlags(flags);
        pipeline[i]->setShaderStages({{QRhiShaderStage::Vertex,shader("vert")},{QRhiShaderStage::Fragment,shader("frag")}});
        QRhiVertexInputLayout layout; layout.setBindings({{2*sizeof(float)}});
        layout.setAttributes({{0,0,QRhiVertexInputAttribute::Float2,0}});
        pipeline[i]->setVertexInputLayout(layout);
        QRhiGraphicsPipeline::TargetBlend blend; blend.enable=true;
        pipeline[i]->setTargetBlends({blend});
        pipeline[i]->setShaderResourceBindings(bindings[i].get());
        pipeline[i]->setRenderPassDescriptor(target->renderPassDescriptor());
        require(pipeline[i]->create(),"Cannot create draw pipeline");
    }
    control.beginFrame(); auto *cmd=control.commandBuffer();
    auto *updates=rhi->nextResourceUpdateBatch();
    updates->uploadStaticBuffer(vertex.get(),vertices);
    updates->updateDynamicBuffer(uniform.get(),0,uniforms.size(),uniforms.constData());
    cmd->beginPass(target,background,{1,0},updates);
    cmd->setViewport({0,0,float(texture->pixelSize().width()),float(texture->pixelSize().height())});
    for(int i=0;i<2;++i) {
        cmd->setGraphicsPipeline(pipeline[i].get());
        cmd->setScissor({i*80,0,80,40});
        cmd->setShaderResources(bindings[i].get());
        const QRhiCommandBuffer::VertexInput input(vertex.get(),0);
        cmd->setVertexInput(0,1,&input);
        cmd->draw(3);
    }
    cmd->endPass();
    const auto image=readTarget(control,texture);
    for(int i=0;i<2;++i) {
        const auto pixel=image.pixel(i*80+20,image.height()-20);
        require(qAbs(qRed(pixel)-channel(foreground.red(),background.red(),102,compatible && i==0))<=1
            && qAbs(qGreen(pixel)-channel(foreground.green(),background.green(),102,compatible && i==0))<=1
            && qAbs(qBlue(pixel)-channel(foreground.blue(),background.blue(),102,compatible && i==0))<=1,
            "Nonindexed selected draw or following ordinary draw changed");
    }
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

class ProfileWidget:public QWidget {
public:
    QFont fonts[3];
    QStaticText prepared[3];
    QVector<int> order;
    bool staticText=false;
    void paintEvent(QPaintEvent *) override {
        QPainter painter(this);
        for(int row=0;row<3;++row) {
            const QColor background=row==0 ? QColor(Qt::white) : row==1 ? QColor(Qt::black) : QColor(219,197,181);
            const QColor foreground=row==0 ? QColor(Qt::black) : row==1 ? QColor(Qt::white) : QColor(73,121,167);
            painter.fillRect(QRect(0,row*70,width(),70),background);
            painter.setPen(foreground);
            for(int column=0;column<order.size();++column) {
                const int role=order[column];
                painter.setFont(fonts[role]);
                const QPointF baseline(column*192+8,row*70+40);
                if(staticText)
                    painter.drawStaticText(baseline-QPointF(0,QFontMetricsF(fonts[role]).ascent()),prepared[role]);
                else
                    painter.drawText(baseline,prepared[role].text());
            }
        }
    }
};
}

int main(int argc,char **argv) {
    try {
        QQuickStyle::setStyle("org.kde.breeze");
        QApplication app(argc,argv);
        const auto busName=qEnvironmentVariable("FONTREAL_TEST_DBUS_NAME");
        if(!busName.isEmpty()) require(QDBusConnection::sessionBus().registerService(busName),"Cannot register activation service");
        const QStringList args=app.arguments();
        require(args.size()>=2,"Supply quick, widget, root, match, client, or view");
        const auto mode=args[1];
        if(mode=="crop") {
            require(args.size()==8,"crop input x y width height output");
            QImage image(args[2]);
            const QRect region(args[3].toInt(),args[4].toInt(),args[5].toInt(),args[6].toInt());
            require(!image.isNull() && !region.isEmpty() && image.rect().contains(region),"Invalid image crop");
            require(image.copy(region).convertToFormat(QImage::Format_RGB32).save(args[7]),"Cannot save image crop");
            return 0;
        }
        if(mode=="equal") {
            require(args.size()==4,"equal first second");
            const QImage a=QImage(args[2]).convertToFormat(QImage::Format_RGB32),b=QImage(args[3]).convertToFormat(QImage::Format_RGB32);
            require(!a.isNull() && !b.isNull() && a.size()==b.size(),"Presented opaque image dimensions differ from its buffer");
            // Use the glyph oracle's one-unit allowance for GPU rounding.
            for(int y=0;y<a.height();++y) for(int x=0;x<a.width();++x) {
                const auto p=a.pixel(x,y),q=b.pixel(x,y);
                require(std::max({qAbs(qRed(p)-qRed(q)),qAbs(qGreen(p)-qGreen(q)),qAbs(qBlue(p)-qBlue(q))})<=1,
                        "Presented opaque image differs from its buffer");
            }
            return 0;
        }
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
            caption("Actual Plasma applet, OpenGL: mild contrast / linear blend");
            for(int row:{0,4,5}) strip("nested-linear-1-default/plasma.png",QRect(0,16+row*56,760,52));
            caption("Actual Plasma applet, OpenGL: mild contrast / encoded blend");
            for(int row:{0,4,5}) strip("nested-encoded-1-default/plasma.png",QRect(0,16+row*56,760,52));
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
        if(mode=="profile") {
            require(args.size()==8,"profile truetype cff emoji output-prefix ordinary|static tt-first|cff-first");
            require(args[6]=="ordinary" || args[6]=="static","Invalid profile entry");
            require(args[7]=="tt-first" || args[7]=="cff-first","Invalid profile order");
            ProfileWidget widget;
            for(int i=0;i<3;++i) {
                widget.fonts[i]=loadFont(args[2+i]);
                if(i==1) widget.fonts[i].setStyleStrategy(QFont::NoSubpixelAntialias);
                widget.prepared[i]=QStaticText(i==2 ? QString::fromUtf8("😀") : QStringLiteral("m n o g W V"));
                widget.prepared[i].setTextFormat(Qt::PlainText);
                widget.prepared[i].prepare(QTransform(),widget.fonts[i]);
            }
            widget.staticText=args[6]=="static";
            widget.order=args[7]=="tt-first" ? QVector<int>{0,0,1,2,0} : QVector<int>{1,2,0,0,1};
            widget.resize(960,210); widget.show();
            QTimer::singleShot(350,&app,[&] {
              try {
                const QImage image=widget.grab().toImage();
                widget.repaint();
                require(image==widget.grab().toImage(),"Mixed cached repaint changed output");
                require(image.save(args[5]+".png"),"Mixed capture failed");
                QJsonArray regions;
                Face face(args[2],15),cffFace(args[3],15);
                bool colorGlyph=false;
                for(int row=0;row<3;++row) for(int column=0;column<widget.order.size();++column) {
                    const int role=widget.order[column];
                    const QRect region(column*192,row*70,192,70);
                    QJsonObject entry{{"row",row},{"column",column},{"role",role},{"hash",imageHash(image.copy(region))}};
                    if(role==0 || role==1) {
                        QJsonObject glyphs;
                        const QColor foreground=row==0 ? QColor(Qt::black) : row==1 ? QColor(Qt::white) : QColor(73,121,167);
                        const QColor background=row==0 ? QColor(Qt::white) : row==1 ? QColor(Qt::black) : QColor(219,197,181);
                        for(const auto c:QStringLiteral("mnogWV")) glyphs[QString(c)]=classify(image,region,role==0 ? face : cffFace,c,foreground,background);
                        entry["glyphs"]=glyphs;
                    } else if(role==2 && row==0) {
                        QSet<QRgb> colors;
                        for(int y=region.top();y<=region.bottom();++y) for(int x=region.left();x<=region.right();++x) {
                            const auto pixel=image.pixel(x,y);
                            if(qRed(pixel)!=qGreen(pixel) || qGreen(pixel)!=qBlue(pixel)) colors.insert(pixel);
                        }
                        colorGlyph=colors.size()>10;
                    }
                    regions.append(entry);
                }
                require(colorGlyph,"Mixed fixture did not draw a multicolor glyph");
                auto result=identity(); result["regions"]=regions; result["colorGlyph"]=colorGlyph;
                result["entry"]=args[6]; result["order"]=args[7]; writeJson(args[5]+".json",result); app.quit();
              } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); app.exit(2); }
            });
            return app.exec();
        }
        if(mode=="target") {
            require(args.size()==4 || (args.size()==5 && args[4]=="sunken"),"target truetype output-directory [sunken]");
            const bool styled=args.size()==5;
            const auto font=loadFont(args[2]);
            QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
            QQuickRenderControl control; QQuickWindow window(&control);
            QQmlEngine engine; QQmlComponent component(&engine);
            component.setData("import QtQuick; Rectangle { width: 760; height: 80; color: '#dbc5b5'; property font testFont; property bool sunken: false; Text { x: 16; y: 12; text: 'l m n o g W V w v'; font: parent.testFont; color: '#804979a7'; opacity: 0.75; renderType: Text.NativeRendering; style: parent.sunken ? Text.Sunken : Text.Normal; styleColor: '#b5a14b3f' } }",QUrl());
            std::unique_ptr<QObject> object(component.create());
            auto *item=qobject_cast<QQuickItem *>(object.get()); require(item,"Target QML failed");
            item->setProperty("testFont",font); item->setParentItem(window.contentItem());
            item->setProperty("sunken",styled);
            window.setGeometry(0,0,760,80); window.contentItem()->setSize({760,80});
            require(control.initialize(),"Render control initialization failed");
            auto *rhi=control.rhi(); require(rhi && rhi->backend()==QRhi::OpenGLES2,"Target is not OpenGL");
            std::unique_ptr<QRhiTexture> textures[2];
            std::unique_ptr<QRhiRenderBuffer> depth[2];
            std::unique_ptr<QRhiTextureRenderTarget> targets[2];
            std::unique_ptr<QRhiRenderPassDescriptor> passes[2];
            for(int i=0;i<2;++i) {
                auto flags=QRhiTexture::RenderTarget|QRhiTexture::UsedAsTransferSource;
                if(i==0) flags|=static_cast<QRhiTexture::Flag>(1<<15);
                textures[i].reset(rhi->newTexture(QRhiTexture::RGBA8,{760,80},1,flags));
                if(i==0) textures[i]->setWriteViewFormat({QRhiTexture::RGBA8,true});
                require(textures[i]->create(),"Target texture creation failed");
                depth[i].reset(rhi->newRenderBuffer(QRhiRenderBuffer::DepthStencil,{760,80},1));
                require(depth[i]->create(),"Target depth creation failed");
                QRhiTextureRenderTargetDescription description(textures[i].get());
                description.setDepthStencilBuffer(depth[i].get());
                targets[i].reset(rhi->newTextureRenderTarget(description));
                passes[i].reset(targets[i]->newCompatibleRenderPassDescriptor());
                targets[i]->setRenderPassDescriptor(passes[i].get());
                require(targets[i]->create(),"Target framebuffer creation failed");
            }
            QJsonArray frames;
            for(int frame=0;frame<3;++frame) {
                const int index=frame==1 ? 1 : 0;
                window.setRenderTarget(QQuickRenderTarget::fromRhiRenderTarget(targets[index].get()));
                QCoreApplication::processEvents(); control.polishItems(); control.beginFrame(); control.sync(); control.render();
                const auto image=readTarget(control,textures[index].get());
                require(image.save(args[3]+QString("/frame-%1.png").arg(frame)),"Cannot save target readback");
                Face face(args[2],15); QJsonObject glyphs;
                for(const auto c:QStringLiteral("lmnogWVwv")) glyphs[QString(c)]=styled ? classifySunken(image,face,c) : classify(image,image.rect(),face,c,QColor(73,121,167,128),QColor(219,197,181),.75);
                frames.append(QJsonObject{{"frame",frame},{"compatible",index==0},{"hash",imageHash(image)},{"glyphs",glyphs}});
            }
            for(int i=0;i<2;++i) nonindexedCheck(control,targets[i].get(),textures[i].get(),i==0);
            auto result=identity(); result["frames"]=frames; result["nonindexed"]=true; result["sunken"]=styled;
            writeJson(args[3]+"/result.json",result); return 0;
        }
        if(mode=="gpu") {
            require(args.size()==7,"gpu truetype cff emoji output-directory tt-first|cff-first");
            const auto tt=loadFont(args[2]);
            auto cff=loadFont(args[3]); cff.setStyleStrategy(QFont::NoSubpixelAntialias);
            const auto emoji=loadFont(args[4]);
            QQuickView view; view.setResizeMode(QQuickView::SizeRootObjectToView);
            view.setSource(QUrl::fromLocalFile(QStringLiteral(FONTREAL_SOURCE_DIR "/tests/KdeGpuMixed.qml")));
            require(view.status()==QQuickView::Ready,"Mixed QML fixture failed");
            auto *root=view.rootObject();
            root->setProperty("trueTypeFont",tt); root->setProperty("cffFont",cff); root->setProperty("emojiFont",emoji);
            root->setProperty("reverse",args[6]=="cff-first");
            QImage windowBuffer; QRhiReadbackResult windowReadback;
            bool grabbing=false,reading=false;
            QObject::connect(&view,&QQuickWindow::afterRendering,&view,[&] {
                if(grabbing || reading) return;
                auto *rhi=view.rhi();
                auto *swapchain=static_cast<QRhiSwapChain *>(view.rendererInterface()->getResource(&view,QSGRendererInterface::RhiSwapchainResource));
                if(!rhi || !swapchain) return;
                reading=true;
                windowReadback.completed=[&,rhi] {
                    const QImage raw(reinterpret_cast<const uchar *>(windowReadback.data.constData()),windowReadback.pixelSize.width(),windowReadback.pixelSize.height(),QImage::Format_RGBA8888_Premultiplied);
                    windowBuffer=(rhi->isYUpInFramebuffer() ? raw.mirrored(false,true) : raw.copy()).convertToFormat(QImage::Format_RGB32);
                    reading=false;
                };
                auto *updates=rhi->nextResourceUpdateBatch();
                updates->readBackTexture(QRhiReadbackDescription(),&windowReadback);
                swapchain->currentFrameCommandBuffer()->resourceUpdate(updates);
            },Qt::DirectConnection);
            view.resize(960,360); view.show();
            int frame=0; QJsonArray frames;
            QTimer timer; timer.setInterval(350);
            QObject::connect(&timer,&QTimer::timeout,&app,[&] {
              try {
                if(windowBuffer.isNull()) { view.update(); return; }
                grabbing=true;
                const auto image=view.grabWindow().convertToFormat(QImage::Format_RGB32);
                grabbing=false;
                require(!image.isNull(),"Mixed GPU capture failed");
                const bool hardware=qgetenv("LIBGL_ALWAYS_SOFTWARE")!="1";
                const auto presented=hardware ? windowBuffer : view.screen()->grabWindow(view.winId()).toImage().convertToFormat(QImage::Format_RGB32);
                require(presented.size()==image.size(),"Presented GPU size changed");
                require(image.save(args[5]+QString("/frame-%1.png").arg(frame)),"Cannot save mixed GPU image");
                require(presented.save(args[5]+QString("/window-%1.png").arg(frame)),"Cannot save presented GPU image");
                QJsonArray regions; QList<QQuickItem *> items; collectRegions(root,items);
                require(items.size()==14,"Missing mixed GPU regions");
                for(auto *item:items) {
                    const auto origin=item->mapToScene(QPointF());
                    const QRect rect(qRound(origin.x()),qRound(origin.y()),128,100);
                    const int role=item->property("role").toInt();
                    const auto part=image.copy(rect);
                    const auto windowPart=presented.copy(rect);
                    QJsonObject region{{"id",item->objectName()},{"role",role},
                        {"windowOrdinary",imageHash(windowPart.copy(0,42,128,58))},{"windowText",imageHash(windowPart.copy(0,0,128,42))},
                        {"ordinary",imageHash(part.copy(0,42,128,58))},{"text",imageHash(part.copy(0,0,128,42))}};
                    if(role>=3) {
                        const QString stem=item->objectName().replace('/','-')+QString("-%1").arg(frame);
                        require(part.copy(0,0,128,42).save(args[5]+"/"+stem+".png"),"Cannot save CFF Qt control");
                        require(windowPart.copy(0,0,128,42).save(args[5]+"/"+stem+"-window.png"),"Cannot save CFF Qt window control");
                        region["textImage"]=stem+".png"; region["windowTextImage"]=stem+"-window.png";
                    }
                    if(role!=2) {
                        Face face(role==0 ? args[2] : args[3],15); QJsonObject glyphs,windowGlyphs;
                        for(const auto c:QStringLiteral("mnogWV")) {
                            glyphs[QString(c)]=classify(image,QRect(rect.topLeft(),QSize(128,42)),face,c,
                                root->property("ink").value<QColor>(),root->property("color").value<QColor>(),.75);
                            windowGlyphs[QString(c)]=classify(presented,QRect(rect.topLeft(),QSize(128,42)),face,c,
                                root->property("ink").value<QColor>(),root->property("color").value<QColor>(),.75);
                        }
                        region["glyphs"]=glyphs;
                        region["windowGlyphs"]=windowGlyphs;
                    }
                    if(role==2) {
                        QSet<QRgb> colors,windowColors;
                        for(int y=0;y<42;++y) for(int x=0;x<128;++x) {
                            const auto p=part.pixel(x,y);
                            if(qRed(p)!=qGreen(p) && qGreen(p)!=qBlue(p) && p!=part.pixel(0,0)) colors.insert(p);
                            const auto w=windowPart.pixel(x,y);
                            if(qRed(w)!=qGreen(w) && qGreen(w)!=qBlue(w) && w!=windowPart.pixel(0,0)) windowColors.insert(w);
                        }
                        if(colors.size()<=10 || windowColors.size()<=10)
                            std::fprintf(stderr,"Emoji colors: capture=%lld presented=%lld frame=%d region=%s\n",static_cast<long long>(colors.size()),static_cast<long long>(windowColors.size()),frame,qPrintable(item->objectName()));
                        require(colors.size()>10 && windowColors.size()>10,"Mixed GPU emoji is missing its colors");
                        region["colorCount"]=colors.size();
                    }
                    regions.append(region);
                }
                frames.append(QJsonObject{{"frame",frame},{"hash",imageHash(image)},{"regions",regions}});
                if(++frame==3) {
                    auto result=identity(); result["frames"]=frames;
                    result["windowReadback"]=qgetenv("LIBGL_ALWAYS_SOFTWARE")!="1" ? "RHI window buffer before presentation" : "X11 presented window capture";
                    result["graphicsApi"]=int(view.rendererInterface()->graphicsApi());
                    writeJson(args[5]+"/result.json",result); app.quit(); return;
                } else if(frame==2) root->setProperty("ink",QColor(151,83,117,181));
                windowBuffer=QImage();
                view.update();
              } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); app.exit(2); }
            });
            timer.start(); return app.exec();
        }
        require(args.size()>=4,"Supply font file and output path");
        const auto font=loadFont(args[2]);
        if(mode=="widget" || mode=="client") {
            Widget widget; widget.face=font; widget.resize(760,370);
            if(args.size()>4) widget.text=args[4];
            if(args.size()>5 && args[5]=="gray") widget.face.setStyleStrategy(QFont::NoSubpixelAntialias);
            if(args.size()>5 && args[5]=="emoji") widget.face.setFamilies({widget.face.family(),QStringLiteral("Noto Color Emoji")});
            widget.setWindowTitle("l m n o g W V w v"); widget.show();
            new SurfaceObserver(widget.windowHandle(),args[3]+".surface.json");
            const auto capture=[&] {
              try {
                const auto image=widget.grab().toImage();
                require(image.save(args[3]+".png"),"Widget capture failed");
                auto result=identity(); result["imageHash"]=imageHash(image); result["font"]=widget.face.toString();
                QRawFont raw=QRawFont::fromFont(widget.face); QJsonArray masks; int missing=0;
                for(const auto glyph:raw.glyphIndexesForString(widget.text)) {
                    masks.append(maskHash(raw.alphaMapForGlyph(glyph,QRawFont::PixelAntialiasing)));
                    if(!glyph) ++missing;
                }
                QMap<QRgb,int> colors;
                const auto characters=widget.text.toUcs4();
                for(int i=0;i<characters.size();++i) if(!raw.supportsCharacter(characters[i])) {
                    const QRect cell=QRect(qRound((20+i*64)*widget.devicePixelRatioF()),0,
                                          qRound(64*widget.devicePixelRatioF()),qRound(60*widget.devicePixelRatioF())).intersected(image.rect());
                    for(int y=cell.top();y<=cell.bottom();++y) for(int x=cell.left();x<=cell.right();++x) {
                        const auto pixel=image.pixel(x,y);
                        if(qRed(pixel)!=qGreen(pixel) || qGreen(pixel)!=qBlue(pixel)) ++colors[pixel];
                    }
                }
                QJsonObject colorCounts;
                for(auto i=colors.cbegin();i!=colors.cend();++i) colorCounts[QString::number(i.key(),16)]=i.value();
                result["masks"]=masks; result["scale"]=widget.devicePixelRatioF();
                result["missingPrimaryGlyphs"]=missing; result["fallbackColors"]=colorCounts;
                writeJson(args[3]+".json",result);
                if(mode=="widget") app.quit();
              } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); app.exit(2); }
            };
            QTimer::singleShot(500,&app,capture);
            QTimer requests; requests.setInterval(150);
            QObject::connect(&requests,&QTimer::timeout,&app,[&] { if(QFile::remove(args[3]+".recapture")) capture(); });
            if(qgetenv("FONTREAL_TEST_HOLD")=="1") requests.start();
            return app.exec();
        }
        require((mode=="quick" || mode=="quick-hidden") && args.size()==5,"quick|quick-hidden font output-directory phase");
        const auto weightSequence=qgetenv("FONTREAL_TEST_WEIGHT_SEQUENCE").split(',');
        const bool changingWeight=!qgetenv("FONTREAL_TEST_WEIGHT_SEQUENCE").isEmpty();
        require(!changingWeight || weightSequence.size()==3,"Expected three weight states");
        if(changingWeight) require(qgetenv("FONTREAL_TEST_WEIGHT")==weightSequence[0],"Set the initial weight explicitly");
        QQuickView view; view.setResizeMode(QQuickView::SizeRootObjectToView);
        view.setSource(QUrl::fromLocalFile(QStringLiteral(FONTREAL_SOURCE_DIR "/tests/KdeTextGrid.qml")));
        require(view.status()==QQuickView::Ready,"QML fixture failed");
        view.rootObject()->setProperty("testFont",font); view.rootObject()->setProperty("phase",args[4].toDouble());
        if(!qgetenv("FONTREAL_TEST_LETTERS").isEmpty()) {
            const auto letters=QString::fromUtf8(qgetenv("FONTREAL_TEST_LETTERS"));
            require(letters.size()==9,"Expected nine grid letters");
            QStringList values; for(const auto c:letters) values.append(QString(c));
            view.rootObject()->setProperty("letters",values);
        }
        view.resize(760,370);
        if(mode=="quick") view.show();
        new SurfaceObserver(&view,args[3]+"/surface.json");
        QJsonArray frames;
        QJsonArray captureTimes;
        int frame=0;
        QTimer timer; timer.setInterval(350);
        QObject::connect(&timer,&QTimer::timeout,&app,[&] {
          try {
            QElapsedTimer elapsed; elapsed.start();
            const auto captured=view.grabWindow();
            const auto captureNs=elapsed.nsecsElapsed();
            const auto image=captured.convertToFormat(QImage::Format_RGB32);
            captureTimes.append(double(captureNs));
            require(!image.isNull(),"Quick capture failed");
            require(mode!="quick-hidden" || !view.isExposed(),"Hidden capture exposed its window");
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
                const auto hypotheses=classify(image,region,face,cell->property("character").toString()[0],fg,bg,view.rootObject()->property("glyphOpacity").toDouble());
                cells.append(QJsonObject{{"cell",cell->objectName()},{"path",cell->property("path").toInt()},
                    {"glyph",cell->property("character").toString()},{"renderType",text->property("renderType").toInt()},
                    {"font",actualFont.toString()},{"originX",glyphOrigin.x()},{"originY",glyphOrigin.y()},
                    {"expectedX",int(std::floor(glyphOrigin.x()+.5))+face.face->glyph->bitmap_left-1},
                    {"hypotheses",hypotheses}});
            }
            require(cells.size()==54,"Fixture did not produce every cell");
            require(image.save(args[3]+QString("/frame-%1.png").arg(frame)),"Cannot save Quick frame");
            const int controlledLeft=qRound(122*view.devicePixelRatio());
            frames.append(QJsonObject{{"frame",frame},{"hash",imageHash(image)},
                {"weight",QString::fromLatin1(qgetenv("FONTREAL_TEST_WEIGHT"))},
                {"scale",view.devicePixelRatio()},{"imageWidth",image.width()},{"imageHeight",image.height()},
                {"cellHash",imageHash(image.copy(controlledLeft,0,image.width()-controlledLeft,image.height()))},{"cells",cells}});
            if(++frame==5) { auto result=identity(); result["frames"]=frames; result["scale"]=view.devicePixelRatio();
                result["graphicsApi"]=int(view.rendererInterface()->graphicsApi()); result["phase"]=args[4].toDouble(); result["unexposed"]=mode=="quick-hidden";
                result["captureNanoseconds"]=captureTimes;
                writeJson(args[3]+"/result.json",result);
                if(qgetenv("FONTREAL_TEST_HOLD")=="1") {
                    timer.stop();
                    view.rootObject()->setProperty("ink",QColor(Qt::black)); view.rootObject()->setProperty("paper",QColor(Qt::white));
                    view.rootObject()->setProperty("glyphOpacity",1.); view.update();
                } else app.quit();
            } else if(frame==2) { view.rootObject()->setProperty("ink",QColor(Qt::white)); view.rootObject()->setProperty("paper",QColor(Qt::black)); }
            else if(frame==3) { view.rootObject()->setProperty("ink",QColor(73,121,167)); view.rootObject()->setProperty("paper",QColor(219,197,181)); }
            else if(frame==4) { view.rootObject()->setProperty("ink",QColor(73,121,167,128)); view.rootObject()->setProperty("glyphOpacity",.75); }
            if(changingWeight && (frame==2 || frame==3)) {
                const auto weight=weightSequence[frame==2 ? 1 : 2];
                auto next=font; next.setVariableAxis("wght",weight.toFloat());
                qputenv("FONTREAL_TEST_WEIGHT",weight);
                view.rootObject()->setProperty("testFont",next);
            }
            view.update();
          } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); app.exit(2); }
        });
        QTimer requests; requests.setInterval(150);
        QObject::connect(&requests,&QTimer::timeout,&app,[&] {
            if(QFile::remove(args[3]+"/recapture")) {
                frames=QJsonArray(); captureTimes=QJsonArray(); frame=0; timer.start();
            }
        });
        if(qgetenv("FONTREAL_TEST_HOLD")=="1") requests.start();
        // Stock distance-field text can finish its atlas after the first hidden grab.
        if(mode=="quick-hidden" && (qgetenv("FONTREAL_RENDERING")!="1"
            || qEnvironmentVariableIsSet("FONTREAL_TEST_STOCK_FALLBACK"))) view.grabWindow();
        timer.start(); return app.exec();
    } catch(const std::exception &error) { std::fprintf(stderr,"%s\n",error.what()); return 2; }
}
