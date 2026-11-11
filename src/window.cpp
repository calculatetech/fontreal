#include "window.h"
#include <QCheckBox>
#include <QDoubleSpinBox>
#include <QEvent>
#include <QFileDialog>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPainter>
#include <QPushButton>
#include <QScrollArea>
#include <QTabWidget>
#include <QVBoxLayout>
#include <cmath>
#include <memory>
#include <cfloat>

namespace {
class NumericControl : public QDoubleSpinBox {
public:
    QString textFromValue(double value) const override
    {
        return locale().toString(value, 'g', QLocale::FloatingPointShortest);
    }
};
}

void PixelCanvas::setImage(QImage image)
{
    image_ = std::move(image);
    resize(sizeHint());
    updateGeometry();
    update();
}

QSize PixelCanvas::sizeHint() const
{
    const double dpr = devicePixelRatioF();
    return {int(std::ceil(image_.width()/dpr)), int(std::ceil(image_.height()/dpr))};
}

void PixelCanvas::paintEvent(QPaintEvent *)
{
    QPainter painter(this);
    painter.fillRect(rect(), palette().window());
    // Cancel Qt's logical scaling so every source pixel occupies one backing-store pixel.
    painter.scale(1/devicePixelRatioF(), 1/devicePixelRatioF());
    painter.setRenderHint(QPainter::SmoothPixmapTransform, false);
    painter.drawImage(0, 0, image_);
}

bool PixelCanvas::event(QEvent *event)
{
    const bool handled = QWidget::event(event);
    if (event->type() == QEvent::DevicePixelRatioChange) {
        resize(sizeHint());
        updateGeometry();
        update();
    }
    return handled;
}

QWidget *createWindow(const Config &initial)
{
    renderExperiment(initial);
    auto *window = new QWidget;
    window->setWindowTitle("Fontreal — controlled FreeType comparison");
    window->resize(1100, 760);
    auto *layout = new QVBoxLayout(window);
    auto *intro = new QLabel("Compare existing rendering modes. Solid aligned stems are the target; the geometry tab illustrates it.");
    intro->setWordWrap(true);
    layout->addWidget(intro);
    auto *fontRow = new QHBoxLayout;
    auto *font = new QLineEdit(initial.font);
    font->setObjectName("font");
    font->setAccessibleName("TrueType font file");
    auto *browse = new QPushButton("Choose font…");
    fontRow->addWidget(new QLabel("Font file"));
    fontRow->addWidget(font, 1);
    fontRow->addWidget(browse);
    layout->addLayout(fontRow);
    auto *controls = new QHBoxLayout;
    const auto spin = [&](const QString &name, const QString &label, double low, double high, double step, double value) {
        auto *box = new NumericControl;
        box->setObjectName(name);
        box->setAccessibleName(label);
        box->setRange(low, high);
        box->setDecimals(DBL_MAX_10_EXP + DBL_DIG);
        box->setSingleStep(step);
        box->setValue(value);
        controls->addWidget(new QLabel(label));
        controls->addWidget(box);
        return box;
    };
    auto *size = spin("size", "Size (px)", 6, 48, 1, initial.size);
    auto *scale = spin("scale", "Scale", 0.5, 3, 0.25, initial.scale);
    auto *phase = spin("phase", "Phase (device px)", 0, 1, 0.25, initial.phase);
    auto *snap = new QCheckBox("Snap origins");
    snap->setObjectName("snap");
    snap->setChecked(initial.snap);
    auto *dark = new QCheckBox("Dark background");
    dark->setObjectName("dark");
    dark->setChecked(initial.dark);
    auto *linear = new QCheckBox("Linear-light blend");
    linear->setObjectName("linear");
    linear->setChecked(initial.linear);
    controls->addWidget(snap);
    controls->addWidget(dark);
    controls->addWidget(linear);
    layout->addLayout(controls);
    auto *text = new QLineEdit(initial.text);
    text->setObjectName("text");
    text->setAccessibleName("Printable ASCII sample");
    auto *sampleRow = new QHBoxLayout;
    sampleRow->addWidget(text, 1);
    sampleRow->addWidget(new QLabel("Inspect glyph"));
    auto *inspect = new QLineEdit(initial.inspect);
    inspect->setObjectName("inspect");
    inspect->setAccessibleName("Character to inspect at eight times its pixel size");
    inspect->setMaxLength(1);
    inspect->setMaximumWidth(48);
    sampleRow->addWidget(inspect);
    layout->addLayout(sampleRow);
    auto *tabs = new QTabWidget;
    QVector<PixelCanvas *> canvases;
    for (const QString name : {"Comparison", "Pixel detail", "Geometry target"}) {
        auto *area = new QScrollArea;
        auto *canvas = new PixelCanvas;
        canvas->setObjectName(name);
        canvas->setAccessibleName(name + " at one image pixel per backing-store pixel");
        area->setWidget(canvas);
        tabs->addTab(area, name);
        canvases.append(canvas);
    }
    layout->addWidget(tabs, 1);
    auto *status = new QLabel;
    status->setObjectName("status");
    status->setWordWrap(true);
    layout->addWidget(status);
    auto *save = new QPushButton("Export to an empty folder…");
    save->setObjectName("export");
    layout->addWidget(save);
    auto result = std::make_shared<Experiment>();
    const auto redraw = [=] {
        Config config{font->text(), text->text(), size->value(), scale->value(), phase->value(), snap->isChecked(), dark->isChecked(), linear->isChecked()};
        config.inspect = inspect->text();
        try {
            *result = renderExperiment(config);
            canvases[0]->setImage(result->comparison);
            canvases[1]->setImage(result->detail);
            canvases[2]->setImage(result->target);
            status->setText("1 image pixel = 1 Qt backing-store pixel. Scroll to inspect. LCD row assumes RGB stripes; compositor/display behavior is separate.");
            save->setEnabled(true);
        } catch (const std::exception &error) {
            for (auto *canvas : canvases) canvas->setImage({});
            status->setText(QString::fromUtf8(error.what()));
            save->setEnabled(false);
        }
    };
    QObject::connect(font, &QLineEdit::editingFinished, window, redraw);
    QObject::connect(text, &QLineEdit::editingFinished, window, redraw);
    QObject::connect(inspect, &QLineEdit::editingFinished, window, redraw);
    for (auto *box : {size, scale, phase}) QObject::connect(box, &QDoubleSpinBox::valueChanged, window, redraw);
    for (auto *box : {snap, dark, linear}) QObject::connect(box, &QCheckBox::toggled, window, redraw);
    QObject::connect(browse, &QPushButton::clicked, window, [=] {
        const QString selected = QFileDialog::getOpenFileName(window, "Choose a TrueType font", font->text(), "TrueType fonts (*.ttf *.ttc);;All files (*)");
        if (!selected.isEmpty()) { font->setText(selected); redraw(); }
    });
    QObject::connect(save, &QPushButton::clicked, window, [=] {
        const QString directory = QFileDialog::getExistingDirectory(window, "Choose a new or empty export folder");
        if (directory.isEmpty()) return;
        try { exportExperiment(*result, directory); }
        catch (const std::exception &error) { QMessageBox::critical(window, "Export failed", QString::fromUtf8(error.what())); }
    });
    redraw();
    return window;
}
