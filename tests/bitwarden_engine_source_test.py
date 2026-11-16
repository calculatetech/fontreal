#!/usr/bin/env python3
"""Check exact Chromium 142 patch contexts and explicit engine target selection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))


def load():
    spec=importlib.util.spec_from_file_location('selected_builder',ROOT/'tools/build-electron-selected.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    return builder


def additions(path):
    return [line for line in path.read_text().splitlines() if line.startswith('+') and not line.startswith('+++')]


def main():
    teams=load();teams.configure('teams')
    assert teams.c1.PINS['electron']=='44.9.0' and teams.UPSTREAM['electron']=='44.9.1'
    assert teams.PRODUCER.name=='build-electron.py' and teams.SKIA_PATCH.name=='skia-747cf654-fontreal-selected.patch'
    selected=load();selected.configure('bitwarden');producer=selected.c1
    assert producer.PINS['electron']=='39.8.5' and selected.UPSTREAM['electron']=='39.8.5'
    assert producer.PINS['node_base']=='b4acf0c9393e4b31c4937564f059c672967161d8'
    assert 'override_electron_version="39.8.5"' in producer.GN_ARGS
    assert selected.WORK==producer.WORK and selected.WORK.is_relative_to((ROOT/'build').resolve())
    frozen=subprocess.check_output(['git','show','46b1bf0:tools/build-electron.py'],cwd=ROOT)
    assert (ROOT/'tools/build-electron.py').read_bytes()==frozen
    source=(producer.WORK/'port-checks').resolve();source.mkdir(parents=True,exist_ok=True)
    skia='https://raw.githubusercontent.com/google/skia/'+producer.PINS['skia']+'/'
    chromium='https://raw.githubusercontent.com/chromium/chromium/'+producer.PINS['chromium']+'/'
    inputs={
        'src/core/SkScalerContext.cpp':(skia+'src/core/SkScalerContext.cpp',producer.BASE_FILES['src/core/SkScalerContext.cpp']),
        'src/core/SkScalerContext.h':(skia+'src/core/SkScalerContext.h','ba0a0c15818b41828dbc6dac79a89a7881ead0621326f581d7b756bdf80b5054'),
        'src/ports/SkTypeface_fontations.cpp':(skia+'src/ports/SkTypeface_fontations.cpp',producer.BASE_FILES['src/ports/SkTypeface_fontations.cpp']),
        'BUILD.gn':(chromium+'skia/BUILD.gn','8ebb10ec6558316f7430f0265303f043c7edace79da265a7c43271758d1c7ec4'),
    }
    for name,(url,digest) in inputs.items():
        path=source/'pristine'/name;path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(urllib.request.urlopen(url).read())
        assert producer.sha(path)==digest,name
    prepared=producer.WORK/('electron-'+producer.PINS['electron'])/'src'
    if (prepared.parent/'.fontreal-source.json').is_file():
        for name,(_,digest) in inputs.items():
            path=prepared/'skia/BUILD.gn' if name=='BUILD.gn' else prepared/'third_party/skia'/name
            assert producer.sha(path)==digest,name
    output=(ROOT/'results/bitwarden-engine-source').resolve();output.mkdir(parents=True,exist_ok=True)
    roles=(('selected',selected.SKIA_PATCH,teams.SKIA_PATCH),('trace',producer.PATCH,teams.c1.PATCH),('gn',selected.GN_PATCH,teams.GN_PATCH))
    for role,patch,previous in roles:
        assert additions(patch)==additions(previous),role
        with tempfile.TemporaryDirectory(prefix=role+'-',dir=source) as folder:
            view=Path(folder)
            for name in inputs:
                if (role=='gn')!=(name=='BUILD.gn'):continue
                destination=view/name;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source/'pristine'/name,destination)
            result=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',patch],cwd=view,text=True,capture_output=True,check=True)
            assert 'offset' not in result.stdout and 'fuzz' not in result.stdout,role
    result=dict(passed=True,sourceInputs={name:digest for name,(_,digest) in inputs.items()},
                patch_sha256={role:producer.sha(patch) for role,patch,_ in roles},
                frozenProducerSha256=hashlib.sha256(frozen).hexdigest(),normalAndTraceAddedCodeUnchanged=True)
    result['preparedSourceChecked']=(prepared.parent/'.fontreal-source.json').is_file()
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS exact142 patches, unchanged hook additions and explicit target selection')


if __name__=='__main__':main()
