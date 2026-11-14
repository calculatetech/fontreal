#!/usr/bin/env python3
"""Compare a regular-weight coverage shoulder and continuous ramp."""
import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageFont

from browser_coverage_balance_test import font_weight
from core_contrast_test import middle_rows
from curve_contrast_test import ROOT, TEXT, Oracle, compose, sha
from encoded_refinement_test import matrix, hard_table, scalar_mask, export_sheet


def coverage_table(mode):
    values = hard_table(160)
    if mode == 'shoulder':
        values[128:160] = [192]*32
    elif mode == 'ramp':
        for a in range(97,160):
            values[a] = 3*a-192 if a < 128 else 192+((a-128)*50+16)//32
    else:
        assert mode == 'reference'
    return values


def expected_table(mode):
    if mode != 'ramp':
        return [192 if mode == 'shoulder' and 128 <= a < 160 else
                242 if 160 <= a < 242 else a for a in range(256)]
    anchors = [(0,0),(96,96),(128,192),(160,242),(242,242),(255,255)]
    values = []
    with localcontext() as context:
        context.prec = 36
        for a in range(256):
            x0,y0,x1,y1 = next((x0,y0,x1,y1) for (x0,y0),(x1,y1) in zip(anchors,anchors[1:]) if x0 <= a <= x1)
            value = Decimal(y0)+Decimal(a-x0)*Decimal(y1-y0)/Decimal(x1-x0)
            values.append(int(value.quantize(Decimal(1),rounding=ROUND_HALF_UP)))
    return values


