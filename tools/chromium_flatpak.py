#!/usr/bin/env python3
"""Inspect Chromium and named Flatpak rendering owners without starting apps."""
import argparse
import configparser
import hashlib
import json
import mmap
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
TARGETS={'teams':'com.github.IsmaelMartinez.teams_for_linux',
         'bitwarden':'com.bitwarden.desktop','telegram':'org.telegram.desktop'}


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(arguments):
    return subprocess.run(list(map(str,arguments)),text=True,capture_output=True,check=True).stdout.strip()


def binary(path):
    dependencies=re.findall(r'\(NEEDED\).*?\[([^]]+)\]',run(['readelf','-d',path]))
    with path.open('rb') as stream, mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as image:
        signature=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'; at=image.find(signature)
        fuses=None
        if at>=0:
            wire=at+len(signature); version=image[wire]; count=image[wire+1]
            assert wire+2+count<=len(image),'Incomplete Electron fuse data'
            states=image[wire+2:wire+2+count].decode('ascii')
            fuses=dict(version=version,states=states,run_as_node=states[0]=='1' if version==1 and states else None)
    return dict(file=path.name,sha256=sha(path),dependencies=dependencies,electron_fuses=fuses)


def flatpak(name,application,versions):
    result=dict(target=name,application=application,status='not-installed',backend='unknown',backend_observed=False)
    if application not in versions:return result
    location=Path(run(['flatpak','info','--show-location',application]))
    metadata=configparser.ConfigParser(interpolation=None); metadata.read(location/'metadata')
    manifest_path=location/'files/manifest.json'; manifest=json.loads(manifest_path.read_text())
    command=metadata['Application']['command']; wrapper=location/'files/bin'/command
    executable=location/'files'/({'teams':'teams-for-linux/teams-for-linux',
                                  'bitwarden':'Bitwarden/bitwarden-app','telegram':'bin/Telegram'}[name])
    modules=[m for m in manifest['modules'] if isinstance(m,dict)]
    result.update(status='installed',version=versions[application]['version'],
                  runtime=metadata['Application']['runtime'],commit=run(['flatpak','info','--show-commit',application]),
                  manifest_sha256=sha(manifest_path),command=command,wrapper_sha256=sha(wrapper),
                  binary=binary(executable),launch_script=wrapper.read_text() if wrapper.read_bytes()[:2]==b'#!' else None)
    if name=='telegram':
        qt=next(m for m in modules if m['name']=='qt')
        result['qt']=dict(shared='-DBUILD_SHARED_LIBS=OFF' not in qt.get('config-opts',[]),
                          sources=[dict(url=s['url'],sha256=s.get('sha256')) for s in qt['sources'] if 'url' in s])
    result['source_modules']=[dict(name=m['name'],sources=[dict(url=s['url'],sha256=s.get('sha256'))
                                for s in m.get('sources',[]) if isinstance(s,dict) and 'url' in s]) for m in modules
                                if m['name'] in ('teams-for-linux','bitwarden-desktop','tdesktop')]
    return result


def owners():
    edge=dict(target='edge',status='not-installed',backend='unknown',backend_observed=False)
    executable=Path('/opt/microsoft/msedge/msedge')
    if executable.is_file():
        edge.update(status='installed',version=run(['dpkg-query','-W','-f=${Version}','microsoft-edge-stable']),binary=binary(executable))
    versions={}
    if shutil.which('flatpak'):
        for line in run(['flatpak','list','--app','--columns=application,version,runtime']).splitlines():
            application,version,runtime=line.split('\t'); versions[application]=dict(version=version,runtime=runtime)
    return [edge,*[flatpak(name,application,versions) for name,application in TARGETS.items()]]


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('owners',)); parser.parse_args()
    print(json.dumps(owners(),indent=2))


if __name__=='__main__':main()
