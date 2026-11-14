#!/usr/bin/env python3
"""Refine encoded light coverage and multi-counter waists independently."""
import argparse
import ctypes as C
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFont

from browser_coverage_balance_test import font_weight
from browser_stroke_axis_test import Outline
from curve_contrast_test import ROOT, FACES, TEXT, Oracle, compose, sha
from core_contrast_test import middle_rows

POINTS = tuple(range(8, 17))
EXTRA = {
    'Noto Sans Light': 'noto/NotoSans-Light.ttf',
    'Noto Sans LightItalic': 'noto/NotoSans-LightItalic.ttf',
    'Noto Serif Light': 'noto/NotoSerif-Light.ttf',
    'Noto Serif LightItalic': 'noto/NotoSerif-LightItalic.ttf',
    'Lato LightItalic': 'lato/Lato-LightItalic.ttf',
    'Lato Regular': 'lato/Lato-Regular.ttf',
}
NAMES = FACES + list(EXTRA)


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, capture_output=True, text=True, **kwargs)


def matrix(rows, names=NAMES, points=POINTS):
    assert all('point_size' in r and r.get('font_point_size') == r['point_size'] for r in rows)
    keys = [(r['label'], r['point_size']) for r in rows]
    expected = {(name, point) for name in names for point in points}
    assert len(keys) == len(set(keys)) == len(expected) and set(keys) == expected
    return dict(zip(keys, rows))


def hard_table(cutoff):
    return [242 if cutoff <= a < 242 else a for a in range(256)]


