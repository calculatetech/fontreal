#pragma once
#include <QImage>
#include <QJsonObject>
#include <QString>
#include <QVector>

struct Config {
    QString font;
    QString text = "Illl1| minimum Hnmo 0123456789";
    double size = 13;
    double scale = 1;
    double phase = 0.5;
    bool snap = true;
    bool dark = false;
    bool linear = false;
    QString inspect = "l";
    bool edges = false;
};

struct Sample {
    QString id, name, unavailable;
    QImage coverage, rendered, glyph, inspected;
    QJsonObject metadata;
};

struct Experiment {
    QImage comparison, detail, target, snapped, fractional;
    QVector<Sample> samples;
    QJsonObject metadata;
};

QString defaultFont();
Experiment renderExperiment(const Config &config);
void exportExperiment(const Experiment &experiment, const QString &directory);
