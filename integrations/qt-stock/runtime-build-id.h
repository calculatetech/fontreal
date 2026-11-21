#pragma once

#include <elf.h>
#include <link.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

static size_t align4(size_t value)
{
    return (value + 3) & ~(size_t)3;
}

struct Runtime {
    const char *prefix;
    const void *base;
    const unsigned char *identity;
    size_t identity_size;
    unsigned matched;
    unsigned compatible;
};

static int inspect(struct dl_phdr_info *object, size_t size, void *data)
{
    (void)size;
    struct Runtime *result = (struct Runtime *)data;
    if (result->base && (const void *)object->dlpi_addr != result->base)
        return 0;
    const char *name = strrchr(object->dlpi_name, '/');
    name = name ? name + 1 : object->dlpi_name;
    if (result->prefix && strncmp(name, result->prefix, strlen(result->prefix)) != 0)
        return 0;

    result->matched++;
    for (int i = 0; i < object->dlpi_phnum; ++i) {
        const ElfW(Phdr) *segment = object->dlpi_phdr + i;
        if (segment->p_type != PT_NOTE)
            continue;
        const unsigned char *bytes = (const unsigned char *)(object->dlpi_addr + segment->p_vaddr);
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

static bool runtimeBuildIdMatches(const char *prefix, const void *base,
                                 const unsigned char *identity, size_t identity_size)
{
    struct Runtime result = {prefix, base, identity, identity_size, 0, 0};
    dl_iterate_phdr(inspect, &result);
    return result.matched == 1 && result.compatible == 1;
}
