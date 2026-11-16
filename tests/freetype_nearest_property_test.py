#!/usr/bin/env python3
"""Check the TT/CFF nearest capability against independent and real older providers."""
import ctypes as C
import json
import os
from pathlib import Path
import shlex

import browser_live_recipe_test as recipe

PROPERTY = 'fontreal-nearest-y-v2'


def main():
    record, _, nearest = recipe.prepare()
    root = recipe.ROOT / 'build/qt-raw-profile'
    root.mkdir(exist_ok=True)
    source = (recipe.BUILD / 'freetype_mask_probe.cpp').read_text()
    needle = 'require(!FT_Init_FreeType(&library), "FT_Init_FreeType failed");'
    assert source.count(needle) == 1
    source = source.replace(needle, needle + '''
        FT_Bool current = true;
        require(!FT_Property_Get(library, "autofitter", "fontreal-nearest-y-v2", &current) && !current,
                "Nearest property must default off");
        FT_Bool nearest = qgetenv("FONTREAL_TEST_NEAREST_Y") == "1";
        require(!FT_Property_Set(library, "autofitter", "fontreal-nearest-y-v2", &nearest), "Cannot set nearest");
        FT_Set_Default_Properties(library);
        require(!FT_Property_Get(library, "autofitter", "fontreal-nearest-y-v2", &current) && current == nearest,
                "Environment properties changed nearest selection");
        FT_Library other = nullptr;
        require(!FT_Init_FreeType(&other), "Other library init failed");
        current = true;
        require(!FT_Property_Get(other, "autofitter", "fontreal-nearest-y-v2", &current) && !current,
                "Nearest selection leaked to another library");
        FT_Done_FreeType(other);
''')
    needle = 'const auto index = FT_Get_Char_Index(face, std::strtoul(argv[4], nullptr, 0));'
    lifecycle = '''QJsonArray lifecycle;
        if (qgetenv("FONTREAL_TEST_LIFECYCLE") == "1") {
            const bool selections[] = {true, false, true, true, true, true};
            const double sizes[] = {pixels, pixels, pixels, pixels + 1, pixels, pixels};
            const long deltas[] = {0, 0, 0, 0, 0, 32};
            const auto load = FT_Int32(std::strtol(argv[3], nullptr, 0));
            for (int step = 0; step < 6; ++step) {
                FT_Bool selected = selections[step];
                require(!FT_Property_Set(library, "autofitter", "fontreal-nearest-y-v2", &selected), "Selection failed");
                require(!FT_Set_Char_Size(face, std::lround(sizes[step] * 64), std::lround(sizes[step] * 64), 0, 0), "Size failed");
                require(!FT_Load_Glyph(face, FT_Get_Char_Index(face, std::strtoul(argv[4], nullptr, 0)), load), "Load failed");
                auto loaded = snapshot(face);
                FT_Outline_Translate(&face->glyph->outline, deltas[step], 0);
                QJsonArray rendered;
                for (int repeat = 0; repeat < 2; ++repeat) {
                    require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "Render failed");
                    rendered.append(snapshot(face));
                }
                require(!FT_Load_Glyph(face, FT_Get_Char_Index(face, 'g'), load), "Next load failed");
                require(!FT_Render_Glyph(face->glyph, FT_RENDER_MODE_NORMAL), "Next render failed");
                lifecycle.append(QJsonObject{{"selected", selections[step]}, {"size", sizes[step]},
                    {"dx", double(deltas[step])}, {"loaded", loaded}, {"rendered", rendered}, {"next", snapshot(face)}});
            }
            require(!FT_Property_Set(library, "autofitter", "fontreal-nearest-y-v2", &nearest), "Restore failed");
            require(!FT_Set_Char_Size(face, std::lround(pixels * 64), std::lround(pixels * 64), 0, 0), "Restore size failed");
        }
        '''
    assert source.count(needle) == 1
    source = source.replace(needle, lifecycle + needle)
    source = source.replace('result["rendered"] = rendered;', 'result["rendered"] = rendered; if (!lifecycle.isEmpty()) result["lifecycle"] = lifecycle;')
    cpp = root / 'property-probe.cpp'; cpp.write_text(source)
    flags = shlex.split(recipe.run(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'freetype2']).stdout)
    binary = root / 'property-probe'
    recipe.run(['c++', '-std=c++17', '-fPIC', '-include', 'algorithm', cpp, *flags, '-o', binary])
    candidate = record['libraries']['candidate']['library']; stock = record['libraries']['stock']['library']
    font = Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf')
    def probe(on, path=font, char='n', size=21, load=0x20028, lifecycle=False):
        env = dict(recipe.environment(candidate), FONTREAL_TEST_NEAREST_Y='1' if on else '0',
                   FONTREAL_TEST_LIFECYCLE='1' if lifecycle else '0',
                   FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1 autofitter:fontreal-nearest-y-v2=1')
        output = root / 'property.json'
        recipe.run([binary, path, size, hex(load), ord(char), 0, 0, 0, 2, output, 'none', 0], env=env)
        return json.loads(output.read_text())
    actual = probe(True); old = probe(False)
    assert actual == recipe.probe(nearest, font, size=21, char='n')
    assert old == recipe.probe(stock, font, size=21, char='n')
    assert actual['loaded']['outline'] != old['loaded']['outline']
    cases = []
    for path, char, size, load in [
        (font, 'n', 21, 0x10028), (font, 'n', 21, 0x28),
        (font, 'n', 21, 0x2002a), (font, 'n', 21, 0x20029),
        (Path('/usr/share/fonts/type1/urw-base35/NimbusSans-Regular.t1'), 'm', 15, 0x20028),
        (Path('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'), '😀', 109, 0x100000),
        (Path('/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz'), 'm', 13, 0),
    ]:
        assert probe(True, path, char, size, load) == probe(False, path, char, size, load), (path, load)
        cases.append(dict(font=str(path), flags=load))
    cff = []; changed = set()
    for name, path in recipe.CFF_FONTS.items():
        for point in range(8, 17):
            size = point * 96 / 72
            got = probe(True, path, 'm', size)
            base = probe(False, path, 'm', size)
            assert got == recipe.probe(nearest, path, size=size, char='m')
            assert base == recipe.probe(stock, path, size=size, char='m')
            assert got['font_format'] == 'CFF'
            if got['loaded'] != base['loaded']:
                changed.add(name)
            cff.append(dict(font=name, point_size=point, glyph=got['glyph']))
        steps = probe(True, path, 'm', 15, lifecycle=True)['lifecycle']
        for step in steps:
            want = recipe.probe(nearest if step['selected'] else stock, path, size=step['size'], char='m', dx=step['dx'])
            assert all(step[k] == want[k] for k in ('loaded', 'rendered', 'next')), (name, step['selected'], step['size'], step['dx'])
    assert len(cff) == 72 and len({(c['font'], c['point_size']) for c in cff}) == 72 and len(changed) >= 2
    cid = recipe.CFF_FONTS['Noto Sans CJK JP']
    for char in '漢国文':
        assert probe(True, cid, char, 15) == recipe.probe(nearest, cid, size=15, char=char)
    # A real TT-only v1 provider must reject v2, rather than advertise CFF support.
    _, older = recipe.v1_provider(record)
    assert recipe.sha(Path(older['library'])) == older['sha256']
    capability_checks = []
    for label, path in [('stock', stock), ('real-v1', older['library']), ('v2', candidate)]:
        ft = C.CDLL(str(path), mode=os.RTLD_LOCAL | os.RTLD_DEEPBIND); ft.FT_Init_FreeType.argtypes = [C.POINTER(C.c_void_p)]; ft.FT_Done_FreeType.argtypes = [C.c_void_p]
        ft.FT_Property_Get.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, C.c_void_p]
        ft.FT_Property_Set.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, C.c_void_p]
        library = C.c_void_p(); assert ft.FT_Init_FreeType(C.byref(library)) == 0
        value = C.c_ubyte(1)
        get = ft.FT_Property_Get(library, b'autofitter', PROPERTY.encode(), C.byref(value))
        set_result = ft.FT_Property_Set(library, b'autofitter', PROPERTY.encode(), C.byref(value))
        assert (get == 0 and set_result == 0) == (label == 'v2')
        if label == 'real-v1':
            assert ft.FT_Property_Get(library, b'autofitter', b'fontreal-nearest-y-v1', C.byref(value)) == 0
        ft.FT_Done_FreeType(library)
        capability_checks.append(dict(provider=label, path=str(path), v2_get=get, v2_set=set_result))
    # Current CFF2 coordinates share a face while the typed property switches off and on.
    variable = (recipe.ROOT / 'tests/freetype_variable_probe.cpp').read_text().replace('"ramp217"', '"raw"')
    variable = variable.replace('#include FT_MULTIPLE_MASTERS_H', '#include FT_MULTIPLE_MASTERS_H\n#include FT_MODULE_H')
    needle = 'setenv("FONTREAL_FT_CONTRAST",modes[step],1);'
    selected = 'FT_Bool selected = qgetenv("FONTREAL_TEST_PROPERTY") == "1" && QByteArray(modes[step]) == "raw"; check(!FT_Property_Set(library,"autofitter","fontreal-nearest-y-v2",&selected));'
    variants = {}
    for label, library, body in [('actual', candidate, variable.replace(needle, needle + selected)), ('nearest', nearest, variable), ('stock', stock, variable)]:
        source = root / f'property-variable-{label}.cpp'; source.write_text(body)
        program = root / f'property-variable-{label}'
        recipe.run(['c++', '-std=c++17', '-fPIC', source, *flags, '-o', program])
        output = root / f'property-variable-{label}.json'
        recipe.run([program, recipe.CFF_FONTS['Cantarell Variable'], 15, '0x20028', output],
                   env=dict(recipe.environment(library), FONTREAL_TEST_PROPERTY='1'))
        variants[label] = json.loads(output.read_text())
    for got, near, old in zip(variants['actual'], variants['nearest'], variants['stock'], strict=True):
        want = near if got['mode'] == 'raw' else old
        assert got['weight'] == got['requested_weight'] == want['weight'] and got['glyphs'] == want['glyphs']
    (root / 'property-results.json').write_text(json.dumps(dict(nearest=True, capability=PROPERTY, independent_libraries=True,
        environment_cannot_select=True, exclusions=cases, candidate=candidate, cff=cff,
        cff_changed_families=sorted(changed), same_face_lifecycle_steps=6, cff2_variable_steps=9,
        real_capability_checks=capability_checks), indent=2) + '\n')
    print('PASS native v2 nearest TT/CFF/CFF2/CID property, raw geometry, same-face lifecycle, real v1 refusal and exclusions')


if __name__ == '__main__':
    main()
