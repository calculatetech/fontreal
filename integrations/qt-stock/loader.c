#define _GNU_SOURCE
#include <dlfcn.h>
#include <elf.h>
#include <link.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

extern const unsigned char fontreal_qt_metadata[];
struct PluginMetadata { const void *bytes; size_t size; };

__attribute__((visibility("default")))
struct PluginMetadata qt_plugin_query_metadata_v2(void)
{
    return (struct PluginMetadata){fontreal_qt_metadata + 24, METADATA_SIZE - 24};
}

static size_t align4(size_t value)
{
    return (value + 3) & ~(size_t)3;
}

struct Runtime {
    const char *prefix;
    const unsigned char *identity;
    size_t identity_size;
    unsigned matched;
    unsigned compatible;
};

static int inspect(struct dl_phdr_info *object, size_t size, void *data)
{
    (void)size;
    struct Runtime *result = data;
    const char *name = strrchr(object->dlpi_name, '/');
    name = name ? name + 1 : object->dlpi_name;
    if (strncmp(name, result->prefix, strlen(result->prefix)) != 0)
        return 0;

    result->matched++;
    for (int i = 0; i < object->dlpi_phnum; ++i) {
        const ElfW(Phdr) *segment = object->dlpi_phdr + i;
        if (segment->p_type != PT_NOTE)
            continue;
        const unsigned char *bytes = (const void *)(object->dlpi_addr + segment->p_vaddr);
        size_t remaining = segment->p_filesz;
        while (remaining >= sizeof(ElfW(Nhdr))) {
            ElfW(Nhdr) header;
            memcpy(&header, bytes, sizeof(header));
            bytes += sizeof(header);
            remaining -= sizeof(header);
            const size_t name_size = align4(header.n_namesz);
            const size_t desc_size = align4(header.n_descsz);
            if (name_size > remaining || desc_size > remaining - name_size)
                break;
            if (header.n_type == NT_GNU_BUILD_ID && header.n_namesz == 4
                && !memcmp(bytes, "GNU", 4) && header.n_descsz == result->identity_size
                && !memcmp(bytes + name_size, result->identity, result->identity_size)) {
                result->compatible++;
                break;
            }
            bytes += name_size + desc_size;
            remaining -= name_size + desc_size;
        }
    }
    return 0;
}

static bool compatible(const char *prefix, const unsigned char *identity, size_t identity_size)
{
    struct Runtime result = {prefix, identity, identity_size, 0, 0};
    dl_iterate_phdr(inspect, &result);
    return result.matched == 1 && result.compatible == 1;
}

__attribute__((visibility("default")))
void *qt_plugin_instance(void)
{
    static const unsigned char expected[] = { RUNTIME_ID };
    if (!compatible(RUNTIME_PREFIX, expected, sizeof(expected)))
        return NULL;
#if defined(GUI_ID)
    static const unsigned char expected_gui[] = { GUI_ID };
    if (!compatible("libQt6Gui.so.", expected_gui, sizeof(expected_gui)))
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
