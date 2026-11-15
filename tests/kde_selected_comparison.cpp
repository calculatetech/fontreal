// Native Qt paint of the six requested KDE font roles. No bitmap reconstruction.
#include <QApplication>
#include <QFontDatabase>
#include <QLabel>
#include <QPlainTextEdit>
#include <QToolBar>
#include <QMenuBar>
#include <QVBoxLayout>
#include <QGroupBox>
#include <QPainter>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QDir>
#include <QRawFont>
#include <QJsonArray>
#include <stdexcept>
#include <utility>
#include <vector>

int main(int argc,char **argv) {
    QApplication app(argc,argv);
    if (argc!=6) return 2;
    app.setStyle("Fusion");
    bool dark=QString(argv[1])=="dark";
    QPalette palette;
    QColor background=dark ? QColor("#202124"):QColor("#f7f7f7");
    QColor foreground=dark ? QColor("#f1f3f4"):QColor("#171717");
    palette.setColor(QPalette::Window,background); palette.setColor(QPalette::WindowText,foreground);
    palette.setColor(QPalette::Base,dark ? QColor("#141516"):Qt::white);
    palette.setColor(QPalette::Text,foreground); palette.setColor(QPalette::Button,background);
    palette.setColor(QPalette::ButtonText,foreground); palette.setColor(QPalette::Highlight,QColor("#3c78a8"));
    palette.setColor(QPalette::HighlightedText,Qt::white); app.setPalette(palette);
    QFont general("Noto Sans",10); general.setStyleName("Regular"); app.setFont(general);
    QWidget root; root.setFixedSize(600,570);
    auto layout=new QVBoxLayout(&root); layout->setSpacing(9);
    std::vector<std::pair<QString,QWidget *>> observed;
    auto heading=new QLabel(QString(argv[2])); heading->setFont(QFont("Noto Sans",14,QFont::Bold)); layout->addWidget(heading);
    auto add=[&](const QString &title,QWidget *child) {
        observed.push_back({title.section(" / ",0,0),child});
        auto group=new QGroupBox(title); auto box=new QVBoxLayout(group); box->setContentsMargins(10,18,10,8);
        box->addWidget(child); layout->addWidget(group);
    };
    auto body=new QLabel("The quick brown fox jumps over the lazy dog.\nCurves, crowns and stems: a e o n m 3 5 8 W V");
    add("General / Noto Sans 10pt",body);
    auto terminal=new QPlainTextEdit("$ printf 'Hello, KDE! 0123456789'\nHello, KDE! 0123456789");
    QFont fixed("Hack",10); fixed.setStyleName("Regular"); terminal->setFont(fixed); terminal->setReadOnly(true);
    terminal->setFixedHeight(59); add("Fixed width / Hack 10pt",terminal);
    auto small=new QLabel("Ready. 24 files selected. Modified today at 10:35.  [ ] { } : ; ! ?");
    QFont smallFont=general; smallFont.setPointSize(8); small->setFont(smallFont);
    add("Small / Noto Sans 8pt",small);
    auto toolbar=new QToolBar; toolbar->setFont(general);
    for (const char *text:{"New","Open","Save","Search","Settings"}) toolbar->addAction(text);
    add("Toolbar / Noto Sans 10pt",toolbar);
    auto menu=new QMenuBar; menu->setNativeMenuBar(false); menu->setFont(general);
    for (const char *text:{"File","Edit","View","Bookmarks","Settings","Help"}) menu->addMenu(text);
    add("Menu / Noto Sans 10pt",menu);
    auto title=new QLabel("Documents — Dolphin                         −   □   ×"); title->setFont(general);
    add("Window title specimen / Noto Sans 10pt",title);
    layout->activate(); root.ensurePolished();
    QImage image(root.size(),QImage::Format_RGB32); image.setDotsPerMeterX(3780); image.setDotsPerMeterY(3780);
    image.fill(background); root.render(&image);
    QJsonArray roles;
    for (const auto &entry: observed) {
        QFont font=entry.second->font(); auto actual=QRawFont::fromFont(font);
        const char *file=entry.first=="Fixed width" ? argv[5]:argv[4];
        QRawFont source(QString::fromLocal8Bit(file),actual.pixelSize());
        for (const char *table:{"head","cmap","name"})
            if (!actual.isValid()||actual.fontTable(table)!=source.fontTable(table)) return 5;
        QPoint origin=entry.second->mapTo(&root,QPoint(0,0));
        roles.append(QJsonObject{{"role",entry.first},{"family",actual.familyName()},{"style",actual.styleName()},
                                 {"point_size",font.pointSize()},{"raster_size",actual.pixelSize()},
                                 {"x",origin.x()},{"y",origin.y()},{"width",entry.second->width()},{"height",entry.second->height()}});
    }
    if (!image.save(argv[3])) return 3;
    QFile maps("/proc/self/maps"), proof(QString(argv[3])+".maps");
    if (!maps.open(QIODevice::ReadOnly)||!proof.open(QIODevice::WriteOnly)) return 4;
    proof.write(maps.readAll());
    QFile metadata(QString(argv[3])+".json"); if (!metadata.open(QIODevice::WriteOnly)) return 6;
    metadata.write(QJsonDocument(QJsonObject{{"roles",roles},{"dpi",image.logicalDpiY()},
                                           {"device_pixel_ratio",image.devicePixelRatio()}}).toJson());
    return 0;
}
