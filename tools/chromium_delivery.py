#!/usr/bin/env python3
"""Own reversible Teams and Bitwarden launch hooks while preserving native Flatpak routing."""
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
from browser import desktop_arg, rendering_profile

ROOT=Path(__file__).resolve().parents[1]
APPLICATION='com.github.IsmaelMartinez.teams_for_linux'
NATIVE='/usr/bin/flatpak'
module=importlib.util.spec_from_file_location('delivery_builder',ROOT/'tools/build-chromium-delivery.py')
builder=importlib.util.module_from_spec(module);module.loader.exec_module(builder)

APPS={name:application for name,application in target.TARGETS.items() if application in builder.LAYOUTS}


def view_options(view):
    view=Path(view)
    if not view.is_absolute() or view!=view.resolve(strict=True):raise ValueError('The application view is not canonical.')
    fd=os.open(view,os.O_PATH|os.O_NOFOLLOW|os.O_DIRECTORY|os.O_CLOEXEC)
    return ['--app-path='+str(view),'--ro-bind-fd='+str(fd),'--env=FONTREAL_ZYPAK_APP_PATH='+str(view)],fd


def paths(name='teams'):
    application=APPS[name];command=builder.LAYOUTS[application][2]
    config=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
    data=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    bindir=Path.home()/'.local/bin'
    return config/'fontreal/chromium/apps.json',dict(flatpak=bindir/'flatpak',command=bindir/command,
                application=bindir/application,desktop=data/'applications'/(application+'.desktop'),
                autostart=config/'systemd/user'/('app-'+application+'@autostart.service.d')/'50-fontreal.conf')


def hook_paths(apps):
    return {str(p):p for name in apps for p in paths(name)[1].values()}


def read_state():
    state_path,_=paths();legacy=state_path.with_name('teams.json')
    if state_path.exists():
        if legacy.exists():raise ValueError('Both launch ownership records exist. No hook was changed.')
        return json.loads(state_path.read_text()),False
    if legacy.exists():
        state=json.loads(legacy.read_text())
        if state['application']!=APPLICATION:raise ValueError('Legacy launch ownership record is not recognized.')
        return dict(apps=dict(teams={k:v for k,v in state.items() if k!='hooks'}),hooks=state['hooks']),True
    return dict(apps={},hooks=[]),False


def require_owned(state):
    if not state['apps'] or any(name not in APPS or entry['application']!=APPS[name]
                                 for name,entry in state['apps'].items()):
        raise ValueError('Launch-hook ownership record is not recognized.')
    expected=set(hook_paths(state['apps']))
    if len(state['hooks'])!=len(expected) or {entry['path'] for entry in state['hooks']}!=expected:
        raise ValueError('Launch-hook ownership record is not recognized.')
    for entry in state['hooks']:
        p=Path(entry['path'])
        if not p.is_file() or p.is_symlink() or target.sha(p)!=entry['sha256']:
            raise ValueError('A launch hook changed outside Fontreal. It was left untouched: '+str(p))


def load_build(path,name='teams'):
    path=path.resolve(strict=True)
    record=json.loads(path.read_text())
    if record['spec']['application']!=APPS[name]:raise ValueError('The application build record identifies a different target.')
    return record


def compatibility(record,selectors=()):
    folder,executable,_=builder.LAYOUTS[record['spec']['application']]
    if not (Path(record['views']['normal']['directory'])/folder/executable).is_file():
        return 'saved Fontreal engine unavailable'
    return None


def hook_texts(name):
    application=APPS[name];_,hooks=paths(name)
    location=Path(builder.run([NATIVE,'info','--show-location',application]))
    desktop=(location/'export/share/applications'/(application+'.desktop')).read_text()
    desktop,count=re.subn(r'^Exec=/usr/bin/flatpak(?=\s)',lambda _: 'Exec='+desktop_arg(hooks['flatpak']),desktop,flags=re.M)
    if not count or count!=len(re.findall('^Exec=',desktop,flags=re.M)):
        raise ValueError('Native desktop commands are not supported. No hook was changed.')
    launch=[sys.executable,'-B',str(Path(__file__).resolve())]
    portal=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/(application+'.desktop')
    # Native ExecStart ':' keeps the quoted desktop path literal; systemd still needs %% for %.
    argument=json.dumps(str(portal),ensure_ascii=False).replace('%','%%')
    texts={'desktop':desktop,'autostart':'[Service]\nExecStart=\nExecStart=:/usr/bin/gio launch '+argument+'\n'}
    for key in ('flatpak','command','application'):
        args=[*launch,'flatpak','--'] if key=='flatpak' else [*launch,'run',name,'--']
        texts[key]='#!/bin/sh\nexec '+' '.join(map(shlex.quote,args))+' "$@"\n'
    return {p:(texts[key],0o644 if key in ('desktop','autostart') else 0o755) for key,p in hooks.items()}


def save_state(state):
    state_path,_=paths()
    state['hooks']=[dict(path=str(p),sha256=target.sha(p)) for p in hook_paths(state['apps']).values()]
    state_path.parent.mkdir(parents=True,exist_ok=True);state_path.write_text(json.dumps(state,indent=2)+'\n');state_path.chmod(0o600)


