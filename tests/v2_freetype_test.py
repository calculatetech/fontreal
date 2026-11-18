#!/usr/bin/env python3
"""Prove the ordinary private FreeType V2 adapter through public calls."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools')]
from browser_stroke_axis_test import Bitmap, Vector, Outline
from v2_coverage_test import d_reference, canonical
from pixel_references_test import reference, registered
from arial_coherence_test import independent
from selected_profile_test import expected_mask

BUILD = ROOT/'build/v2-freetype'
OUT = ROOT/'results/v2-freetype'
NORMAL = 0x8008
OUTLINE = 0x6f75746c
BITMAP = 0x62697473


class Generic(C.Structure):
    _fields_ = [('data', C.c_void_p), ('finalizer', C.c_void_p)]


class Metrics(C.Structure):
    _fields_ = [(n, C.c_long) for n in ('width', 'height', 'horiBearingX', 'horiBearingY', 'horiAdvance', 'vertBearingX', 'vertBearingY', 'vertAdvance')]


class Slot(C.Structure):
    _fields_ = [('library', C.c_void_p), ('face', C.c_void_p), ('next', C.c_void_p), ('glyph_index', C.c_uint),
                ('generic', Generic), ('metrics', Metrics), ('linearHoriAdvance', C.c_long),
                ('linearVertAdvance', C.c_long), ('advance', Vector), ('format', C.c_uint), ('bitmap', Bitmap),
                ('bitmap_left', C.c_int), ('bitmap_top', C.c_int), ('outline', Outline)]


class Face(C.Structure):
    _fields_ = [(n, C.c_long) for n in ('num_faces', 'face_index', 'face_flags', 'style_flags', 'num_glyphs')] + [
        ('family_name', C.c_void_p), ('style_name', C.c_void_p), ('num_fixed_sizes', C.c_int), ('available_sizes', C.c_void_p),
        ('num_charmaps', C.c_int), ('charmaps', C.c_void_p), ('generic', Generic), ('bbox', C.c_long*4),
        ('units_per_EM', C.c_ushort)] + [(n, C.c_short) for n in ('ascender', 'descender', 'height', 'max_advance_width', 'max_advance_height', 'underline_position', 'underline_thickness')] + [('glyph', C.POINTER(Slot))]


class Matrix(C.Structure):
    _fields_ = [(n, C.c_long) for n in ('xx', 'xy', 'yx', 'yy')]


class Parameter(C.Structure):
    _fields_ = [('tag', C.c_ulong), ('data', C.c_void_p)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment(pref=None, active=True, scope=None, contrast='weighted'):
    for k in list(os.environ):
        if k.startswith('FONTREAL_') or k in ('FREETYPE_PROPERTIES', 'FT2_DEBUG'):
            del os.environ[k]
    if pref is not None: os.environ['FONTREAL_PROFILE'] = pref
    if active: os.environ['FONTREAL_FT_RENDERING'] = '1'
    if scope is not None: os.environ['FONTREAL_FT_EXECUTABLE'] = scope
    os.environ['FONTREAL_FT_CONTRAST'] = contrast


class Library:
    def __init__(self, path, helper):
        self.api = C.CDLL(str(path), mode=os.RTLD_LOCAL | os.RTLD_DEEPBIND)
        self.helper = helper
        signatures = {
            'FT_Init_FreeType': ([C.POINTER(C.c_void_p)], C.c_int),
            'FT_New_Face': ([C.c_void_p, C.c_char_p, C.c_long, C.POINTER(C.POINTER(Face))], C.c_int),
            'FT_Set_Pixel_Sizes': ([C.POINTER(Face), C.c_uint, C.c_uint], C.c_int),
            'FT_Select_Size': ([C.POINTER(Face), C.c_int], C.c_int),
            'FT_Get_Char_Index': ([C.POINTER(Face), C.c_ulong], C.c_uint),
            'FT_Load_Glyph': ([C.POINTER(Face), C.c_uint, C.c_int32], C.c_int),
            'FT_Load_Char': ([C.POINTER(Face), C.c_ulong, C.c_int32], C.c_int),
            'FT_Render_Glyph': ([C.POINTER(Slot), C.c_int], C.c_int),
            'FT_Property_Get': ([C.c_void_p, C.c_char_p, C.c_char_p, C.c_void_p], C.c_int),
            'FT_Property_Set': ([C.c_void_p, C.c_char_p, C.c_char_p, C.c_void_p], C.c_int),
            'FT_Get_Module': ([C.c_void_p, C.c_char_p], C.c_void_p),
            'FT_Remove_Module': ([C.c_void_p, C.c_void_p], C.c_int),
            'FT_Set_Transform': ([C.POINTER(Face), C.POINTER(Matrix), C.POINTER(Vector)], None),
            'FT_Outline_Get_Bitmap': ([C.c_void_p, C.POINTER(Outline), C.POINTER(Bitmap)], C.c_int),
            'FT_Face_Properties': ([C.POINTER(Face), C.c_uint, C.c_void_p], C.c_int),
            'FT_Set_Var_Design_Coordinates': ([C.POINTER(Face), C.c_uint, C.POINTER(C.c_long)], C.c_int),
            'FT_Done_Face': ([C.POINTER(Face)], C.c_int),
            'FT_Done_FreeType': ([C.c_void_p], C.c_int)}
        for name, (args, result) in signatures.items():
            f = getattr(self.api, name); f.argtypes = args; f.restype = result
        self.library = C.c_void_p(); assert not self.api.FT_Init_FreeType(C.byref(self.library))
        self.faces = []
        assert self.property('interpreter-version',module='truetype',kind=C.c_uint)==(0,40)

    def property(self, name, value=None, module='autofitter', kind=C.c_ubyte):
        v = kind(0 if value is None else value)
        fn = self.api.FT_Property_Get if value is None else self.api.FT_Property_Set
        status = fn(self.library, module.encode(), name.encode(), C.byref(v))
        return status, v.value

    def face(self, path, size=13):
        face = C.POINTER(Face)(); assert not self.api.FT_New_Face(self.library, os.fsencode(path), 0, C.byref(face)), path
        self.faces.append(face)
        error=self.api.FT_Set_Pixel_Sizes(face, 0, size)
        if error and face.contents.num_fixed_sizes: error=self.api.FT_Select_Size(face,0)
        assert not error,(path,error)
        return face

    def close(self):
        for face in self.faces: assert not self.api.FT_Done_Face(face)
        assert not self.api.FT_Done_FreeType(self.library)


def snapshot(face, helper):
    s = face.contents.glyph.contents; b = s.bitmap; o = s.outline
    pixels = b''.join(C.string_at(C.cast(b.buffer, C.c_void_p).value+y*b.pitch, abs(b.pitch)) for y in range(b.rows)) if b.buffer else b''
    return dict(format=s.format, flags=helper.fontreal_test_load_flags(face.contents.glyph),
                bitmap=dict(width=b.width, rows=b.rows, pitch=b.pitch, mode=b.pixel_mode, grays=b.num_grays, pixels=pixels.hex()),
                left=s.bitmap_left, top=s.bitmap_top, metrics=[getattr(s.metrics,n) for n,_ in Metrics._fields_],
                advance=[s.advance.x,s.advance.y], linear=[s.linearHoriAdvance,s.linearVertAdvance],
                outline=dict(points=[[o.points[i].x,o.points[i].y] for i in range(o.n_points)],
                             tags=[ord(o.tags[i]) for i in range(o.n_points)], contours=list(o.contours[:o.n_contours]), flags=o.flags))


def mask(s):
    b=s['bitmap']; values=bytes.fromhex(b['pixels']); pitch=abs(b['pitch'])
    return dict(left=s['left'],top=-s['top'],width=b['width'],height=b['rows'],pixels=[values[y*pitch+x] for y in range(b['rows']) for x in range(b['width'])])


def high_raster(lib, outline, raw, flags=None, scale=4):
    w,h=4*(raw['width']+6),4*(raw['height']+6)
    bottom=-raw['top']-raw['height']-3; left=raw['left']-3
    points=(Vector*len(outline['points']))(*(Vector(x*scale-left*256,y*scale-bottom*256) for x,y in outline['points']))
    tags=(C.c_ubyte*len(points))(*outline['tags']); contours=(C.c_short*len(outline['contours']))(*outline['contours'])
    o=Outline(len(contours),len(points),points,C.cast(tags,C.POINTER(C.c_char)),contours,outline['flags'] if flags is None else flags)
    bits=(C.c_ubyte*(w*h))(); bitmap=Bitmap(h,w,w,bits,256,2,0,None)
    assert not lib.api.FT_Outline_Get_Bitmap(lib.library,C.byref(o),C.byref(bitmap))
    return dict(left=left*4,top=(raw['top']-3)*4,width=w,height=h,pixels=list(bits))


def expected(raw, high, pref):
    if not raw['width'] or not raw['height']: return raw['pixels']
    d=d_reference(raw); frame=dict(left=raw['left']-2,top=raw['top']-2,width=raw['width']+4,height=raw['height']+4)
    padded=registered({**raw,'pixels':d},frame); values,audit=reference(high,padded,frame['width'])
    if pref=='o': result=values['O']
    else:
        sums=[dict(phase=list(p),values=v) for p,v in sorted(audit['sums'].items())]
        result=independent(padded,values['L'],values['S'],sums,audit['axes'],audit['primary'],audit['components'],frame['width'])[0]['K3']
    return [result[(y+2)*frame['width']+x+2] for y in range(raw['height']) for x in range(raw['width'])]


def transform(lib, face, kind):
    if not kind: return
    matrix={'quarter':(65536,0,0,65536),'slant':(65536,17000,0,65536),'singular-x':(0,0,0,65536),'singular-y':(65536,0,0,0)}[kind]
    lib.api.FT_Set_Transform(face,C.byref(Matrix(*matrix)),C.byref(Vector(0,0) if kind.startswith('singular') else Vector(17,29)))


def outline_fixture(face, kind):
    # Explicit outline fixtures test raster flags, not font/provider compatibility.
    s=face.contents.glyph.contents
    shapes={'overlap':([(0,0),(330,0),(330,570),(0,570),(130,70),(510,70),(510,460),(130,460)],0x40),
            'fill':([(0,0),(520,0),(520,580),(0,580),(130,120),(390,120),(390,450),(130,450)],2)}
    points,flags=shapes[kind]; assert s.outline.n_points>=8 and s.outline.n_contours>=2
    for i,(x,y) in enumerate(points): s.outline.points[i]=Vector(x+13,y+21);s.outline.tags[i]=bytes([1])
    s.outline.n_points=8;s.outline.n_contours=2;s.outline.contours[0]=3;s.outline.contours[1]=7;s.outline.flags=flags


def observe(path, raw, high, pref):
    data=path.read_bytes(); line,values=data.split(b'\n',1)
    assert list(map(int,line.split()))==[1 if pref=='o' else 2,raw['width'],raw['height'],raw['left'],-raw['top'],high['width'],high['height']]
    assert list(values)==raw['pixels']+high['pixels']


def compare(lib, stock, face, oracle_face, helper, pref, code='n', flags=0, immediate=False,
            fixture=None, caller_phase=False, bypass=False, tag=''):
    observation=BUILD/'same-call.bin'; observation.unlink(missing_ok=True); os.environ['FONTREAL_V2_OBSERVATION']=str(observation)
    native_flags=flags if bypass else (flags & ~((15<<16)|0x1000|0x20))|NORMAL
    # Immediate calls cannot receive a caller outline edit.
    api='FT_Load_Char' if immediate else 'FT_Load_Glyph'
    arg=ord(code) if immediate else lib.api.FT_Get_Char_Index(face,ord(code))
    arg_stock=ord(code) if immediate else stock.api.FT_Get_Char_Index(oracle_face,ord(code))
    a=getattr(lib.api,api)(face,arg,flags|(4 if immediate else 0))
    b=getattr(stock.api,api)(oracle_face,arg_stock,native_flags)
    assert a==b,(tag,'load',a,b)
    if a:return dict(tag=tag,status=a)
    if fixture:
        outline_fixture(face,fixture);outline_fixture(oracle_face,fixture)
    unmodified=snapshot(oracle_face,helper)
    if caller_phase:
        for f in (face,oracle_face):
            o=f.contents.glyph.contents.outline
            for i in range(o.n_points):o.points[i].x+=23;o.points[i].y-=11
    before=snapshot(face,helper); source=snapshot(oracle_face,helper)
    if not immediate:
        assert before==source,(tag,'load source',before,source)
        a=lib.api.FT_Render_Glyph(face.contents.glyph,0)
    b=stock.api.FT_Render_Glyph(oracle_face.contents.glyph,0)
    assert a==b,(tag,'render status',a,b)
    actual=snapshot(face,helper); raw_snapshot=snapshot(oracle_face,helper)
    if immediate: raw_snapshot['flags'] |= 4
    if bypass:
        assert actual==raw_snapshot,(tag,'bypass')
        return dict(tag=tag,raw=canonical(raw_snapshot),source=canonical(source),output=canonical(actual),
                    pixels=actual['bitmap']['pixels'],width=actual['bitmap']['width'],height=actual['bitmap']['rows'],twice_diff=False,native_flags_diff=False)
    raw=mask(raw_snapshot)
    if bypass: assert actual==raw_snapshot,(tag,'bypass')
    else:
        high=high_raster(stock,source['outline'],raw)
        want=expected(raw,high,pref)
        if caller_phase:
            wrong=high_raster(stock,unmodified['outline'],raw)
            assert wrong['pixels']!=high['pixels'],(tag,'stale support witness')
            assert expected(raw,wrong,pref)!=want,(tag,'stale terminal witness')
        assert mask(actual)['pixels']==want,(tag,'pixels',mask(actual)['pixels'],want)
        assert {k:v for k,v in actual.items() if k!='bitmap'}=={k:v for k,v in raw_snapshot.items() if k!='bitmap'},(tag,'metadata')
        assert {k:v for k,v in actual['bitmap'].items() if k!='pixels'}=={k:v for k,v in raw_snapshot['bitmap'].items() if k!='pixels'}
        assert actual['outline']==source['outline'],(tag,'source preservation')
        if observation.exists():observe(observation,raw,high,pref)
        elif 'FONTREAL_V2_TEST_OBSERVE' in lib.cflags and raw['width'] and raw['height']:raise AssertionError((tag,'missing observer'))
    repeated=lib.api.FT_Render_Glyph(face.contents.glyph,0)
    assert repeated==a and snapshot(face,helper)==actual,(tag,'repeat')
    flag_diff=False
    if fixture:
        alternate=stock.face('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf')
        assert not stock.api.FT_Load_Char(alternate,ord('8'),NORMAL)
        outline_fixture(alternate,fixture);alternate.contents.glyph.contents.outline.flags=0
        assert not stock.api.FT_Render_Glyph(alternate.contents.glyph,0)
        flag_diff=mask(snapshot(alternate,helper))!=raw
    return dict(tag=tag,raw=canonical(raw_snapshot),source=canonical(source),output=canonical(actual),
                high=canonical(high),
                pixels=mask(actual)['pixels'],width=raw['width'],height=raw['height'],
                twice_diff=bool(raw['width'] and raw['height'] and expected({**raw,'pixels':mask(actual)['pixels']},high,pref)!=mask(actual)['pixels']) if not bypass else False,
                native_flags_diff=flag_diff,
                high_flags_diff=high_raster(stock,source['outline'],raw,0)['pixels']!=high['pixels'] if fixture else False)


def helper(record):
    source=Path(record).parent/'candidate-source'; target=BUILD/'private-state.so'
    command=['cc','-shared','-fPIC','-DFT2_BUILD_LIBRARY','-I'+str(source/'include'),str(ROOT/'tests/v2_freetype_probe.c'),'-o',str(target)]
    subprocess.run(command,check=True)
    dll=C.CDLL(str(target));dll.fontreal_test_darkening.argtypes=[C.POINTER(Face)];dll.fontreal_test_darkening.restype=C.c_int
    dll.fontreal_test_load_flags.argtypes=[C.POINTER(Slot)];dll.fontreal_test_load_flags.restype=C.c_long
    return dll


def plain(lib, stock, face, sf, h, code='n', flags=0, tag=''):
    snapshots=[]
    for immediate in (False,True):
        a=lib.api.FT_Load_Char(face,ord(code),flags|(4 if immediate else 0))
        b=stock.api.FT_Load_Char(sf,ord(code),flags|(4 if immediate else 0))
        assert a==b,(tag,'load status',a,b)
        assert snapshot(face,h)==snapshot(sf,h),(tag,'loaded')
        if not a and not immediate:
            a=lib.api.FT_Render_Glyph(face.contents.glyph,0)
            b=stock.api.FT_Render_Glyph(sf.contents.glyph,0)
            assert a==b,(tag,'render status',a,b)
            assert snapshot(face,h)==snapshot(sf,h),(tag,'rendered')
        snapshots.append(dict(status=a,snapshot=snapshot(face,h)))
    return dict(tag=tag,results=snapshots)


def face_darkening(lib, face, disabled):
    value=C.c_ubyte(not disabled)
    p=Parameter(int.from_bytes(b'dark','big'),C.cast(C.byref(value),C.c_void_p))
    assert not lib.api.FT_Face_Properties(face,1,C.byref(p))


def selection_checks(rec, observed, h, fonts):
    rows=[]; candidate=rec['libraries']['candidate']['library']; provider=rec['libraries']['stock']['library']
    libc=C.CDLL(None);libc.getauxval.argtypes=[C.c_ulong];libc.getauxval.restype=C.c_char_p
    executable=os.fsdecode(libc.getauxval(31))
    # Both entry paths preserve stock bytes when a preference has no authority.
    for pref in (None,'invalid','o','k3'):
        environment(pref,False)
        lib=Library(candidate,h);stock=Library(provider,h)
        rows.append(plain(lib,stock,lib.face(fonts['TT']),stock.face(fonts['TT']),h,tag=f'preference-only/{pref}'))
        lib.close();stock.close()
    for scope,on in ((executable,True),('/wrong:'+executable,True),(executable+':/wrong',True),
                     (executable+'-prefix',False),('/wrong',False),(executable[:-1],False)):
        environment('o',True,scope);lib=Library(candidate,h);lib.cflags='';stock=Library(provider,h)
        f,s=lib.face(fonts['TT']),stock.face(fonts['TT'])
        rows.append(compare(lib,stock,f,s,h,'o',tag=f'scope/{scope}') if on else plain(lib,stock,f,s,h,tag=f'scope/{scope}'))
        lib.close();stock.close()
    environment('o');old=Library(candidate,h);old.cflags=''
    os.environ['FONTREAL_PROFILE']='k3';new=Library(candidate,h);new.cflags='';stock=Library(provider,h)
    assert old.property('fontreal-profile-v2',kind=C.c_uint)==(0,1)
    assert new.property('fontreal-profile-v2',kind=C.c_uint)==(0,2)
    rows.append(compare(old,stock,old.face(fonts['TT']),stock.face(fonts['TT']),h,'o',tag='old-library-fixed'))
    rows.append(compare(new,stock,new.face(fonts['TT']),stock.face(fonts['TT']),h,'k3',tag='new-library-current'))
    old.close();new.close();stock.close()
    for contrast,kind in (('raw','TT'),('none','CFF')):
        environment('o',True,contrast=contrast);lib=Library(candidate,h);lib.cflags='';stock=Library(provider,h)
        rows.append(compare(lib,stock,lib.face(fonts[kind]),stock.face(fonts[kind]),h,'o',tag=f'preference-overrides/{contrast}/{kind}'))
        lib.close();stock.close()
    for pref in (None,'invalid','o','k3'):
        environment(pref,False);lib=Library(candidate,h);lib.cflags='';other=Library(candidate,h);stock=Library(provider,h)
        assert lib.property('fontreal-selected-v1')==other.property('fontreal-selected-v1')==(0,0)
        assert lib.property('fontreal-selected-v1',7)==(0,7)
        assert lib.property('fontreal-selected-v1')==(0,1) and other.property('fontreal-selected-v1')==(0,0)
        guard=(C.c_ubyte*3)(91,0,173)
        assert not lib.api.FT_Property_Get(lib.library,b'autofitter',b'fontreal-selected-v1',C.byref(guard,1))
        assert list(guard)==[91,1,173]
        f,s=lib.face(fonts['TT']),stock.face(fonts['TT'])
        if pref in ('o','k3'):rows.append(compare(lib,stock,f,s,h,pref,tag=f'bool/{pref}'))
        else:
            assert not lib.api.FT_Load_Char(f,ord('n'),0)
            assert not stock.api.FT_Load_Char(s,ord('n'),NORMAL)
            assert snapshot(f,h)==snapshot(s,h)
            assert not stock.api.FT_Render_Glyph(s.contents.glyph,0)
            raw=snapshot(s,h);want=expected_mask(bytes(mask(raw)['pixels']),raw['bitmap']['width'])
            assert not lib.api.FT_Render_Glyph(f.contents.glyph,0)
            actual=snapshot(f,h);assert mask(actual)['pixels']==list(want)
            rows.append(dict(tag=f'legacy-bool/{pref}',raw=canonical(raw),output=canonical(actual)))
        assert lib.property('fontreal-selected-v1',0)==(0,0)
        rows.append(plain(lib,stock,f,s,h,tag=f'bool-off/{pref}'))
        assert lib.property('fontreal-profile-v2',1,kind=C.c_uint)[0]!=0,'Profile getter became a setter'
        os.environ['FREETYPE_PROPERTIES']='autofitter:fontreal-selected-v1=1'
        lib.api.FT_Set_Default_Properties.argtypes=[C.c_void_p];lib.api.FT_Set_Default_Properties.restype=None
        lib.api.FT_Set_Default_Properties(lib.library)
        assert lib.property('fontreal-selected-v1')==(0,0),'String property accepted'
        lib.close();other.close();stock.close()
    for build in (rec,observed):
        environment('o');lib=Library(build['libraries']['candidate']['library'],h);lib.cflags=build['libraries']['candidate']['cflags'];stock=Library(provider,h)
        module=lib.api.FT_Get_Module(lib.library,b'autofitter');assert module
        assert not lib.api.FT_Remove_Module(lib.library,module)
        assert lib.property('fontreal-selected-v1')[0]!=0
        row=compare(lib,stock,lib.face(fonts['TT']),stock.face(fonts['TT']),h,'o',tag='remove-autofitter');rows.append(row)
        assert not stock.api.FT_Load_Char(stock.faces[-1],ord('n'),NORMAL)
        assert not stock.api.FT_Render_Glyph(stock.faces[-1].contents.glyph,0)
        raw=mask(snapshot(stock.faces[-1],h))
        assert row['pixels']!=list(expected_mask(bytes(raw['pixels']),raw['width'])),'Removal witness also matches V1'
        lib.close();stock.close()
    return rows


def cff_checks(rec, observed, h, fonts):
    rows=[]
    for build in (rec,observed):
        for pref in ('o','k3'):
            environment(pref);lib=Library(build['libraries']['candidate']['library'],h);lib.cflags=build['libraries']['candidate']['cflags'];stock=Library(rec['libraries']['stock']['library'],h)
            for library in (lib,stock):assert library.property('no-stem-darkening',0,module='cff')==(0,0)
            f,s=lib.face(fonts['CFF']),stock.face(fonts['CFF'])
            face_darkening(lib,f,False);face_darkening(stock,s,True)
            assert h.fontreal_test_darkening(f)==0 and h.fontreal_test_darkening(s)==1
            for code in ('n','8','W'):
                rows.append(compare(lib,stock,f,s,h,pref,code,tag=f'cff-driver-face-on/{pref}/{code}'))
                assert h.fontreal_test_darkening(f)==0 and lib.property('no-stem-darkening',module='cff')==(0,0)
            # The driver owns invalid-index failure while the temporary override is active.
            a=lib.api.FT_Load_Glyph(f,f.contents.num_glyphs+100,0)
            b=stock.api.FT_Load_Glyph(s,s.contents.num_glyphs+100,NORMAL)
            assert a==b and a!=0 and h.fontreal_test_darkening(f)==0
            rows.append(dict(tag=f'cff-error/{pref}',error=a,restored=h.fontreal_test_darkening(f)))
            rows.append(compare(lib,stock,f,s,h,pref,tag=f'cff-after-error/{pref}'))
            face_darkening(stock,s,False)
            rows.append(compare(lib,stock,f,s,h,pref,flags=2,bypass=True,tag=f'cff-ineligible-restored/{pref}'))
            face_darkening(stock,s,True)
            environment(pref,False)
            face_darkening(stock,s,False)
            rows.append(plain(lib,stock,f,s,h,flags=NORMAL,tag=f'cff-restored-on/{pref}'))
            on=snapshot(f,h)
            face_darkening(stock,s,True)
            assert not stock.api.FT_Load_Char(s,ord('n'),NORMAL)
            assert not stock.api.FT_Render_Glyph(s.contents.glyph,0)
            assert mask(on)['pixels']!=mask(snapshot(s,h))['pixels'],'No CFF face-darkening contrast'
            lib.close();stock.close()
    return rows


def late_activation_checks(rec, observed, h, fonts):
    rows=[]
    for build in (rec,observed):
        environment('o',False)
        lib=Library(build['libraries']['candidate']['library'],h);lib.cflags=build['libraries']['candidate']['cflags']
        stock=Library(rec['libraries']['stock']['library'],h)
        for library in (lib,stock):assert library.property('no-stem-darkening',0,module='cff')==(0,0)
        f,s=lib.face(fonts['CFF']),stock.face(fonts['CFF'])
        for library,face in ((lib,f),(stock,s)):
            face_darkening(library,face,False)
            assert not library.api.FT_Load_Char(face,ord('n'),NORMAL)
        assert snapshot(f,h)==snapshot(s,h)
        assert lib.property('fontreal-selected-v1',1)==(0,1)
        observation=BUILD/'same-call.bin';observation.unlink(missing_ok=True)
        assert not lib.api.FT_Render_Glyph(f.contents.glyph,0)
        assert not stock.api.FT_Render_Glyph(s.contents.glyph,0)
        native_on=snapshot(s,h)
        assert snapshot(f,h)==native_on,'Late activation treated an unnormalized load'
        assert not observation.exists(),'Late activation reached the V2 kernel'
        assert h.fontreal_test_darkening(f)==0
        rows.append(dict(tag='late-bool-activation-bypass',output=canonical(native_on)))
        face_darkening(stock,s,True)
        selected=compare(lib,stock,f,s,h,'o',tag='late-bool-next-eligible-load');rows.append(selected)
        assert selected['pixels']!=mask(native_on)['pixels'],'Missing late-activation source contrast'
        lib.close();stock.close()
    return rows


def bypass_checks(rec, h, fonts):
    environment('o');lib=Library(rec['libraries']['candidate']['library'],h);stock=Library(rec['libraries']['stock']['library'],h)
    rows=[]
    for path,code,flags in ((Path('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'),'😀',0x100000),
                            (Path('/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz'),'m',0),
                            (Path('/usr/share/fonts/type1/urw-base35/NimbusSans-Regular.t1'),'m',NORMAL)):
        assert path.is_file(),('Missing native exclusion fixture',path)
        rows.append(plain(lib,stock,lib.face(path),stock.face(path),h,code,flags,tag='exclusion/'+path.name))
    for kind in ('stored-target','stored-bitmap-policy','stored-auto-policy','non-outline'):
        environment('o',False)
        f,s=lib.face(fonts['TT']),stock.face(fonts['TT'])
        flags={'stored-target':NORMAL|0x20000,'stored-bitmap-policy':0x8000,'stored-auto-policy':8,'non-outline':NORMAL}[kind]
        assert not lib.api.FT_Load_Char(f,ord('n'),flags)
        assert not stock.api.FT_Load_Char(s,ord('n'),flags)
        if kind=='non-outline':
            f.contents.glyph.contents.format=0x636f6d70;s.contents.glyph.contents.format=0x636f6d70
        environment('o')
        a=lib.api.FT_Render_Glyph(f.contents.glyph,0);b=stock.api.FT_Render_Glyph(s.contents.glyph,0)
        assert a==b and snapshot(f,h)==snapshot(s,h),(kind,a,b)
        rows.append(dict(tag=kind,error=a,snapshot=snapshot(f,h)))
    lib.close();stock.close();return rows


def legacy_checks(rec, h, fonts):
    old_path=ROOT/'build/freetype-native/artifacts/62e1aa4776e4fbaaed74/build.json'
    assert old_path.is_file(),'Missing retained legacy control'
    old=json.loads(old_path.read_text());base=old_path.parent/'candidate-source/src/base'
    assert sha(old_path)=='ceeee87ff1aebfbc1a5790b45c7865688e230995505055d6dc4eda0666586aca'
    assert sha(old['libraries']['candidate']['library'])==old['libraries']['candidate']['sha256']
    assert sha(base/'fontreal_coverage.cpp')==sha(ROOT/'src/fontreal_coverage.cpp')=='125c39efdc3e1003b533add69af082b3318323d71f1e15713322deae33d7cc59'
    assert sha(base/'fontreal_coverage.h')==sha(ROOT/'src/fontreal_coverage.h')=='5ed19c2cca3ac825b18260517e6b80a26e1836dd382a4c980c05eb824ae5b80f'
    rows=[]
    for pref in (None,'invalid'):
        for contrast in ('weighted','raw','ramp217','mild','none','nearest'):
            environment(pref,True,contrast=contrast)
            lib=Library(rec['libraries']['candidate']['library'],h);control=Library(old['libraries']['candidate']['library'],h)
            for kind in ('TT','CFF'):
                rows.append(plain(lib,control,lib.face(fonts[kind]),control.face(fonts[kind]),h,tag=f'legacy/{pref}/{contrast}/{kind}'))
            lib.close();control.close()
    # Frozen scalar V1 remains an independent numerical contrast to the V2 path.
    environment(None);lib=Library(rec['libraries']['candidate']['library'],h);stock=Library(rec['libraries']['stock']['library'],h)
    f,s=lib.face(fonts['TT']),stock.face(fonts['TT'])
    assert not lib.api.FT_Load_Char(f,ord('n'),4)
    assert not stock.api.FT_Load_Char(s,ord('n'),NORMAL|4)
    raw=mask(snapshot(s,h));v1=list(expected_mask(bytes(raw['pixels']),raw['width']))
    assert mask(snapshot(f,h))['pixels']==v1
    rows.append(dict(tag='independent-v1',raw=canonical(raw),output=canonical(snapshot(f,h))))
    lib.close();stock.close();return rows


def receipt_checks(path, rec):
    original=path.read_bytes();results=[]
    try:
        for field,value in (('v2_processor',None),('v2_processor','0'*64),('v2_declaration',None),('v2_declaration','0'*64)):
            changed=json.loads(original)
            if value is None:del changed['spec'][field]
            else:changed['spec'][field]=value
            path.write_text(json.dumps(changed))
            result=subprocess.run(['python3','-B',str(ROOT/'tools/build-freetype.py')],capture_output=True,text=True)
            assert result.returncode and 'no longer matches its recorded inputs' in result.stderr,(field,result)
            results.append(dict(field=field,mutation=value,exit=result.returncode,error=result.stderr.strip()))
    finally:path.write_bytes(original)
    assert sha(path)==hashlib.sha256(original).hexdigest()
    return results


def geometry_checks(rec, h, fonts):
    environment('o');lib=Library(rec['libraries']['candidate']['library'],h);lib.cflags='';stock=Library(rec['libraries']['stock']['library'],h)
    rows=[];witnesses={'rehint':False,'top':False,'transform':False}
    for kind in ('TT','CFF'):
        f,s=lib.face(fonts[kind]),stock.face(fonts[kind])
        large=stock.face(fonts[kind],52)
        for code in ('n','o','8','W'):
            row=compare(lib,stock,f,s,h,'o',code,tag=f'geometry/{kind}/{code}');rows.append(row)
            raw=mask(snapshot(s,h));outline=snapshot(s,h)['outline'];high=high_raster(stock,outline,raw)
            assert not stock.api.FT_Load_Char(large,ord(code),NORMAL)
            rehint=high_raster(stock,snapshot(large,h)['outline'],raw,scale=1)
            wrong_top={**high,'pixels':[0]*(4*high['width'])+high['pixels'][:-4*high['width']]}
            witnesses['rehint'] |= high['pixels']!=rehint['pixels'] and expected(raw,rehint,'o')!=row['pixels']
            witnesses['top'] |= expected(raw,wrong_top,'o')!=row['pixels']
            transform(lib,f,'slant');transform(stock,s,'slant')
            changed=compare(lib,stock,f,s,h,'o',code,tag=f'geometry/{kind}/{code}/slant');rows.append(changed)
            current=mask(snapshot(s,h));wrong=high_raster(stock,outline,current)
            witnesses['transform'] |= expected(current,wrong,'o')!=changed['pixels']
            lib.api.FT_Set_Transform(f,None,None);stock.api.FT_Set_Transform(s,None,None)
    lib.close();stock.close()
    assert all(witnesses.values()),witnesses
    return dict(rows=rows,witnesses=witnesses)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--record',type=Path,required=True)
    parser.add_argument('--startup',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args();BUILD.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    rec=json.loads(args.record.read_text());h=helper(args.record)
    if args.startup:
        lib=Library(rec['libraries']['candidate']['library'],h)
        print(json.dumps(dict(profile=lib.property('fontreal-profile-v2',kind=C.c_uint),selected=lib.property('fontreal-selected-v1'))))
        lib.close();return
    numerical=ROOT/'build/v2-coverage/tested-sources.json'
    assert sha(numerical)=='d57cee29e7e972b59de57eb239ac1f90522924cf27110ad6a8bdf429a98a0f4a'
    prior=json.loads(numerical.read_text())
    for source,value in prior['sources'].items():
        if source!='docs/experiments/supersampling.md':assert sha(ROOT/source)==value,source
    for source,value in prior['opaque_sources'].items():assert sha(ROOT/source)==value,source
    assert rec['libraries']['stock']['sha256']==prior['provider']['sha256']
    for key,path in [('v2_processor','src/fontreal_v2_coverage.cpp'),('v2_declaration','src/fontreal_v2_coverage.h'),('processor','src/fontreal_coverage.cpp'),('declaration','src/fontreal_coverage.h'),('recipe','tools/build-freetype.py'),('patch','patches/freetype-2.14.2-fontreal.patch')]:assert rec['spec'][key]==sha(ROOT/path),key
    assert rec['spec']['v2_observer'] is None,'Supply the ordinary build receipt.'
    rebuilt=subprocess.check_output(['python3','-B',str(ROOT/'tools/build-freetype.py')],text=True).splitlines()[-1]
    assert Path(rebuilt).resolve()==args.record.resolve()
    observer_stdout=BUILD/'observer-build.log'
    with observer_stdout.open('w') as log:subprocess.run(['python3','-B',str(ROOT/'tools/build-freetype.py'),'--v2-observe'],stdout=log,stderr=subprocess.STDOUT,check=True)
    observed_path=Path(observer_stdout.read_text().splitlines()[-1]);observed=json.loads(observed_path.read_text())
    assert observed['spec']['v2_observer']==sha(ROOT/'tests/v2_freetype_observe.h')
    for r in (rec,observed):
        for v in r['libraries'].values():assert sha(v['library'])==v['sha256']
        root=Path(r['libraries']['candidate']['library']).parents[2]
        assert (root/'v2-coverage.o').exists() and (root/'coverage.o').exists()
        assert 'v2-coverage.o' in r['libraries']['candidate']['ldflags']
        for file in ('fontreal_coverage.cpp','fontreal_coverage.h','fontreal_v2_coverage.cpp','fontreal_v2_coverage.h'):
            assert sha(root/'candidate-source/src/base'/file)==sha(ROOT/'src'/file)
        assert (root/'FTL.TXT').is_file() and 'FreeType Team' in (root/'NOTICE').read_text()
        assert sha(root/'candidate-source/FONTREAL-LICENSE.txt')==sha(ROOT/'LICENSE')==sha(root/'FONTREAL-LICENSE.txt')
        exports=[subprocess.check_output(['nm','-D','--defined-only',v['library']],text=True) for v in r['libraries'].values()]
        assert [{tuple(x.split()[1:]) for x in e.splitlines()} for e in exports][0]==[{tuple(x.split()[1:]) for x in e.splitlines()} for e in exports][1]
    fonts={'TT':Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'),'CFF':Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf'),'VAR':Path('/usr/share/fonts/truetype/ubuntu/UbuntuSansMono[wght].ttf')}
    assert all(p.is_file() for p in fonts.values()),fonts
    rows=[]; witnesses={};startup=[]
    for pref,value in [(None,0),('',0),('O',0),('k3 ',0),('invalid',0),('o',1),('k3',2)]:
        environment(pref)
        got=json.loads(subprocess.check_output([sys.executable,'-B',__file__,'--record',str(args.record),'--startup'],text=True))
        assert got==dict(profile=[0,value],selected=[0,0]),(pref,got);startup.append([pref,got])
    environment('o',False)
    os.environ['FREETYPE_PROPERTIES']='autofitter:fontreal-selected-v1=1'
    got=json.loads(subprocess.check_output([sys.executable,'-B',__file__,'--record',str(args.record),'--startup'],text=True))
    assert got==dict(profile=[0,1],selected=[0,0]),got
    startup.append(['string-selected-rejected',got])
    for build in (rec,observed):
        for pref in ('o','k3'):
            environment(pref);lib=Library(build['libraries']['candidate']['library'],h);lib.cflags=build['libraries']['candidate']['cflags'];stock=Library(rec['libraries']['stock']['library'],h)
            assert lib.property('fontreal-selected-v1')==(0,0)
            assert lib.property('fontreal-profile-v2',kind=C.c_uint)==(0,1 if pref=='o' else 2)
            for name,font in fonts.items():
                face=lib.face(font);sf=stock.face(font)
                for code in ('n','o','8','W','i',' '):
                    for immediate in (False,True):rows.append(compare(lib,stock,face,sf,h,pref,code,immediate=immediate,tag=f'{pref}/{name}/{code}/{immediate}'))
                for size in (9,18,13):
                    assert not lib.api.FT_Set_Pixel_Sizes(face,0,size);assert not stock.api.FT_Set_Pixel_Sizes(sf,0,size)
                    for code in ('n','n','W',' ','n'):rows.append(compare(lib,stock,face,sf,h,pref,code,tag=f'{pref}/{name}/ordered/{size}/{code}'))
                if name=='VAR':
                    for weight in (200,700,400):
                        coords=(C.c_long*1)(weight<<16)
                        assert not lib.api.FT_Set_Var_Design_Coordinates(face,1,coords);assert not stock.api.FT_Set_Var_Design_Coordinates(sf,1,coords)
                        rows.append(compare(lib,stock,face,sf,h,pref,tag=f'{pref}/variation/{weight}'))
                for t in ('quarter','slant','singular-x','singular-y'):
                    transform(lib,face,t);transform(stock,sf,t)
                    row=compare(lib,stock,face,sf,h,pref,tag=f'{pref}/{name}/{t}');rows.append(row)
                    if t.startswith('singular'):
                        assert (row['width']==0)!=(row['height']==0),(t,row)
                        lib.api.FT_Set_Transform(face,None,None);stock.api.FT_Set_Transform(sf,None,None)
                        rows.append(compare(lib,stock,face,sf,h,pref,tag=f'{pref}/{name}/after-{t}'))
                lib.api.FT_Set_Transform(face,None,None);stock.api.FT_Set_Transform(sf,None,None)
                rows.append(compare(lib,stock,face,sf,h,pref,caller_phase=True,tag=f'{pref}/{name}/caller-phase'))
                if name=='TT':
                    for kind in ('overlap','fill'):
                        row=compare(lib,stock,face,sf,h,pref,'8',fixture=kind,tag=f'{pref}/{kind}');rows.append(row);witnesses[kind]=row['native_flags_diff']
                for flags in (1,2,0x400,0x100,0x400000):rows.append(compare(lib,stock,face,sf,h,pref,flags=flags,bypass=True,tag=f'{pref}/{name}/bypass/{flags}'))
                rows.append(compare(lib,stock,face,sf,h,pref,tag=f'{pref}/{name}/return'))
            lib.close();stock.close()
    assert all(witnesses.values()),witnesses
    assert any(r['twice_diff'] for r in rows),'No twice-treatment witness'
    ordinary=rows[:len(rows)//2];passive=rows[len(rows)//2:];assert ordinary==passive
    bytag={r['tag']:r for r in ordinary}
    assert any(bytag[k]['pixels']!=bytag['k3'+k[1:]]['pixels'] for k in bytag if k.startswith('o/')),'No O/K3 witness'
    selection=selection_checks(rec,observed,h,fonts)
    policy=cff_checks(rec,observed,h,fonts)
    late_activation=late_activation_checks(rec,observed,h,fonts)
    bypasses=bypass_checks(rec,h,fonts)
    legacy=legacy_checks(rec,h,fonts)
    geometry=geometry_checks(rec,h,fonts)
    receipts=receipt_checks(args.record,rec)
    scenarios={
        'S-FT1':dict(boundaries=['B-FT1'],results=len(rows),output_binding=canonical(rows)),
        'S-FT2':dict(boundaries=['B-FT2','B-FT3'],startup=startup,selection_binding=canonical(selection)),
        'S-FT3':dict(boundaries=['B-FT4'],bypass_binding=canonical(bypasses),late_activation_binding=canonical(late_activation),load_exclusions=[1,2,0x400,0x100,0x400000]),
        'S-FT4':dict(boundaries=['B-FT5'],policy_binding=canonical(policy),late_activation_binding=canonical(late_activation)),
        'S-FT5':dict(boundaries=['B-FT6'],geometry_binding=canonical(geometry),witnesses=geometry['witnesses']),
        'S-FT6':dict(boundaries=['B-FT7'],flag_witnesses=witnesses),
        'S-FT7':dict(boundaries=['B-FT8'],empty_results=[r for r in rows if not r['width'] or not r['height']]),
        'S-FT8':dict(boundaries=['B-FT9'],twice_witnesses=[r['tag'] for r in rows if r['twice_diff']]),
        'S-FT9':dict(boundaries=['B-FT9'],ordered_binding=canonical([r for r in rows if '/ordered/' in r['tag'] or '/variation/' in r['tag']])),
        'S-FT10':dict(boundaries=['B-FT3','B-FT10'],legacy_binding=canonical(legacy),scope_binding=canonical(selection)),
        'S-FT11':dict(boundaries=['B-FT11'],error_binding=canonical([r for r in policy if 'error' in r])),
        'S-FT12':dict(boundaries=['B-FT12','B-FT14'],stale_receipts=receipts,ordinary=sha(args.record),observed=sha(observed_path)),
        'B-FT13':dict(status='Deferred to SS-16; no package qualification')}
    receipt=dict(
        sources={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'patches/freetype-2.14.2-fontreal.patch',ROOT/'tools/build-freetype.py',ROOT/'tests/v2_freetype_test.py',ROOT/'tests/v2_freetype_probe.c',ROOT/'tests/v2_freetype_observe.h',ROOT/'docs/experiments/supersampling.md']},
        record=sha(args.record),observed_record=sha(observed_path),numerical_receipt=sha(numerical),
        opaque_sources=prior['opaque_sources'],
        fonts={k:dict(file=v.name,sha256=sha(v)) for k,v in fonts.items()},
        startup=startup,rows=rows,witnesses=witnesses,selection=selection,policy=policy,
        bypasses=bypasses,legacy=legacy,geometry=geometry,late_activation=late_activation,receipts=receipts,scenarios=scenarios)
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'V2 public adapter: {len(rows)} complete results; {OUT/"receipt.json"}')


if __name__=='__main__':main()
