#include <QGuiApplication>
#include <QFontDatabase>
#include <QRawFont>
#include <QScreen>
#include <QTextLayout>
#include <QGlyphRun>
#include <QPainter>
#include <QImage>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QFile>
#include <QDir>
#include <QCryptographicHash>
#include <ft2build.h>
#include FT_FREETYPE_H
#include <cmath>
#include <stdexcept>
#include <iostream>
void check(bool b,const char*m){if(!b)throw std::runtime_error(m);}
QJsonDocument read(const QString&p){QFile f(p);check(f.open(QIODevice::ReadOnly),"read failed");QJsonParseError e;auto d=QJsonDocument::fromJson(f.readAll(),&e);check(e.error==QJsonParseError::NoError,"JSON failed");return d;}
void save(const QString&p,const QJsonDocument&d){QFile f(p);check(f.open(QIODevice::WriteOnly),"write failed");auto b=d.toJson();check(f.write(b)==b.size(),"short write");}
QString hash(const QByteArray&b){return QCryptographicHash::hash(b,QCryptographicHash::Sha256).toHex();}
int main(int argc,char**argv){try{
 QGuiApplication app(argc,argv);check(argc==4,"mode input output required");QString mode=argv[1],out=argv[3];QDir().mkpath(out);QJsonArray rows=read(argv[2]).array(),results;FT_Library lib=nullptr;if(mode=="candidate")check(!FT_Init_FreeType(&lib),"FT init failed");
 for(auto value:rows){auto r=value.toObject();QString file=r["font_path"].toString(),id=r["id"].toString();double dpi=r.contains("logical_dpi")?r["logical_dpi"].toDouble():app.primaryScreen()->logicalDotsPerInchY();double scale=r.contains("scale")?r["scale"].toDouble():app.primaryScreen()->devicePixelRatio();double size=r["base_px"].toDouble();bool points=r.contains("point_size");if(mode=="stock"&&points)size=r["point_size"].toDouble()*dpi/72.;double px=size*scale;int cutoff=r["cutoff"].toInt();r["scale"]=scale;r["nominal_base_px"]=points?r["point_size"].toDouble()*dpi/72.:size;
 if(mode=="stock"){
  int registered=QFontDatabase::addApplicationFont(file);check(registered>=0,"font register failed");QRawFont source(file,px);check(source.isValid(),"raw font failed");QFont f(source.familyName());f.setStyleName(source.styleName());f.setWeight(QFont::Weight(source.weight()));f.setStyle(source.style());if(points){f.setPointSizeF(r["point_size"].toDouble());check(f.pointSizeF()==r["point_size"].toDouble(),"point API mismatch");r["font_point_size"]=f.pointSizeF();}else f.setPixelSize(int(size));
  QImage device(620,int(std::ceil(px*4))+24,QImage::Format_RGB32);device.setDevicePixelRatio(scale);device.setDotsPerMeterX(std::lround(dpi/0.0254));device.setDotsPerMeterY(std::lround(dpi/0.0254));r["logical_dpi"]=device.logicalDpiY();r["screen_logical_dpi"]=app.primaryScreen()->logicalDotsPerInchY();double resolved=-1;QJsonArray runs;double y=8/scale;
  for(auto txt:QList<QString>{"ilI1 minimum 0358 VvWw 0123456789"}){
   QTextLayout layout(txt,f,&device);layout.beginLayout();auto line=layout.createLine();line.setLineWidth(600/scale);layout.endLayout();line.setPosition(QPointF(0,y));check(line.textLength()==txt.size(),"text clipped or wrapped");check(line.naturalTextWidth()*scale<600,"text width overflow");
   for(auto run:layout.glyphRuns()){
    check(run.rawFont().fontTable("head")==source.fontTable("head"),"font substitution");if(resolved<0)resolved=run.rawFont().pixelSize();check(std::abs(run.rawFont().pixelSize()-resolved)<.02,"inconsistent resolved pixel size");auto indexes=run.glyphIndexes();auto positions=run.positions();check(indexes.size()==positions.size(),"glyph positions mismatch");
    for(int i=0;i<indexes.size();++i)runs.append(QJsonObject{{"glyph",int(indexes[i])},{"x",8+positions[i].x()*scale},{"y",positions[i].y()*scale}});
   }
   y+=line.height()+3/scale;
  }
  check(resolved>0,"missing resolved pixel size");r["base_px"]=resolved;int height=int(std::ceil(y*scale))+8;r["height"]=height;r["runs"]=runs;r["family"]=source.familyName();r["style"]=source.styleName();auto os2=source.fontTable("OS/2");check(os2.size()>=6,"OS2 weight missing");int weight=(int((unsigned char)os2[4])<<8)|int((unsigned char)os2[5]);r["weight"]=weight;r["qt_reported_weight"]=source.weight();QFile fontFile(file);check(fontFile.open(QIODevice::ReadOnly),"font read failed");r["font_sha256"]=hash(fontFile.readAll());check((weight<400?128:160)==cutoff,"weight cutoff differs");
  for(bool dark:{false,true}){QImage image(620,height,QImage::Format_RGB32);image.setDevicePixelRatio(scale);image.setDotsPerMeterX(device.dotsPerMeterX());image.setDotsPerMeterY(device.dotsPerMeterY());image.fill(dark?Qt::black:Qt::white);QPainter p(&image);p.setPen(dark?Qt::white:Qt::black);p.setFont(f);double yy=8/scale;
   for(auto txt:QList<QString>{"ilI1 minimum 0358 VvWw 0123456789"}){QTextLayout l(txt,f,&image);l.beginLayout();auto ln=l.createLine();ln.setLineWidth(600/scale);l.endLayout();ln.setPosition(QPointF(0,yy));l.draw(&p,QPointF(8/scale,0));yy+=ln.height()+3/scale;}p.end();image.setDevicePixelRatio(1);check(image.save(out+"/"+id+(dark?"-dark.png":"-light.png")),"stock PNG failed");}
  QFontDatabase::removeApplicationFont(registered);
 }else{
  check(mode=="candidate","invalid mode");FT_Face face;check(!FT_New_Face(lib,QFile::encodeName(file).constData(),0,&face),"FT face failed");check(!FT_Set_Char_Size(face,std::lround(px*64),std::lround(px*64),0,0),"FT size failed");int height=r["height"].toInt();QByteArray mask(620*height,0);QJsonArray glyphs;
  for(auto rv:r["runs"].toArray()){auto run=rv.toObject();int index=run["glyph"].toInt();check(!FT_Load_Glyph(face,index,FT_LOAD_FORCE_AUTOHINT|FT_LOAD_TARGET_MONO|FT_LOAD_NO_BITMAP),"FT load failed");QJsonArray points,ends;for(int i=0;i<face->glyph->outline.n_points;++i)points.append(QJsonArray{double(face->glyph->outline.points[i].x),double(face->glyph->outline.points[i].y),int(face->glyph->outline.tags[i])});for(int i=0;i<face->glyph->outline.n_contours;++i)ends.append(int(face->glyph->outline.contours[i]));QJsonObject loaded{{"outline",points},{"contours",ends}};check(!FT_Render_Glyph(face->glyph,FT_RENDER_MODE_NORMAL),"FT render failed");auto &b=face->glyph->bitmap;check(b.pixel_mode==FT_PIXEL_MODE_GRAY,"not grayscale");int x=int(std::floor(run["x"].toDouble()))+face->glyph->bitmap_left,y=int(std::lround(run["y"].toDouble()))-face->glyph->bitmap_top;check(x>=0&&y>=0&&x+int(b.width)<=620&&y+int(b.rows)<=height,"candidate clipped");QByteArray raw;
   for(unsigned yy=0;yy<b.rows;++yy)for(unsigned xx=0;xx<b.width;++xx){int a=b.buffer[yy*b.pitch+xx];raw.append(char(a));int v=(a>=cutoff&&a<242)?242:a;int at=(y+yy)*620+x+xx;mask[at]=char(v+(int((unsigned char)mask[at])*(255-v)+127)/255);}
   glyphs.append(QJsonObject{{"glyph",index},{"loaded",loaded},{"x",x},{"y",y},{"left",face->glyph->bitmap_left},{"top",face->glyph->bitmap_top},{"width",int(b.width)},{"height",int(b.rows)},{"mask",QString::fromLatin1(raw.toHex())}});
  }
  r["glyphs"]=glyphs;r["composed_mask_sha256"]=hash(mask);check(mask.size()==620*height,"mask length");QFile m(out+"/"+id+"-mask.bin");check(m.open(QIODevice::WriteOnly)&&m.write(mask)==mask.size(),"mask write failed");
  for(bool dark:{false,true}){QImage image(620,height,QImage::Format_RGB32);for(int yy=0;yy<height;++yy)for(int xx=0;xx<620;++xx){int a=(unsigned char)mask[yy*620+xx];double linear=dark?a/255.:1-a/255.;double encoded=linear<=.0031308?12.92*linear:1.055*std::pow(linear,1/2.4)-.055;int v=std::clamp(int(std::lround(encoded*255)),0,255);image.setPixel(xx,yy,qRgb(v,v,v));}check(image.save(out+"/"+id+(dark?"-dark.png":"-light.png")),"candidate PNG failed");}FT_Done_Face(face);
 }
 results.append(r);
 }
 if(lib)FT_Done_FreeType(lib);save(out+"/rows.json",QJsonDocument(results));std::cout<<mode.toStdString()<<" PASS "<<results.size()<<" conditions\n";return 0;
 }catch(std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
