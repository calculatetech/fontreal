#pragma once
#include "experiment.h"
#include <QWidget>

class PixelCanvas : public QWidget {
public:
    using QWidget::QWidget;
    void setImage(QImage image);
    const QImage &image() const { return image_; }
    QSize sizeHint() const override;
protected:
    void paintEvent(QPaintEvent *) override;
    bool event(QEvent *event) override;
private:
    QImage image_;
};

QWidget *createWindow(const Config &config);
