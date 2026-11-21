#pragma once

#include <QCryptographicHash>
#include <QFile>
#include <QScopeGuard>
#include <QScreen>
#include <dlfcn.h>
#include <qpa/qplatformscreen.h>

namespace fontreal_qt {

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
                || hash.result().toHex() != "750d84878e449229d3a8973b5a5828ba7ddc37e485a7be01092db581ec2ea463")
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
