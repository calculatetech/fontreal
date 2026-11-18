# Keep the frozen V1 oracle intact while extending actual package probes for V2.
add_compile_options(-include "${CMAKE_CURRENT_LIST_DIR}/v2_freetype_reference.h")