def enable(name,build_path):
    build_path=build_path.resolve(strict=True);record=load_build(build_path,name);reason=compatibility(record)
    if reason:raise ValueError(reason+'; no hook was changed.')
    builder.verify(record['views']['normal'])
    state,legacy=read_state()
    if state['apps']:require_owned(state)
    owned=hook_paths(state['apps']);apps=dict(state['apps'])
    apps[name]=dict(application=APPS[name],build=str(build_path),build_sha256=target.sha(build_path),
                    tool_sha256=target.sha(Path(__file__)))
    for key,p in hook_paths(apps).items():
        if key not in owned and (p.exists() or p.is_symlink()):
            raise ValueError('Existing per-user launch customizations were left untouched: '+str(p))
    texts={p:value for app in apps for p,value in hook_texts(app).items()}
    for entry in apps.values():entry['tool_sha256']=target.sha(Path(__file__))
    for p,(text,mode) in texts.items():
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);p.chmod(mode)
    save_state(dict(apps=apps))
    if legacy:paths()[0].with_name('teams.json').unlink()
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    print('Enabled '+name+' launch hooks. Fully quit and reopen the application normally to use Fontreal.')


def disable(name):
    state,legacy=read_state()
    if name not in state['apps']:print(name+' delivery is disabled.');return
    require_owned(state)
    remaining={key:value for key,value in state['apps'].items() if key!=name}
    retained=hook_paths(remaining)
    for key,p in hook_paths(state['apps']).items():
        if key not in retained:p.unlink()
    state_path=paths()[0]
    if remaining:save_state(dict(apps=remaining))
    else:(state_path.with_name('teams.json') if legacy else state_path).unlink()
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    print('Disabled '+name+' launch hooks. Fully quit and reopen for current stock rendering. Application data retained.')


def selected(arguments,state):
    # Flatpak splits at the first non-option before native option parsing.
    first=next((i for i,value in enumerate(arguments) if not value.startswith('-')),None)
    if first is None or arguments[first]!='run':return None
    index=next((i for i in range(first+1,len(arguments)) if not arguments[i].startswith('-')),None)
    if index is None:return None
    name=next((name for name,application in APPS.items() if arguments[index] in
               (application,application+'/x86_64',application+'/x86_64/stable','app/'+application+'/x86_64/stable')),None)
    if name not in state['apps']:return None
    application=APPS[name];command=builder.LAYOUTS[application][2]
    selectors=[]
    for option in [*arguments[:first],*arguments[first+1:index]]:
        if option in ('--file-forwarding','--command='+command,'--arch=x86_64','--branch=stable'):continue
        if option in ('--user','--system') or option.startswith('--installation='):selectors.append(option);continue
        return None
    saved=state['apps'][name];path=Path(saved['build'])
    record=load_build(path,name);reason=compatibility(record)
    if target.sha(path)!=saved['build_sha256']:reason='saved Fontreal record changed'
    if reason:
        print('Fontreal '+name+': '+reason+'; using the current native application.',file=sys.stderr);return None
    options,fd=view_options(builder.current_view(record,selectors))
    options.append('--env=FONTREAL_PROFILE='+rendering_profile())
    return [*arguments[:index],*options,*arguments[index:]],fd


def run(arguments):
    chosen=None
    try:
        state,_=read_state()
        if state['apps']:require_owned(state);chosen=selected(arguments,state)
    except (OSError,ValueError,KeyError,AssertionError,subprocess.SubprocessError):
        print('Fontreal: saved engine unavailable; using the current native application.',file=sys.stderr)
    if chosen is not None:
        command,fd=chosen
        try:
            os.set_inheritable(fd,True)
            os.execv(NATIVE,[NATIVE,*command])
        except OSError:
            os.close(fd)
            print('Fontreal: application view handoff failed; using the current native application.',file=sys.stderr)
    os.execv(NATIVE,[NATIVE,*arguments])


def status(name):
    state,_=read_state()
    if state['apps']:require_owned(state)
    result=dict(enabled=name in state['apps'],application=APPS[name])
    if result['enabled']:
        saved=state['apps'][name];record=load_build(Path(saved['build']),name)
        reason=compatibility(record)
        if target.sha(Path(saved['build']))!=saved['build_sha256']:reason='saved Fontreal record changed'
        result.update(build=saved['build'],compatibility=reason)
    print(json.dumps(result,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('enable');p.add_argument('target',choices=APPS);p.add_argument('--record',type=Path,required=True)
    for name in ('disable','status'):
        p=sub.add_parser(name);p.add_argument('target',choices=APPS)
    p=sub.add_parser('run');p.add_argument('target',choices=APPS);p.add_argument('arguments',nargs=argparse.REMAINDER)
    p=sub.add_parser('flatpak');p.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.action=='enable':enable(args.target,args.record)
    elif args.action=='disable':disable(args.target)
    elif args.action=='status':status(args.target)
    else:
        arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
        run(['run',APPS[args.target],*arguments] if args.action=='run' else arguments)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise SystemExit(str(error))
