#!/usr/bin/env python3
"""Capture genuine stock Qt and selected rendering at the supplied KDE defaults."""
import json
import os
from pathlib import Path
import shlex
import subprocess

from PIL import Image
from selected_profile_test import ROOT, WORK, build, references
import browser_masks_test as masks
from bridge_font_matrix_test import sha

PUBLIC=ROOT/'docs/images/kde-selected'
ROLES=[('General','Noto Sans',10),('Fixed width','Hack',10),('Small','Noto Sans',8),
       ('Toolbar','Noto Sans',10),('Menu','Noto Sans',10),('Window title specimen','Noto Sans',10)]


def main():
    WORK.mkdir(parents=True,exist_ok=True); PUBLIC.mkdir(parents=True,exist_ok=True)
    _,record=build(); _,trace=build(True)
    binary=WORK/'kde-comparison'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets'],text=True))
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/kde_selected_comparison.cpp'),*flags,'-o',str(binary)],check=True)
    qt_stock=ROOT/'build/stem-core-study/stock-qt/usr/lib/x86_64-linux-gnu'
    qt_selected=ROOT/'build/qt-native/qt-build/lib'
    noto=Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf')
    hack=Path('/usr/share/fonts/truetype/hack/Hack-Regular.ttf')
    env={k:v for k,v in os.environ.items() if not k.startswith(('FONTREAL_','QT_')) and
         k not in ('LD_LIBRARY_PATH','LD_PRELOAD','FT2_DEBUG','FREETYPE_PROPERTIES')}
    env.update(QT_QPA_PLATFORM='offscreen',QT_FONT_DPI='96',QT_SCALE_FACTOR='1',
               QT_PLUGIN_PATH=subprocess.check_output(['qtpaths6','--query','QT_INSTALL_PLUGINS'],text=True).strip(),
               FREETYPE_PROPERTIES='cff:no-stem-darkening=1 autofitter:no-stem-darkening=1')
    captures=[]
    source_cases=[(case,arrays) for label,case,arrays in references() if label=='sizes' and
                  (case['font']['family'],case['font']['style'],case['point_size']) in
                  (('Noto Sans','Regular',10),('Hack','Regular',10),('Noto Sans','Regular',8))]
    assert len(source_cases)==3
    for palette in ('light','dark'):
        images={}
        for mode,provider,qt in (('stock',record['libraries']['stock'],qt_stock),
                                 ('selected',record['libraries']['candidate'],qt_selected),
                                 ('trace',trace['libraries']['candidate'],qt_selected)):
            library=Path(provider['library']); output=WORK/f'kde-{palette}-{mode}.png'
            selected=mode!='stock'
            child=dict(env,LD_LIBRARY_PATH=os.pathsep.join((str(library.parent),str(qt.resolve()))),
                       FONTREAL_FT_RENDERING='1' if selected else '0',FONTREAL_FT_CONTRAST='weighted',
                       FONTREAL_FT_EXECUTABLE=str(binary.resolve()),FONTREAL_RENDERING='1' if selected else '0',
                       FONTREAL_BLEND='encoded',FONTREAL_CONTRAST='none')
            with (WORK/f'kde-{palette}-{mode}.log').open('w') as log:
                subprocess.run([str(binary.resolve()),palette,'Fontreal' if selected else 'Stock Qt',str(output),str(noto),str(hack)],
                               env=child,check=True,stdout=log,stderr=log)
            maps=Path(str(output)+'.maps').read_text(); libraries={}
            for stem in ('libQt6Core.so.','libQt6Gui.so.','libQt6Widgets.so.','libfreetype.so.'):
                paths={Path(line.split()[-1]).resolve() for line in maps.splitlines() if stem in line}
                assert len(paths)==1,(mode,stem,paths); loaded=paths.pop()
                if stem=='libfreetype.so.': assert loaded==library.resolve()
                elif stem in ('libQt6Core.so.','libQt6Gui.so.'): assert loaded.parent==qt.resolve(),(mode,loaded)
                libraries[stem]=dict(file=loaded.name,sha256=sha(loaded))
            metadata=json.loads(Path(str(output)+'.json').read_text())
            assert metadata['dpi']==96 and metadata['device_pixel_ratio']==1
            assert [(r['role'],r['family'],r['point_size']) for r in metadata['roles']]==ROLES
            image=Image.open(output).convert('RGB'); assert image.size==(600,570)
            for role in metadata['roles']:
                x,y,width,height=[role[k] for k in ('x','y','width','height')]
                assert width>0 and height>0 and 0<=x<x+width<=600 and 0<=y<y+height<=570
                crop=image.crop((x,y,x+width,y+height))
                assert len(set(crop.get_flattened_data()))>4
                role['palette']=palette; role['scale']=1
                role['crop_pixels_sha256']=__import__('hashlib').sha256(crop.tobytes()).hexdigest()
            images[mode]=image
            captures.append(dict(mode=mode,palette=palette,libraries=libraries,fonts=metadata['roles'],pixels_sha256=__import__('hashlib').sha256(image.tobytes()).hexdigest()))
        assert images['trace'].tobytes()==images['selected'].tobytes()
        rasters=masks.raw_masks(WORK/f'kde-{palette}-trace.log')
        raster_checks=0
        for case,arrays in source_cases:
            family=case['font']['family'].encode().hex()
            matching=[r for r in rasters if r['family']==family and
                      abs(r['y_scale']*r['units']/65536/64-case['native_size'])<.02]
            assert matching,(family,case['point_size'])
            for raster in matching:
                glyph=arrays.get(raster['glyph'])
                if glyph is None: continue
                assert raster['mask']==glyph['selected']
                assert (raster['width'],raster['height'])==(glyph['width'],glyph['height'])
                raster_checks+=1
        assert raster_checks>30
        captures[-1]['accepted_raster_checks']=raster_checks
        assert images['stock'].crop((0,55,600,570)).tobytes()!=images['selected'].crop((0,55,600,570)).tobytes()
        sheet=Image.new('RGB',(1200,570)); sheet.paste(images['stock'],(0,0)); sheet.paste(images['selected'],(600,0))
        destination=PUBLIC/f'kde-defaults-{palette}.png'; sheet.save(destination)
        reopened=Image.open(destination).convert('RGB')
        assert reopened.crop((0,0,600,570)).tobytes()==images['stock'].tobytes()
        assert reopened.crop((600,0,1200,570)).tobytes()==images['selected'].tobytes()
        for capture in captures[-3:]:
            if capture['mode']=='trace':continue
            offset=600 if capture['mode']=='selected' else 0
            for role in capture['fonts']:
                x,y,width,height=[role[k] for k in ('x','y','width','height')]
                crop=reopened.crop((offset+x,y,offset+x+width,y+height))
                assert __import__('hashlib').sha256(crop.tobytes()).hexdigest()==role['crop_pixels_sha256']
    record=dict(profile='native normal + selected weighted stems only',logical_dpi=96,scale=1,
                roles=[dict(role=r,family=f,point_size=p) for r,f,p in ROLES],
                fonts=[dict(file=p.name,sha256=sha(p)) for p in (noto,hack)],
                captures=captures,images=[dict(file=p.name,sha256=sha(p),width=1200,height=570)
                    for p in sorted(PUBLIC.glob('*.png'))],
                scope='Real Qt Widgets and a title-font specimen. Fusion style. No KWin decoration claim.',
                probe_sha256=sha(ROOT/'tests/kde_selected_comparison.cpp'))
    (PUBLIC/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    print('PASS six KDE roles, both palettes, stock/selected and normal/trace pixel identity')


if __name__=='__main__':main()
