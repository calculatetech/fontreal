#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include "runtime-build-id.h"

extern const unsigned char fontreal_qt_metadata[];
struct PluginMetadata { const void *bytes; size_t size; };

struct Provider {
    unsigned char gui[20];
    unsigned char quick[20];
    const char *directory;
};

static const struct Provider providers[] = {
#include "providers.inc"
};

__attribute__((visibility("default")))
struct PluginMetadata qt_plugin_query_metadata_v2(void)
{
    return (struct PluginMetadata){fontreal_qt_metadata + 24, METADATA_SIZE - 24};
}

__attribute__((visibility("default")))
void *qt_plugin_instance(void)
{
    const struct Provider *selected = NULL;
    for (size_t i = 0; i < sizeof(providers) / sizeof(providers[0]); ++i) {
        const struct Provider *provider = &providers[i];
        if (!runtimeBuildIdMatches("libQt6Gui.so.", NULL, provider->gui, sizeof(provider->gui)))
            continue;
        if (runtimeBuildIdMatches("libQt6Quick.so.", NULL, provider->quick, sizeof(provider->quick))) {
            selected = provider;
            break;
        }
#ifndef FONTREAL_QUICK_LOADER
        // A Widgets application may never load Qt Quick.
        if (!selected)
            selected = provider;
#endif
    }
    if (!selected)
        return NULL;

    Dl_info location;
    if (!dladdr((const void *)fontreal_qt_metadata, &location))
        return NULL;
    const char *slash = strrchr(location.dli_fname, '/');
    if (!slash)
        return NULL;
    char filename[4096];
    const int length = snprintf(filename, sizeof(filename), "%.*s/providers/%s/%s",
        (int)(slash-location.dli_fname), location.dli_fname, selected->directory, PROVIDER_FILE);
    if (length < 0 || (size_t)length >= sizeof(filename))
        return NULL;
    void *library = dlopen(filename, RTLD_LOCAL | RTLD_NOW | RTLD_NODELETE);
    if (!library)
        return NULL;
    void *(*instance)(void) = dlsym(library, "qt_plugin_instance");
    void *object = instance ? instance() : NULL;
    dlclose(library);
    return object;
}
