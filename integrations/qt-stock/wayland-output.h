#pragma once

#include <QCryptographicHash>
#include <QFile>
#include <QGuiApplication>
#include <QScopeGuard>
#include <QScreen>
#include <dlfcn.h>
#include <qpa/qplatformscreen.h>
#include "runtime-abi.h"

namespace fontreal_qt {

inline bool waylandPlatform()
{
    const auto platform = QGuiApplication::platformName();
    return platform == QStringLiteral("wayland") || platform == QStringLiteral("wayland-egl");
}

inline bool nativeWaylandScale()
{
    const auto scale = qEnvironmentVariable("QT_SCALE_FACTOR");
    return waylandPlatform()
        && (scale.isEmpty() || scale.toDouble() == 1.0)
        && !qEnvironmentVariableIsSet("QT_SCREEN_SCALE_FACTORS")
        && !qEnvironmentVariableIsSet("QT_DEVICE_PIXEL_RATIO")
        && qEnvironmentVariable("QT_ENABLE_HIGHDPI_SCALING") != QStringLiteral("0")
        && QGuiApplication::highDpiScaleFactorRoundingPolicy() == Qt::HighDpiScaleFactorRoundingPolicy::PassThrough;
}

template<typename Refresh>
void watchScreens(QObject *owner, Refresh refresh)
{
    const auto watch = [owner, refresh](QScreen *screen) {
        QObject::connect(screen, &QScreen::orientationChanged, owner, refresh);
        QObject::connect(screen, &QScreen::geometryChanged, owner, refresh);
    };
    for (auto *screen : QGuiApplication::screens())
        watch(screen);
    QObject::connect(qGuiApp, &QGuiApplication::screenAdded, owner, [watch, refresh](QScreen *screen) {
        watch(screen);
        refresh();
    });
    QObject::connect(qGuiApp, &QGuiApplication::screenRemoved, owner, refresh);
    refresh();
}

inline bool unrotatedWaylandScreen(const QScreen *screen)
{
    using NativeOrientation = Qt::ScreenOrientation (*)(const void *, int, Qt::ScreenOrientation);
    static const auto orientation = []() -> NativeOrientation {
        auto *module = dlopen("libQt6WaylandClient.so.6", RTLD_NOLOAD | RTLD_NOW);
        if (!module)
            return nullptr;
        const auto release = qScopeGuard([module] { dlclose(module); });
        const auto method = dlsym(module,
            "_ZNK15QtWaylandClient14QWaylandScreen19toScreenOrientationEiN2Qt17ScreenOrientationE");
        Dl_info info{};
        if (!method || !dladdr(method, &info) || !info.dli_fname)
            return nullptr;
        QFile file(QString::fromLocal8Bit(info.dli_fname));
        QCryptographicHash hash(QCryptographicHash::Sha256);
        if (!file.open(QIODevice::ReadOnly) || !hash.addData(&file)
                || hash.result().toHex() != FONTREAL_QT_WAYLAND_SHA)
            return nullptr;
        return reinterpret_cast<NativeOrientation>(method);
    }();
    auto *handle = screen->handle();
    if (!orientation || !handle
            || QByteArrayView(typeid(*handle).name()) != "N15QtWaylandClient14QWaylandScreenE")
        return false;
    const auto native = orientation(dynamic_cast<const void *>(handle), 0, Qt::PrimaryOrientation);
    return handle->orientation() == native;
}

} // namespace fontreal_qt
