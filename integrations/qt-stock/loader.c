#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include "runtime-build-id.h"

extern const unsigned char fontreal_qt_metadata[];
struct PluginMetadata { const void *bytes; size_t size; };

__attribute__((visibility("default")))
struct PluginMetadata qt_plugin_query_metadata_v2(void)
{
    return (struct PluginMetadata){fontreal_qt_metadata + 24, METADATA_SIZE - 24};
}

__attribute__((visibility("default")))
void *qt_plugin_instance(void)
{
    static const unsigned char expected[] = { RUNTIME_ID };
    if (!runtimeBuildIdMatches(RUNTIME_PREFIX, NULL, expected, sizeof(expected)))
        return NULL;
#if defined(GUI_ID)
    static const unsigned char expected_gui[] = { GUI_ID };
    if (!runtimeBuildIdMatches("libQt6Gui.so.", NULL, expected_gui, sizeof(expected_gui)))
        return NULL;
#endif
    Dl_info location;
    if (!dladdr((const void *)fontreal_qt_metadata, &location))
        return NULL;
    const char *slash = strrchr(location.dli_fname, '/');
    if (!slash)
        return NULL;
    char filename[4096];
    const int length = snprintf(filename, sizeof(filename), "%.*s/%s",
        (int)(slash-location.dli_fname), location.dli_fname, PROVIDER_PATH);
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
