#pragma once

#include <algorithm>
#include <cstdint>
#include <dlfcn.h>
#include <link.h>
#include <sys/mman.h>
#include <unistd.h>

namespace fontreal_qt {

inline void **methodSlot(void **table, void *method)
{
    Dl_info owner{}, target{};
    void *symbol = nullptr;
    if (!table || !method || !dladdr1(table, &owner, &symbol, RTLD_DL_SYMENT) || !symbol
            || !dladdr(method, &target) || owner.dli_fbase != target.dli_fbase)
        return nullptr;
    const auto size = static_cast<const ElfW(Sym) *>(symbol)->st_size;
    if (size <= 2 * sizeof(void *) || size % sizeof(void *))
        return nullptr;
    auto *end = table + size / sizeof(void *);
    auto *slot = std::find(table + 2, end, method);
    return slot != end && std::find(slot + 1, end, method) == end ? slot : nullptr;
}

inline bool replacePointer(void **slot, void *value)
{
    const long pageSize = sysconf(_SC_PAGESIZE);
    if (pageSize <= 0)
        return false;
    const auto address = reinterpret_cast<uintptr_t>(slot);
    auto *page = reinterpret_cast<void *>(address - address % pageSize);
    if (mprotect(page, pageSize, PROT_READ | PROT_WRITE))
        return false;
    auto *previous = __atomic_exchange_n(slot, value, __ATOMIC_RELEASE);
    if (!mprotect(page, pageSize, PROT_READ))
        return true;
    __atomic_store_n(slot, previous, __ATOMIC_RELEASE);
    return false;
}

} // namespace fontreal_qt
