#!/usr/bin/env python3
"""Own reversible Teams launch hooks while preserving native Flatpak routing."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

import chromium_flatpak as target
from browser import desktop_arg

ROOT=Path(__file__).resolve().parents[1]
APPLICATION='com.github.IsmaelMartinez.teams_for_linux'
NATIVE='/usr/bin/flatpak'
AUTOSTART_UNIT='app-'+APPLICATION+'@autostart.service'
module=importlib.util.spec_from_file_location('delivery_builder',ROOT/'tools/build-chromium-delivery.py')
builder=importlib.util.module_from_spec(module);module.loader.exec_module(builder)


def view_options(view):
    view=Path(view)
    if not view.is_absolute() or view!=view.resolve(strict=True):raise ValueError('The application view is not canonical.')
    fd=os.open(view,os.O_PATH|os.O_NOFOLLOW|os.O_DIRECTORY|os.O_CLOEXEC)
    return ['--app-path='+str(view),'--ro-bind-fd='+str(fd),'--env=FONTREAL_ZYPAK_APP_PATH='+str(view)],fd


def paths():
    config=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
    data=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    bindir=Path.home()/'.local/bin'
    return config/'fontreal/chromium/teams.json',dict(flatpak=bindir/'flatpak',command=bindir/'teams-for-linux',
                application=bindir/APPLICATION,desktop=data/'applications'/(APPLICATION+'.desktop'),
                autostart=config/'systemd/user'/(AUTOSTART_UNIT+'.d')/'50-fontreal.conf')


def require_owned(state):
    expected=set(map(str,paths()[1].values()))
    if {entry['path'] for entry in state['hooks']}!=expected:raise ValueError('Launch-hook ownership record is not recognized.')
    for entry in state['hooks']:
        p=Path(entry['path'])
        if not p.is_file() or p.is_symlink() or target.sha(p)!=entry['sha256']:
            raise ValueError('A launch hook changed outside Fontreal. It was left untouched: '+str(p))


def load_build(path):
    path=path.resolve()
    if not path.is_relative_to(builder.WORK/'artifacts'):raise ValueError('The application build record is outside its build root.')
    record=json.loads(path.read_text())
    if record['spec']['application']!=APPLICATION:raise ValueError('This delivery owner qualifies Teams only.')
    return record


def compatibility(record,selectors=()):
    spec=record['spec']
    try:
        if builder.run([NATIVE,'info',*selectors,'--show-location',APPLICATION])!=spec['location']:return 'application deployment changed'
        if builder.run([NATIVE,'info',*selectors,'--show-commit',APPLICATION])!=spec['commit']:return 'application commit changed'
        if builder.run([NATIVE,'info','--show-commit',spec['runtime']])!=spec['runtime_commit']:return 'runtime commit changed'
        location=Path(spec['location'])
        if target.sha(location/'metadata')!=spec['metadata_sha256'] or target.sha(location/'files/manifest.json')!=spec['manifest_sha256']:
            return 'native package metadata changed'
        if target.sha(Path(spec['native_desktop']))!=spec['native_desktop_sha256']:return 'native desktop command changed'
        if builder.tree(location/'files')!=spec['original_files']:return 'native application code changed'
        builder.verify(record['views']['normal'])
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):return 'qualified package or payload unavailable'
    return None


def enable(build_path):
    record=load_build(build_path);reason=compatibility(record)
    if reason:raise ValueError(reason+'; no hook was changed.')
    proof_path=build_path.resolve().parent/'qualification.json'
    if not proof_path.is_file():raise ValueError('Run the actual-app qualification check before enabling this application view.')
    proof=json.loads(proof_path.read_text())
    if proof.get('passed') is not True or proof.get('build_sha256')!=target.sha(build_path):
        raise ValueError('The actual-app qualification does not identify this build.')
    state_path,hooks=paths();previous=json.loads(state_path.read_text()) if state_path.exists() else None
    if previous:require_owned(previous)
    elif any(p.exists() or p.is_symlink() for p in hooks.values()):
        raise ValueError('Existing per-user launch customizations were left untouched.')
    desktop_source=Path(record['spec']['native_desktop'])
    desktop=desktop_source.read_text()
    desktop,count=re.subn(r'^Exec=/usr/bin/flatpak(?=\s)',lambda _: 'Exec='+desktop_arg(hooks['flatpak']),desktop,flags=re.M)
    if not count or count!=len(re.findall('^Exec=',desktop,flags=re.M)):
        raise ValueError('Native desktop commands are not supported. No hook was changed.')
    launch=[sys.executable,'-B',str(Path(__file__).resolve())]
    portal=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/(APPLICATION+'.desktop')
    # Native ExecStart ':' keeps the quoted desktop path literal; systemd still needs %% for %.
    argument=json.dumps(str(portal),ensure_ascii=False).replace('%','%%')
    texts={'desktop':desktop,'autostart':'[Service]\nExecStart=\nExecStart=:/usr/bin/gio launch '+argument+'\n'}
    for name in ('flatpak','command','application'):
        args=[*launch,'flatpak','--'] if name=='flatpak' else [*launch,'run','teams','--']
        texts[name]='#!/bin/sh\nexec '+' '.join(map(shlex.quote,args))+' "$@"\n'
    for name,p in hooks.items():
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(texts[name]);p.chmod(0o644 if name in ('desktop','autostart') else 0o755)
    state=dict(application=APPLICATION,build=str(build_path.resolve()),build_sha256=target.sha(build_path),
               qualification=str(proof_path),qualification_sha256=target.sha(proof_path),tool_sha256=target.sha(Path(__file__)),
               hooks=[dict(path=str(p),sha256=target.sha(p)) for p in hooks.values()])
    state_path.parent.mkdir(parents=True,exist_ok=True);state_path.write_text(json.dumps(state,indent=2)+'\n');state_path.chmod(0o600)
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    print('Enabled Teams launch hooks. Fully quit and reopen Teams normally to use the qualified view.')


def disable():
    state_path,_=paths()
    if not state_path.exists():print('Teams delivery is disabled.');return
    state=json.loads(state_path.read_text());require_owned(state)
    for entry in state['hooks']:Path(entry['path']).unlink()
    state_path.unlink();subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    print('Disabled Teams launch hooks. Fully quit and reopen Teams for current stock rendering. Application data retained.')


def selected(arguments,state):
    # Flatpak splits at the first non-option before native option parsing.
    first=next((i for i,value in enumerate(arguments) if not value.startswith('-')),None)
    if first is None or arguments[first]!='run':return None
    index=next((i for i in range(first+1,len(arguments)) if not arguments[i].startswith('-')),None)
    if index is None or arguments[index] not in (APPLICATION,APPLICATION+'/x86_64',APPLICATION+'/x86_64/stable','app/'+APPLICATION+'/x86_64/stable'):
        return None
    selectors=[]
    for option in [*arguments[:first],*arguments[first+1:index]]:
        if option in ('--file-forwarding','--command=teams-for-linux','--arch=x86_64','--branch=stable'):continue
        if option in ('--user','--system') or option.startswith('--installation='):selectors.append(option);continue
        return None
    record=load_build(Path(state['build']))
    reason=compatibility(record,selectors)
    if target.sha(Path(state['build']))!=state['build_sha256'] or target.sha(Path(__file__))!=state['tool_sha256']:
        reason='qualified delivery input changed'
    if reason:
        print('Fontreal Teams: '+reason+'; using the current native application.',file=sys.stderr);return None
    options,fd=view_options(record['views']['normal']['directory'])
    return [*arguments[:index],*options,*arguments[index:]],fd


def run(arguments):
    state_path,_=paths();chosen=None
    if state_path.exists():
        try:
            state=json.loads(state_path.read_text());require_owned(state);chosen=selected(arguments,state)
        except (OSError,ValueError,KeyError,json.JSONDecodeError):
            print('Fontreal Teams: qualification unavailable; using the current native application.',file=sys.stderr)
    if chosen is not None:
        command,fd=chosen
        try:
            os.set_inheritable(fd,True)
            os.execv(NATIVE,[NATIVE,*command])
        except OSError:
            os.close(fd)
            print('Fontreal Teams: application view handoff failed; using the current native application.',file=sys.stderr)
    os.execv(NATIVE,[NATIVE,*arguments])


def status():
    state_path,_=paths();result=dict(enabled=state_path.exists(),application=APPLICATION)
    if state_path.exists():
        state=json.loads(state_path.read_text());require_owned(state)
        result.update(build=state['build'],compatibility=compatibility(load_build(Path(state['build']))))
    print(json.dumps(result,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('enable');p.add_argument('target',choices=('teams',));p.add_argument('--record',type=Path,required=True)
    for name in ('disable','status'):
        p=sub.add_parser(name);p.add_argument('target',choices=('teams',))
    p=sub.add_parser('run');p.add_argument('target',choices=('teams',));p.add_argument('arguments',nargs=argparse.REMAINDER)
    p=sub.add_parser('flatpak');p.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.action=='enable':enable(args.record)
    elif args.action=='disable':disable()
    elif args.action=='status':status()
    else:
        arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
        run(['run',APPLICATION,*arguments] if args.action=='run' else arguments)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise SystemExit(str(error))