def smooth_table():
    return [a + (a*(255-a)+510)//1020 for a in range(256)]


def expected_table(kind, weight):
    if weight >= 400 or kind == 'reference':
        return hard_table(128 if weight < 400 else 160)
    if kind == 'raw':
        return list(range(256))
    values = []
    with localcontext() as context:
        context.prec = 36
        for a in range(256):
            lift = (Decimal(a)*Decimal(255-a)/Decimal(1020)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            values.append(a+int(lift))
    return values


def scalar_mask(glyphs, height, table):
    pixels = bytearray(620*height)
    for glyph in glyphs:
        width = glyph['width']
        for i, value in enumerate(bytes.fromhex(glyph['mask'])):
            alpha = table[value]
            at = (glyph['y']+i//width)*620+glyph['x']+i%width
            pixels[at] = alpha+(pixels[at]*(255-alpha)+127)//255
    return bytes(pixels)


def counter_outline(oracle, snapshot, strength):
    base = oracle.outline(snapshot)
    orientation = oracle.ft.FT_Outline_Get_Orientation(C.byref(base))
    inner, start, counters = set(), 0, 0
    for end in snapshot['contours']:
        part = dict(outline=snapshot['outline'][start:end+1], contours=[end-start])
        direction = oracle.ft.FT_Outline_Get_Orientation(C.byref(oracle.outline(part)))
        if direction != 2 and orientation != 2 and direction != orientation:
            counters += 1
            inner.update(range(start,end+1))
        start = end+1
    if counters < 2:
        return snapshot, counters, set()
    expanded = oracle.outline(snapshot)
    assert oracle.ft.FT_Outline_EmboldenXY(C.byref(expanded), 0, strength) == 0
    points = [[x, expanded.points[i].y-strength//2 if i in inner else y, tag]
              for i,(x,y,tag) in enumerate(snapshot['outline'])]
    return dict(outline=points, contours=snapshot['contours']), counters, inner


def export_sheet(cases, modes, titles, images, layouts, target, font, palette, width=320):
    bg, fg = (255,0) if palette == 'light' else (0,255)
    blocks = []
    for key in cases:
        crops = []
        for mode in modes:
            source = images[mode,key,palette]
            limit = width-16
            native = source.crop((0,0,limit,source.height))
            row = layouts[key]
            details, total = [], 0
            for char in '835v':
                at = TEXT.index(char)
                left, right = int(row['runs'][at]['x'])-1, int(row['runs'][at+1]['x'])+2
                detail = source.crop((left,0,right,source.height))
                details.append(detail)
                total += detail.width*6+4
            assert total <= limit
            zoom = Image.new('RGB',(limit,source.height*6),(bg,)*3)
            x = 0
            for detail in details:
                large = detail.resize((detail.width*6,detail.height*6),Image.Resampling.NEAREST)
                zoom.paste(large,(x,0))
                x += large.width+4
            box = ImageChops.difference(zoom,Image.new('RGB',zoom.size,(bg,)*3)).getbbox()
            assert box
            crops.append((native,zoom.crop((0,box[1],limit,box[3]))))
        blocks.append((key,crops,32+max(n.height+d.height for n,d in crops)))
    canvas = Image.new('RGB',(4*width,76+sum(h for _,_,h in blocks)),(bg,)*3)
    draw = ImageDraw.Draw(canvas)
    draw.text((8,8),'Encoded reference | integer 8-16pt | native text and 6x excerpts: 8 3 5 v',font=font,fill=(fg,)*3)
    for column,title in enumerate(titles):
        draw.text((column*width+8,35),title,font=font,fill=(fg,)*3)
    y, checks = 66, []
    for key,crops,height in blocks:
        draw.text((8,y),f'{key[0].replace("LightItalic","Light Italic").replace("BoldItalic","Bold Italic")} | {key[1]:g}pt',font=font,fill=(fg,)*3)
        for column,(native,detail) in enumerate(crops):
            x = column*width+8
            for yy,crop in ((y+19,native),(y+19+native.height,detail)):
                canvas.paste(crop,(x,yy))
                checks.append((x,yy,crop))
        y += height
    canvas.save(target)
    with Image.open(target) as saved:
        for x,y,crop in checks:
            assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes() == crop.tobytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-study',type=Path,required=True)
    parser.add_argument('--native-build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args = parser.parse_args()
    initial_env = dict(os.environ)
    output, native = args.output.resolve(), args.native_build.resolve()
    work = (ROOT/'build/encoded-refinement').resolve()
    assert output.is_relative_to((ROOT/'results').resolve()) and native.is_relative_to((ROOT/'build').resolve())
    output.mkdir(parents=True,exist_ok=True)
    work.mkdir(parents=True,exist_ok=True)
    prior = json.loads((args.source_study/'qt/rows.json').read_text())
    faces = {r['label']:Path(r['font_path']) for r in prior}
    assert set(faces) == set(FACES)
    faces.update({name:Path('/usr/share/fonts/truetype')/file for name,file in EXTRA.items()})
    assert set(faces) == set(NAMES) and len(faces) == 19
    weights = {name:font_weight(path) for name,path in faces.items()}
    assert len([w for w in weights.values() if w < 400]) == 6
    libraries = {name:native/name/'.libs/libfreetype.so' for name in ('stock','nearest')}
    source = ROOT/'tests/point_benchmark_chart.cpp'
    patch = ROOT/'tests/point_counter_refinement.patch'
    provenance = json.loads((args.source_study/'build.json').read_text())
    assert provenance['source_archive_sha256'] == '9a2bdc2c992fa82a309eccf5e8bcbf2a380a98ba22f9f2ec7e56767739a19a0a'
    assert all(sha(libraries[k]) == provenance['libraries'][k] for k in libraries)
    protected = [source,patch,args.label_font,args.source_study/'build.json',args.source_study/'qt/rows.json',args.source_study/'50/rows.json',ROOT/'tests/curve_contrast_test.py']
    protected += list(faces.values())+list(libraries.values())
    before = {str(p):sha(p) for p in protected}
    env = {k:v for k,v in initial_env.items() if not k.startswith('FONTREAL_') and k not in ('LD_PRELOAD','LD_LIBRARY_PATH','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env.update(FONTREAL_RENDERING='0',QT_QPA_PLATFORM='offscreen',QT_FONT_DPI='96',FT2_DEBUG='any:0')
    flags = shlex.split(run(['pkg-config','--cflags','--libs','Qt6Gui','freetype2']).stdout)
    base = work/'chart'
    run(['c++','-std=c++17','-fPIC','-include','algorithm',source,*flags,'-o',base])
    cpp = work/'source/tests/point_benchmark_chart.cpp'
    cpp.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,cpp)
    run(['patch','--batch','--fuzz=0','-p1','-i',patch],cwd=work/'source')
    binaries = {}
    for strength in (8,16):
        binaries[strength] = work/f'counter-{strength}'
        run(['c++','-std=c++17','-fPIC','-include','algorithm',f'-DFONTREAL_COUNTER_STRENGTH={strength}',cpp,*flags,'-o',binaries[strength]])
    inputs = [dict(id=f'refine-{i:03}',label=name,font_path=str(faces[name]),point_size=point,
                   cutoff=128 if weights[name] < 400 else 160,logical_dpi=96,scale=1)
              for i,(name,point) in enumerate((n,p) for n in NAMES for p in POINTS)]
    input_file = work/'input.json'
    input_file.write_text(json.dumps(inputs,indent=2)+'\n')

    def capture(binary,mode,input_path,target,library):
        child = dict(env,LD_LIBRARY_PATH=str(libraries[library].parent))
        if mode == 'candidate':
            child['FREETYPE_PROPERTIES'] = 'autofitter:no-stem-darkening=1'
        run([binary,mode,input_path,target],env=child)
        return json.loads((target/'rows.json').read_text())

    datasets = {'qt':matrix(capture(base,'stock',input_file,output/'qt','stock'))}
    for mode,binary in (('reference',base),('counter8',binaries[8]),('counter16',binaries[16])):
        datasets[mode] = matrix(capture(binary,'candidate',output/'qt/rows.json',output/mode,'nearest'))
    good = list(datasets['qt'].values())
    for bad in (good[:-1]+[good[0]],good[:-1],[dict(good[0],point_size=8.5)]+good[1:],
                [{k:v for k,v in good[0].items() if k != 'point_size'}]+good[1:]):
        try:
            matrix(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError('bad matrix accepted')
    soft = smooth_table()
    assert soft == expected_table('soft',300) and soft[0] == 0 and soft[-1] == 255
    assert all(0 <= b-a <= 2 for a,b in zip(soft,soft[1:]))
    assert all(0 <= a <= 255 for a in soft)
    glyph = dict(width=1,height=1,x=0,y=0,mask='40')
    assert compose([glyph,glyph],1,128,table=soft).tobytes()[0] == 129
    assert soft[compose([glyph,glyph],1,128,table=list(range(256))).tobytes()[0]] == 128
    oracle = Oracle(libraries['stock'])
    oracle.ft.FT_Outline_Get_Orientation.argtypes = [C.POINTER(Outline)]
    old = {(r['label'],r['point_size']):r for r in json.loads((args.source_study/'50/rows.json').read_text()) if r['point_size'] in POINTS}
    images, profiles, checked = {}, [], 0
    for key,row in datasets['reference'].items():
        qt = datasets['qt'][key]
        assert row['weight'] == weights[key[0]] and row['font_sha256'] == before[row['font_path']]
        assert row['point_size'] in POINTS and len(row['runs']) == len(row['glyphs']) == len(TEXT) == 33
        assert row['logical_dpi'] == 96 and row['scale'] == 1
        if key in old:
            for field in ('font_sha256','base_px','runs','height','cutoff','weight','family','style'):
                assert row[field] == old[key][field],(key,field)
            assert row['glyphs'] == old[key]['glyphs']
        for mode in ('reference','counter8','counter16'):
            trial = datasets[mode][key]
            for field in ('font_sha256','runs','height','cutoff','weight','point_size','font_point_size'):
                assert trial[field] == row[field] == qt[field]
            for index,g in enumerate(trial['glyphs']):
                original = row['glyphs'][index]['loaded']
                if mode != 'reference':
                    expected,counters,inner = counter_outline(oracle,original,8 if mode == 'counter8' else 16)
                    assert g['loaded'] == expected
                    assert [(p[0],p[2]) for p in original['outline']] == [(p[0],p[2]) for p in g['loaded']['outline']]
                    assert all(g['loaded']['outline'][i] == p for i,p in enumerate(original['outline']) if i not in inner)
                bitmap = oracle.raster(g['loaded'])
                assert all(bitmap[k] == g[k] for k in ('mask','left','top','width','height'))
                assert g['glyph'] == trial['runs'][index]['glyph']
                assert g['x'] == int(trial['runs'][index]['x']//1)+g['left']
                assert g['y'] == int(trial['runs'][index]['y']+0.5)-g['top']
                checked += 1
            mask = compose(trial['glyphs'],trial['height'],trial['cutoff'])
            assert mask.tobytes() == (output/mode/(trial['id']+'-mask.bin')).read_bytes()
            for dark,palette in ((False,'light'),(True,'dark')):
                # Both studies keep encoded composition. Candidate C++ PNGs retain their original blend and are not relabeled.
                images[mode,key,palette] = mask.point(list(range(256)) if dark else list(range(255,-1,-1))).convert('RGB')
        for mode in ('raw','soft'):
            table = (list(range(256)) if mode == 'raw' else soft) if weights[key[0]] < 400 else None
            actual = compose(row['glyphs'],row['height'],row['cutoff'],table=table)
            independent = scalar_mask(row['glyphs'],row['height'],expected_table(mode,weights[key[0]]))
            assert actual.tobytes() == independent,(key,mode,'light export dispatch')
            for dark,palette in ((False,'light'),(True,'dark')):
                actual_rgb = actual.point(list(range(256)) if dark else list(range(255,-1,-1))).convert('RGB')
                expected_pixels = bytes(v for a in independent for v in ((a if dark else 255-a),)*3)
                assert actual_rgb.tobytes() == expected_pixels
                if weights[key[0]] >= 400:
                    assert actual_rgb.tobytes() == images['reference',key,palette].tobytes()
                images[mode,key,palette] = actual_rgb
        for palette in ('light','dark'):
            images['qt',key,palette] = Image.open(output/'qt'/f'{qt["id"]}-{palette}.png').convert('RGB')
        eight = row['glyphs'][TEXT.index('8')]
        center = -eight['top']+eight['height']//2
        profiles.append(dict(face=key[0],point=key[1],weight=weights[key[0]],waist={m:middle_rows(datasets[m][key]['glyphs'][TEXT.index('8')],(center-1,center),row['cutoff']) for m in ('reference','counter8','counter16')}))
    assert checked == 16929
    # Actual Qt B/g/O captures prove that eligibility follows shape, not an '8' selector.
    micro_source = work/'micro.cpp'
    source_text = source.read_text()
    assert source_text.count(TEXT) == 2
    micro_source.write_text(source_text.replace(TEXT,'B g O'))
    micro_binary = work/'micro-chart'
    run(['c++','-std=c++17','-fPIC','-include','algorithm',micro_source,*flags,'-o',micro_binary])
    micro_names = ['Noto Sans Regular','Noto Serif Regular','Lato Regular','Noto Sans Light','Noto Serif Light','Lato Light','Noto Serif Italic']
    micro_input = work/'micro-input.json'
    micro_input.write_text(json.dumps([dict(r,id=f'micro-{i}') for i,name in enumerate(micro_names) for r in inputs if r['label'] == name and r['point_size'] == 11],indent=2)+'\n')
    micro_qt = capture(micro_binary,'stock',micro_input,output/'micro-qt','stock')
    micro = {}
    for mode,binary in (('reference',base),('counter8',binaries[8]),('counter16',binaries[16])):
        micro[mode] = matrix(capture(binary,'candidate',output/'micro-qt/rows.json',output/('micro-'+mode),'nearest'),micro_names,(11,))
    micro_records = []
    for key,row in micro['reference'].items():
        assert len(row['glyphs']) == 5
        for index,char in enumerate('B g O'):
            original = row['glyphs'][index]['loaded']
            for mode in ('reference','counter8','counter16'):
                glyph = micro[mode][key]['glyphs'][index]
                if mode != 'reference':
                    expected,count,inner = counter_outline(oracle,original,8 if mode == 'counter8' else 16)
                    assert glyph['loaded'] == expected
                    micro_records.append(dict(face=key[0],char=char,mode=mode,counters=count,changed=glyph['loaded'] != original))
                bitmap = oracle.raster(glyph['loaded'])
                assert all(bitmap[k] == glyph[k] for k in ('mask','left','top','width','height'))
                checked += 1
    oracle.close()
    assert checked == 17034
    assert any(r['char'] == 'B' and r['changed'] for r in micro_records)
    assert any(r['char'] == 'g' and r['changed'] for r in micro_records)
    assert any(r['char'] == 'g' and r['counters'] < 2 and not r['changed'] for r in micro_records)
    assert all(not r['changed'] for r in micro_records if r['counters'] < 2)
    assert all(not r['changed'] for r in micro_records if r['char'] in ' O')
    label = ImageFont.truetype(str(args.label_font),13)
    outputs = []

    def save(cases,modes,titles,filename,palette,width=320):
        path = output/filename
        export_sheet(cases,modes,titles,images,datasets['qt'],path,label,palette,width)
        outputs.append(dict(file=filename,sha256=sha(path)))

    for palette in ('light','dark'):
        for family in ('Noto Sans','Noto Serif','Lato'):
            cases = [(family+' '+style,point) for point in (8,11) for style in ('Regular','Light','LightItalic')]
            slug = family.lower().replace(' ','-')
            save(cases,('reference','raw','soft','qt'),('Encoded reference','Light: no floor','Light: smooth lift','Stock Qt'),f'encoded-light-{slug}-{palette}.png',palette)
            full = [(family+' '+style,point) for point in POINTS for style in ('Light','LightItalic')]
            save(full,('reference','raw','soft','qt'),('Encoded reference','Light: no floor','Light: smooth lift','Stock Qt'),f'encoded-light-{slug}-8-16pt-{palette}.png',palette,520)
        cases = [(face,point) for point in (8,11) for face in ('Noto Sans Regular','Noto Serif Regular','Noto Serif Italic')]
        save(cases,('reference','counter8','counter16','qt'),('Encoded reference','Inner holes: mild','Inner holes: stronger','Stock Qt'),f'encoded-waist-{palette}.png',palette)
        for face in ('Noto Sans Regular','Noto Serif Italic'):
            slug = face.lower().replace(' ','-')
            save([(face,point) for point in POINTS],('reference','counter8','counter16','qt'),('Encoded reference','Inner holes: mild','Inner holes: stronger','Stock Qt'),f'encoded-waist-{slug}-8-16pt-{palette}.png',palette,520)
    assert before == {str(p):sha(p) for p in protected} and initial_env == dict(os.environ)
    report = dict(point_sizes=list(POINTS),conditions=[{k:r[k] for k in ('id','label','point_size','font_point_size','font_sha256','weight','cutoff')} for r in datasets['qt'].values()],
                  light_tables=dict(reference=hard_table(128),raw=list(range(256)),soft=soft),profiles=profiles,micro=micro_records,images=outputs,
                  native_masks_checked=checked,source_archive_sha256=provenance['source_archive_sha256'],source_sha256=sha(source),private_source_sha256=sha(cpp),
                  patch_sha256=sha(patch),checker_sha256=sha(Path(__file__)),compose_helper_sha256=sha(ROOT/'tests/curve_contrast_test.py'),
                  libraries={k:sha(v) for k,v in libraries.items()},qt_version=run(['pkg-config','--modversion','Qt6Gui']).stdout.strip(),
                  limits=['Separate coverage and geometry diagnostics; no combined policy selected','Counter orientation is a bounded static-TrueType study filter',
                          'Counter contraction may lose coverage or close a small hole; visual judgment remains required','No browser or application qualification'])
    (output/'encoded-refinement-captures.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS 171 integer-point conditions; {checked} independent native masks; light exporter scalar/Decimal oracle; {len(outputs)} verified images')


if __name__ == '__main__':
    main()
