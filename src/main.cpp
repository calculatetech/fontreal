#include "experiment.h"
#include "window.h"
#include <QApplication>
#include <QCommandLineParser>
#include <QTextStream>
#include <memory>
#include <stdexcept>

int main(int argc, char **argv)
{
    for (int i = 1; i < argc; ++i)
        if (QByteArray(argv[i]) == "--export" || QByteArray(argv[i]).startsWith("--export=")) {
            if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM")) qputenv("QT_QPA_PLATFORM", "offscreen");
            break;
        }
    QApplication app(argc, argv);
    QCoreApplication::setApplicationName("fontreal");
    QCommandLineParser parser;
    parser.setApplicationDescription("Controlled TrueType comparison. Prioritize pixel alignment, then inspect gray edges.");
    parser.addHelpOption();
    parser.addOptions({
        {{"f", "font"}, "TrueType font file; default from fc-match sans-serif", "file"},
        {"size", "Font size in pixels before scale (6..48)", "pixels", "13"},
        {"scale", "Software scale, rasterized directly (0.5..3)", "factor", "1"},
        {"phase", "Horizontal device-pixel phase (0..1), quantized to 1/64", "pixels", "0.5"},
        {"fractional", "Keep fractional glyph origins instead of snapping"},
        {"dark", "White text on black"},
        {"linear", "Blend in linear light, then encode sRGB"},
        {"text", "Printable ASCII sample (1..96 characters)", "sample", Config{}.text},
        {"inspect", "Character to magnify (one visible ASCII character)", "character", "l"},
        {"export", "Write PNG and JSON results to a new or empty directory, then exit", "directory"}
    });
    parser.process(app);
    try {
        if (!parser.positionalArguments().isEmpty()) throw std::runtime_error("Unexpected positional arguments; use --help");
        Config config;
        config.font = parser.isSet("font") ? parser.value("font") : defaultFont();
        config.text = parser.value("text");
        config.inspect = parser.value("inspect");
        const auto number = [&](const char *name) {
            bool valid = false;
            const double value = parser.value(name).toDouble(&valid);
            if (!valid) throw std::runtime_error(QString("Invalid --%1 number").arg(name).toStdString());
            return value;
        };
        config.size = number("size");
        config.scale = number("scale");
        config.phase = number("phase");
        config.snap = !parser.isSet("fractional");
        config.dark = parser.isSet("dark");
        config.linear = parser.isSet("linear");
        if (parser.isSet("export")) {
            exportExperiment(renderExperiment(config), parser.value("export"));
            QTextStream(stdout) << "Wrote comparison to " << parser.value("export") << '\n';
            return 0;
        }
        std::unique_ptr<QWidget> window(createWindow(config));
        window->show();
        return app.exec();
    } catch (const std::exception &error) {
        QTextStream(stderr) << "fontreal: " << error.what() << '\n';
        return 2;
    }
}