def self_check():
    reference = coverage_table('reference')
    for mode in ('reference','shoulder','ramp'):
        table = coverage_table(mode)
        assert table == expected_table(mode)
        assert table[0] == 0 and table[-1] == 255 and all(0 <= a <= 255 for a in table)
        assert all(b >= a for a,b in zip(table,table[1:]))
        assert table[:97] == list(range(97)) and table[160:] == reference[160:]
        glyph = dict(width=1,height=1,x=0,y=0,mask='80')
        actual = compose([glyph,glyph],1,160,table=table).tobytes()
        assert actual == scalar_mask([glyph,glyph],1,expected_table(mode))
        if mode != 'reference':
            assert actual[0] == 239
            raw = compose([glyph,glyph],1,160,table=list(range(256))).tobytes()[0]
            assert table[raw] == 242
    shoulder, ramp = coverage_table('shoulder'), coverage_table('ramp')
    assert [shoulder[a] for a in (127,128,159,160)] == [127,192,192,242]
    assert [ramp[a] for a in (127,128,159,160)] == [189,192,240,242]
    assert max(b-a for a,b in zip(ramp,ramp[1:])) == 3
    assert shoulder[128]-shoulder[127] == 65 and shoulder[160]-shoulder[159] == 50


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-study',type=Path,required=True)
    parser.add_argument('--native-build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args = parser.parse_args()
    original_env = dict(os.environ)
    output = args.output.resolve()
    assert output.is_relative_to((ROOT/'results').resolve())
    output.mkdir(parents=True,exist_ok=True)
    self_check()
    source = args.source_study
    reference_file, qt_file = source/'reference/rows.json', source/'qt/rows.json'
    reference = matrix(json.loads(reference_file.read_text()))
    qt = matrix(json.loads(qt_file.read_text()))
    report_file = source/'encoded-refinement-captures.json'
    prior = json.loads(report_file.read_text())
    library = args.native_build/'stock/.libs/libfreetype.so'
    assert sha(library) == prior['libraries']['stock']
    assert sha(ROOT/'tests/point_benchmark_chart.cpp') == prior['source_sha256']
    assert sha(ROOT/'tests/encoded_refinement_test.py') == prior['checker_sha256']
    assert sha(ROOT/'tests/curve_contrast_test.py') == prior['compose_helper_sha256']
    fonts = {r['font_path']:font_weight(Path(r['font_path'])) for r in reference.values()}
    protected = [reference_file,qt_file,report_file,library,args.label_font,
                 ROOT/'tests/point_benchmark_chart.cpp',ROOT/'tests/curve_contrast_test.py',ROOT/'tests/encoded_refinement_test.py']
    protected += [Path(p) for p in fonts]
    protected += [source/'qt'/f'{r["id"]}-{palette}.png' for r in qt.values() for palette in ('light','dark')]
    protected += [source/'reference'/f'{r["id"]}-mask.bin' for r in reference.values()]
    before = {str(p):sha(p) for p in protected}
    records = {(r['label'],r['point_size']):r for r in prior['conditions']}
    assert len(prior['conditions']) == len(records) == 171 and set(records) == set(reference)
    controls = list(qt.values())
    for bad in (controls[:-1]+[controls[0]],controls[:-1],[dict(controls[0],point_size=8.5)]+controls[1:],
                [{k:v for k,v in controls[0].items() if k != 'point_size'}]+controls[1:]):
        try:
            matrix(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError('invalid matrix accepted')
    oracle = Oracle(library)
    images, profiles, changes, masks = {}, [], [], 0
    totals = {mode:{char:0 for char in '835vVWwl'} for mode in ('shoulder','ramp')}
    for key,row in reference.items():
        stock = qt[key]
        assert len(row['glyphs']) == len(row['runs']) == len(TEXT) == 33
        assert row['weight'] == fonts[row['font_path']] and row['font_sha256'] == before[row['font_path']]
        assert row['logical_dpi'] == 96 and row['scale'] == 1
        for field in ('id','label','point_size','font_point_size','font_sha256','weight','cutoff'):
            assert row[field] == stock[field] == records[key][field]
        for field in ('runs','height','base_px','logical_dpi','scale'):
            assert row[field] == stock[field]
        for index,glyph in enumerate(row['glyphs']):
            expected = oracle.raster(glyph['loaded'])
            assert all(expected[k] == glyph[k] for k in ('mask','left','top','width','height'))
            assert glyph['glyph'] == row['runs'][index]['glyph']
            assert glyph['x'] == int(row['runs'][index]['x']//1)+glyph['left']
            assert glyph['y'] == int(row['runs'][index]['y']+0.5)-glyph['top']
            masks += 1
        light = row['weight'] < 400
        baseline = list(range(256)) if light else coverage_table('reference')
        for mode in ('reference','shoulder','ramp'):
            table = list(range(256)) if light else coverage_table(mode)
            independent = list(range(256)) if fonts[row['font_path']] < 400 else expected_table(mode)
            alpha = compose(row['glyphs'],row['height'],160,table=table)
            expected_alpha = scalar_mask(row['glyphs'],row['height'],independent)
            assert alpha.tobytes() == expected_alpha,(key,mode,'actual dispatch')
            if mode == 'reference' and not light:
                assert expected_alpha == (source/'reference'/f'{row["id"]}-mask.bin').read_bytes()
            counts, gains = [], []
            for char,glyph in zip(TEXT,row['glyphs']):
                raw = bytes.fromhex(glyph['mask'])
                count = sum(table[a] != baseline[a] for a in raw)
                counts.append(count)
                gains.append(sum(table[a]-baseline[a] for a in raw))
                if mode != 'reference' and char in totals[mode]:
                    totals[mode][char] += count
            if mode != 'reference':
                changes.append(dict(face=key[0],point=key[1],mode=mode,treated_changed=counts,per_glyph_alpha_gain=gains))
            for palette in ('light','dark'):
                pixels = alpha.point(list(range(256)) if palette == 'dark' else list(range(255,-1,-1))).convert('RGB')
                expected_rgb = bytes(v for a in expected_alpha for v in ((a if palette == 'dark' else 255-a),)*3)
                assert pixels.tobytes() == expected_rgb
                if light and mode != 'reference':
                    assert pixels.tobytes() == images['reference',key,palette].tobytes()
                images[mode,key,palette] = pixels
            detail = {}
            for char in '835v':
                glyph = row['glyphs'][TEXT.index(char)]
                center = -glyph['top']+glyph['height']//2
                regions = middle_rows(glyph,(-glyph['top'],center-1,center),160)
                for region in regions:
                    region['treated'] = [table[a] for a in region['raw']]
                detail[char] = regions
            profiles.append(dict(face=key[0],point=key[1],mode=mode,regions=detail))
        for palette in ('light','dark'):
            images['qt',key,palette] = Image.open(source/'qt'/f'{stock["id"]}-{palette}.png').convert('RGB')
    oracle.close()
    assert masks == 5643
    label = ImageFont.truetype(str(args.label_font),13)
    outputs = []
    for palette in ('light','dark'):
        cases = [(face,p) for p in (8,11) for face in ('Noto Sans Regular','Noto Serif Regular','Noto Serif Italic','Lato Light')]
        sheets = [('shoulder-preview',cases,320)]
        for face in ('Noto Sans Regular','Noto Serif Italic','Lato Light'):
            sheets.append(('shoulder-'+face.lower().replace(' ','-')+'-8-16pt',[(face,p) for p in range(8,17)],520))
        for name,cases,width in sheets:
            for key in cases:
                for mode in ('reference','shoulder','ramp','qt'):
                    image = images[mode,key,palette]
                    blank = Image.new('RGB',image.size,(255,)*3 if palette == 'light' else (0,)*3)
                    box = ImageChops.difference(image,blank).getbbox()
                    assert box is None or box[2] <= width-16,(key,mode,'native strip clipped')
            path = output/f'{name}-{palette}.png'
            export_sheet(cases,('reference','shoulder','ramp','qt'),('Accepted reference','128 to 192 shoulder','Continuous ramp','Stock Qt'),images,qt,path,label,palette,width)
            outputs.append(dict(file=path.name,sha256=sha(path)))
    assert before == {str(p):sha(p) for p in protected} and original_env == dict(os.environ)
    report = dict(point_sizes=list(range(8,17)),conditions=list(records.values()),source_report_sha256=sha(report_file),
                  reference_rows_sha256=sha(reference_file),qt_rows_sha256=sha(qt_file),library_sha256=sha(library),
                  checker_sha256=sha(Path(__file__)),native_masks_checked=masks,
                  tables={mode:coverage_table(mode) for mode in ('reference','shoulder','ramp')},light_table=list(range(256)),
                  treated_changed_totals=totals,changes=changes,profiles=profiles,images=outputs,
                  source_images=[dict(file=p.name,sha256=before[str(p)]) for p in protected if p.suffix == '.png'],
                  semantics='Per-glyph complete coverage table before alpha-over; encoded blend; all light faces raw with no floor',
                  limits=['Coverage-only diagnostics; diagonal pixels can also gain weight','No optical winner selected','No application qualification or preset change'])
    (output/'shoulder-captures.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS 171 integer conditions; {masks} native masks; Decimal/scalar final-pixel oracle; {len(outputs)} saved comparisons')
    print(json.dumps(totals))


if __name__ == '__main__':
    main()
