#!/usr/bin/env python3
"""Test native dropout guidance without changing the accepted ramp elsewhere."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import re
import shlex
import shutil

from PIL import Image, ImageChops, ImageDraw, ImageFont

from browser_coverage_balance_test import font_weight
from browser_stroke_axis_test import Bitmap
from core_contrast_test import middle_rows
from coverage_shoulder_test import coverage_table, expected_table, self_check
from curve_contrast_test import ROOT, TEXT, Oracle, compose, sha
from encoded_refinement_test import matrix, scalar_mask, run


def mono_raster(oracle, snapshot, ignore):
    outline = oracle.outline(snapshot)
    if not outline.n_points:
        return dict(width=0,height=0,left=0,top=0,mask='')
    first = 0
    for end in snapshot['contours']:
        assert not snapshot['outline'][first][2] & 4
        first = end+1
    outline.flags = 8 if ignore else 0
    points = outline.points[:outline.n_points]
    left, bottom = min(p.x for p in points)//64, min(p.y for p in points)//64
    right, top = -(-max(p.x for p in points)//64), -(-max(p.y for p in points)//64)
    width, height = right-left, top-bottom
    for p in points:
        p.x -= left*64
        p.y -= bottom*64
    stride = (width+7)//8
    pixels = (C.c_ubyte*(stride*height))()
    bitmap = Bitmap(height,width,stride,pixels,2,1,0,None)
    assert oracle.ft.FT_Outline_Get_Bitmap(oracle.handle,C.byref(outline),C.byref(bitmap)) == 0
    return dict(width=width,height=height,left=left,top=top,mask=bytes(pixels).hex())


def bits(raw, width, height):
    assert len(raw) == ((width+7)//8)*height
    stride = (width+7)//8
    return bytes(bool(raw[y*stride+x//8] & (128>>(x%8))) for y in range(height) for x in range(width))


def support_pixels(record):
    width, height = record['width'], record['height']
    if not width or not height:
        assert record['with'] == record['ignored'] == ''
        return b''
    enabled, ignored = [Image.frombytes('1',(width,height),bytes.fromhex(record[k])).convert('L').tobytes()
                        for k in ('with','ignored')]
    assert all(not b or a for a,b in zip(enabled,ignored))
    return bytes(bool(a and not b) for a,b in zip(enabled,ignored))


def guard(glyph, selected, table, floor):
    raw = bytes.fromhex(glyph['mask'])
    assert len(raw) == len(selected)
    return dict(glyph,mask=bytes(max(table[a],floor) if on else table[a] for a,on in zip(raw,selected)).hex())


def export(cases, images, rows, path, font, palette, width):
    bg, fg = (255,0) if palette == 'light' else (0,255)
    modes = ('reference','guard192','guard217','qt')
    blocks = []
    for key in cases:
        columns = []
        for mode in modes:
            image, row = images[mode,key,palette], rows[key]
            box = ImageChops.difference(image,Image.new('RGB',image.size,(bg,)*3)).getbbox()
            assert box is None or box[2] <= width-16,(key,mode,'native text clipped')
            native = image.crop((0,0,width-16,image.height))
            zoom = Image.new('RGB',(width-16,image.height*6),(bg,)*3)
            x, two = 0, None
            for char in '2vW':
                at = TEXT.index(char)
                left, right = int(row['runs'][at]['x'])-1, int(row['runs'][at+1]['x'])+2
                crop = image.crop((left,0,right,image.height))
                large = crop.resize((crop.width*6,crop.height*6),Image.Resampling.NEAREST)
                assert x+large.width <= zoom.width
                zoom.paste(large,(x,0))
                if char == '2':
                    two = (left,crop,large)
                x += large.width+4
            box = ImageChops.difference(zoom,Image.new('RGB',zoom.size,(bg,)*3)).getbbox()
            assert box and two
            columns.append((native,zoom.crop((0,box[1],zoom.width,box[3])),two,box[1:4:2]))
        blocks.append((key,columns,32+max(n.height+z.height for n,z,_,_ in columns)))
    canvas = Image.new('RGB',(width*4,76+sum(h for _,_,h in blocks)),(bg,)*3)
    draw = ImageDraw.Draw(canvas)
    draw.text((8,8),'Native dropout continuity | integer 8-16pt | native text and 6x: 2 v W',font=font,fill=(fg,)*3)
    for col,title in enumerate(('Accepted ramp','Native support: 192','Native support: 217','Stock Qt')):
        draw.text((col*width+8,35),title,font=font,fill=(fg,)*3)
    y, checks = 66, []
    for key,columns,height in blocks:
        draw.text((8,y),f'{key[0]} | {key[1]:g}pt',font=font,fill=(fg,)*3)
        for col,(native,zoom,two,(top,bottom)) in enumerate(columns):
            x, yy = col*width+8, y+19
            canvas.paste(native,(x,yy));checks.append((x,yy,native))
            left,crop,large = two
            checks.append((x+left,yy,crop))
            canvas.paste(zoom,(x,yy+native.height));checks.append((x,yy+native.height,zoom))
            checks.append((x,yy+native.height,large.crop((0,top,large.width,bottom))))
        y += height
    canvas.save(path)
    with Image.open(path) as saved:
        for x,y,crop in checks:
            assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes() == crop.tobytes()


def ownership(build, output, rows, env):
    observations = []
    for name in ('Noto Serif Regular','Noto Sans Regular'):
        row = rows[name,11]
        glyph = row['glyphs'][TEXT.index('2')]
        target = output/(name.lower().replace(' ','-')+'-2-trace.json')
        result = run([build/'probe',row['font_path'],row['base_px'],'0x20028',ord('2'),0,0,0,2,target,'none',0],
                     env=dict(env,LD_LIBRARY_PATH=str(build/'nearest-owners/.libs'),FT2_DEBUG='aflatin:6,afhints:7,afmodule:7'))
        probe = json.loads(target.read_text())
        assert probe['glyph'] == glyph['glyph'] == 21
        assert all(probe['loaded'][k] == glyph['loaded'][k] for k in ('outline','contours'))
        assert probe['rendered'][0] == probe['rendered'][1]
        assert all(probe['rendered'][0][k] == glyph[k] for k in ('mask','width','height','left','top'))
        lines, frames = result.stderr.splitlines(), {}
        for i,line in enumerate(lines):
            match = re.fullmatch(r'FR_STAGE glyph=21 dim=(\d+) stage=(\w+) count=(\d+)',line)
            if match:
                points = [dict((k,int(v)) for k,v in re.findall(r'(\w+)=(-?\d+)',s)) for s in lines[i+1:i+1+int(match[3])]]
                assert [p['id'] for p in points] == list(range(len(glyph['loaded']['outline'])))
                key = (int(match[1]),match[2]);assert key not in frames
                frames[key] = points
        assert set(frames) == {(d,s) for d in (0,1) for s in ('edge','strong','weak','final')} | {(1,'save')}
        shifts = {(x-p['x'],y-p['y']) for p,(x,y,_) in zip(frames[1,'save'],glyph['loaded']['outline'])}
        assert len(shifts) == 1 and next(iter(shifts))[1] == 0
        observation = dict(face=name,point=11,char='2',loader_translation=list(next(iter(shifts))),
                           weak_x=[b['x']-a['x'] for a,b in zip(frames[0,'strong'],frames[0,'weak'])],
                           weak_y=[b['y']-a['y'] for a,b in zip(frames[1,'strong'],frames[1,'weak'])])
        if name == 'Noto Serif Regular':
            assert [observation['weak_x'][i] for i in (2,25)] == [18,-10]
            observation['paired_points'] = dict(ids=[2,25],x_gap_before_weak=73,x_gap_after_weak=45,final_y_gap=6)
        observations.append(observation);target.unlink()
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-study','ramp-study','native-build','output','label-font'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    original_env = dict(os.environ)
    source, output, build = args.source_study.resolve(), args.output.resolve(), args.native_build.resolve()
    assert output.is_relative_to((ROOT/'results').resolve()) and build.is_relative_to((ROOT/'build').resolve())
    output.mkdir(parents=True,exist_ok=True)
    work = ROOT/'build/dropout-continuity'
    cpp = work/'source/tests/point_benchmark_chart.cpp'
    cpp.parent.mkdir(parents=True,exist_ok=True)
    original, patch = ROOT/'tests/point_benchmark_chart.cpp', ROOT/'tests/point_dropout_continuity.patch'
    reference_file, qt_file = source/'reference/rows.json', source/'qt/rows.json'
    original_rows, qt = matrix(json.loads(reference_file.read_text())), matrix(json.loads(qt_file.read_text()))
    prior_file, ramp_file = source/'encoded-refinement-captures.json', args.ramp_study/'shoulder-captures.json'
    prior, ramp_record = json.loads(prior_file.read_text()), json.loads(ramp_file.read_text())
    assert ramp_record['source_report_sha256'] == sha(prior_file)
    assert ramp_record['reference_rows_sha256'] == sha(reference_file) and ramp_record['qt_rows_sha256'] == sha(qt_file)
    assert ramp_record['checker_sha256'] == sha(ROOT/'tests/coverage_shoulder_test.py')
    libraries = {k:build/k/'.libs/libfreetype.so' for k in ('stock','nearest','nearest-owners')}
    assert all(sha(libraries[k]) == prior['libraries'][k] for k in ('stock','nearest'))
    fonts = {r['font_path']:font_weight(Path(r['font_path'])) for r in original_rows.values()}
    protected = [original,patch,reference_file,qt_file,prior_file,ramp_file,args.label_font,build/'probe',
                 ROOT/'tests/freetype_mask_probe.cpp',ROOT/'tests/freetype_curve_trace.h',ROOT/'tests/freetype_curve_trace.patch',
                 ROOT/'tests/curve_contrast_test.py',ROOT/'tests/encoded_refinement_test.py',ROOT/'tests/coverage_shoulder_test.py']
    protected += list(libraries.values())+[Path(p) for p in fonts]
    protected += [source/'qt'/f'{r["id"]}-{p}.png' for r in qt.values() for p in ('light','dark')]
    before = {str(p):sha(p) for p in protected}
    shutil.copyfile(original,cpp)
    run(['patch','--batch','--fuzz=0','-p1','-i',patch],cwd=work/'source')
    flags = shlex.split(run(['pkg-config','--cflags','--libs','Qt6Gui','freetype2']).stdout)
    binary = work/'chart'
    run(['c++','-std=c++17','-fPIC','-include','algorithm',cpp,*flags,'-o',binary])
    env = {k:v for k,v in original_env.items() if not k.startswith('FONTREAL_') and k not in ('LD_PRELOAD','LD_LIBRARY_PATH','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env.update(FONTREAL_RENDERING='0',QT_QPA_PLATFORM='offscreen',QT_FONT_DPI='96',FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1',FT2_DEBUG='any:0')
    run([binary,'candidate',qt_file,output/'native'],env=dict(env,LD_LIBRARY_PATH=str(libraries['nearest'].parent)))
    rows = matrix(json.loads((output/'native/rows.json').read_text()))
    controls = list(qt.values())
    for bad in (controls[:-1]+[controls[0]],controls[:-1],[dict(controls[0],point_size=8.5)]+controls[1:],
                [{k:v for k,v in controls[0].items() if k != 'point_size'}]+controls[1:]):
        try:
            matrix(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError('invalid matrix accepted')
    self_check()
    ramp, independent_ramp, identity = coverage_table('ramp'), expected_table('ramp'), list(range(256))
    assert ramp == ramp_record['tables']['ramp'] == independent_ramp
    sample = dict(width=1,height=1,x=0,y=0,mask='40')
    for floor,expected in ((192,239),(217,249)):
        selected = guard(sample,b'\1',ramp,floor)
        assert compose([selected,selected],1,160,table=identity).tobytes()[0] == expected
        assert max(compose([sample,sample],1,160,table=ramp).tobytes()[0],floor) == floor
        assert guard(sample,b'\0',ramp,floor)['mask'] == '40'
        assert guard(dict(sample,mask='ff'),b'\1',ramp,floor)['mask'] == 'ff'
    oracle = Oracle(libraries['stock'])
    images, changes, profiles, native_checks, selected_total = {}, [], [], 0, 0
    target_support = None
    for key,row in rows.items():
        old, stock = original_rows[key], qt[key]
        assert row['weight'] == fonts[row['font_path']] and row['font_sha256'] == before[row['font_path']]
        assert len(row['runs']) == len(row['glyphs']) == len(TEXT) == 33
        for field in ('id','label','point_size','font_point_size','base_px','font_sha256','weight','cutoff','height','runs','logical_dpi','scale'):
            assert row[field] == old[field] == stock[field]
        assert row['logical_dpi'] == 96 and row['scale'] == 1
        actual_support, expected_support = [], []
        for index,(glyph,original_glyph) in enumerate(zip(row['glyphs'],old['glyphs'])):
            assert {k:v for k,v in glyph.items() if k != 'dropouts'} == original_glyph
            assert glyph['glyph'] == row['runs'][index]['glyph']
            expected_gray = oracle.raster(original_glyph['loaded'])
            assert all(expected_gray[k] == glyph[k] for k in ('mask','left','top','width','height'))
            native_checks += 1
            record = glyph['dropouts']
            assert all(record[k] == glyph[k] for k in ('width','height','left','top'))
            pair = []
            for ignore,name in ((False,'with'),(True,'ignored')):
                expected = mono_raster(oracle,original_glyph['loaded'],ignore)
                assert all(expected[k] == record[k] for k in ('width','height','left','top'))
                assert expected['mask'] == record[name]
                pair.append(bits(bytes.fromhex(expected['mask']),expected['width'],expected['height']))
                native_checks += 1
            assert all(not b or a for a,b in zip(*pair))
            predicted = bytes(bool(a and not b) for a,b in zip(*pair))
            actual = support_pixels(record)
            assert actual == predicted
            actual_support.append(actual);expected_support.append(predicted)
            selected_total += sum(actual)
            if key == ('Noto Serif Regular',11) and TEXT[index] == '2':
                assert glyph['glyph'] == 21
                target_support = [(y-glyph['top'],x+glyph['left']) for y in range(glyph['height']) for x in range(glyph['width']) if actual[y*glyph['width']+x]]
                assert target_support == [(-5,4),(-4,3),(-3,2),(-2,1)]
        assert compose(old['glyphs'],old['height'],old['cutoff']).tobytes() == (output/'native'/f'{old["id"]}-mask.bin').read_bytes()
        light = row['weight'] < 400
        table = identity if light else ramp
        for mode,floor in (('reference',0),('guard192',192),('guard217',217)):
            treated = [guard(g,s,table,0 if light else floor) for g,s in zip(row['glyphs'],actual_support)]
            expected_glyphs = []
            counts = []
            for glyph,support in zip(old['glyphs'],expected_support):
                baseline = bytes.fromhex(glyph['mask']) if light else bytes(independent_ramp[a] for a in bytes.fromhex(glyph['mask']))
                expected = bytes(max(a,floor) if on and not light else a for a,on in zip(baseline,support))
                expected_glyphs.append(dict(glyph,mask=expected.hex()))
                counts.append(sum(a != b for a,b in zip(baseline,expected)))
                assert all(a == b for a,b,on in zip(baseline,expected,support) if not on)
            alpha = compose(treated,row['height'],160,table=identity)
            predicted = scalar_mask(expected_glyphs,row['height'],identity)
            assert alpha.tobytes() == predicted
            if mode == 'reference':
                assert predicted == compose(old['glyphs'],row['height'],160,table=table).tobytes()
            else:
                changes.append(dict(face=key[0],point=key[1],mode=mode,treated_changed=counts))
            for palette in ('light','dark'):
                image = alpha.point(identity if palette == 'dark' else list(range(255,-1,-1))).convert('RGB')
                assert image.tobytes() == bytes(v for a in predicted for v in ((a if palette == 'dark' else 255-a),)*3)
                if light and floor:
                    assert image.tobytes() == images['reference',key,palette].tobytes()
                images[mode,key,palette] = image
            detail = {}
            for char in '28vVW':
                at = TEXT.index(char);glyph = old['glyphs'][at]
                levels = range(-glyph['top'],-glyph['top']+glyph['height'])
                raw_rows = middle_rows(glyph,levels,160)
                treated_rows = middle_rows(expected_glyphs[at],levels,160)
                for raw,treatment in zip(raw_rows,treated_rows):
                    raw['treated'] = treatment['raw']
                    raw['horizontal_coverage_pixels'] = sum(raw['raw'])/255
                detail[char] = raw_rows
            profiles.append(dict(face=key[0],point=key[1],mode=mode,regions=detail))
        for palette in ('light','dark'):
            images['qt',key,palette] = Image.open(source/'qt'/f'{stock["id"]}-{palette}.png').convert('RGB')
    oracle.close()
    assert native_checks == 16929 and target_support
    observations = ownership(build,output,rows,env)
    label = ImageFont.truetype(str(args.label_font),13)
    outputs = []
    for palette in ('light','dark'):
        cases = [(face,p) for p in (8,11) for face in ('Noto Serif Regular','Noto Sans Regular','Noto Serif Italic','Lato Light')]
        sheets = [('dropout-preview',cases,320)]
        for face in ('Noto Serif Regular','Noto Sans Regular','Lato Light'):
            sheets.append(('dropout-'+face.lower().replace(' ','-')+'-8-16pt',[(face,p) for p in range(8,17)],520))
        for name,cases,width in sheets:
            path = output/f'{name}-{palette}.png'
            export(cases,images,qt,path,label,palette,width)
            outputs.append(dict(file=path.name,sha256=sha(path)))
    assert before == {str(p):sha(p) for p in protected} and original_env == dict(os.environ)
    report = dict(point_sizes=list(range(8,17)),conditions=prior['conditions'],images=outputs,profiles=profiles,changes=changes,
                  native_rasters_checked=native_checks,selected_pixels_including_repeated_occurrences=selected_total,
                  target_support=target_support,ownership=observations,flags=dict(enabled=0,ignored=8,stubs=False),floors=[192,217],
                  source_report_sha256=sha(prior_file),ramp_report_sha256=sha(ramp_file),checker_sha256=sha(Path(__file__)),
                  source_sha256=sha(original),patch_sha256=sha(patch),private_source_sha256=sha(cpp),libraries={k:sha(v) for k,v in libraries.items()},
                  limits=['Native dropout guidance with fixed alpha floors; no physical minimum-width guarantee','Light faces bypass guards; other diagonal dropouts can also change','No installed preset change or real-application qualification'])
    (output/'dropout-captures.json').write_text(json.dumps(report,separators=(',',':'))+'\n')
    print(f'PASS 171 integer conditions; {native_checks} native rasters; independent guarded final RGB; {len(outputs)} reopened comparisons')
    print('Target native dropout support:',target_support)


if __name__ == '__main__':
    main()
