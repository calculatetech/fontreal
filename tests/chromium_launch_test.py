#!/usr/bin/env python3
"""Local launch contracts with synthetic packages, not a rendering qualification."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import chromium_delivery as delivery


class Executed(BaseException):
    pass


def put(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text)


def main():
    builder=delivery.builder
    output=(ROOT/'results/chromium-launch').resolve();output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='launch-',dir=(ROOT/'build').resolve()) as temporary:
        root=Path(temporary);home=root/'home';home.mkdir()
        work=root/'work';work.mkdir()
        signature=b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'+bytes([1,9])
        native=signature+b'111100011'+b'native engine'
        selected=signature+b'101100011'+b'selected engine'
        source=work/'artifacts/saved/normal'
        put(source/'teams-for-linux/resources/app.asar','obsolete application')
        put(source/'teams-for-linux/teams-for-linux','')
        (source/'teams-for-linux/teams-for-linux').write_bytes(selected)
        for name in ('icudtl.dat','resources.pak','LICENSE.fontreal.txt'):
            put(source/'teams-for-linux'/name,'selected '+name)
        for name in ('bin/zypak-helper','lib/libzypak-preload-host.so'):
            put(source/name,'selected '+name)
        (source/'bin/zypak-wrapper').symlink_to('/app/bin/zypak-helper')
        put(source/'share/licenses/fontreal-zypak/LICENSE','BSD notice')
        deployments=[]
        for name in ('A','B','user'):
            location=root/name;deployments.append(location)
            put(location/'files/teams-for-linux/resources/app.asar','current '+name)
            put(location/'files/teams-for-linux/teams-for-linux','')
            (location/'files/teams-for-linux/teams-for-linux').write_bytes(native)
            put(location/'files/bin/teams-for-linux','native wrapper '+name)
            put(location/'files/lib/new-native-module.so','native module '+name)
            put(location/'export/share/applications'/(delivery.APPLICATION+'.desktop'),
                '[Desktop Entry]\nType=Application\nName=Teams\nExec=/usr/bin/flatpak run '+delivery.APPLICATION+' %U\n')
        baseline={str(p):p.read_bytes() for d in deployments for p in d.rglob('*') if p.is_file()}
        profile=home/'original-profile/marker';put(profile,'keep working data')
        record=dict(spec=dict(application=delivery.APPLICATION,location='obsolete deployment'),
                    views=dict(normal=dict(directory=str(source),files=builder.tree(source),
                                           engine_sha256=delivery.target.sha(source/'teams-for-linux/teams-for-linux'))))
        build=source.parent/'build.json';put(build,json.dumps(record))
        put(build.parent/'qualification.json',json.dumps(dict(passed=True,build_sha256=delivery.target.sha(build))))
        current=deployments[0];queries=[];observations=[]

        def native_info(arguments,**kwargs):
            args=list(map(str,arguments));queries.append(args)
            assert args[0:2]==['/usr/bin/flatpak','info'] and args[-2:]==['--show-location',delivery.APPLICATION],args
            assert all(x in ('--user','--system','--installation=test') for x in args[2:-2]),args
            return str(deployments[2] if '--user' in args else current)

        def exec_native(executable,arguments):
            assert executable==delivery.NATIVE and arguments[0]==delivery.NATIVE
            options=[a for a in arguments if a.startswith('--app-path=')]
            observed=dict(argv=arguments[:],selected=bool(options))
            if options:
                view=Path(options[0].split('=',1)[1]);fd=int(next(a.split('=',1)[1] for a in arguments if a.startswith('--ro-bind-fd=')))
                assert os.get_inheritable(fd)
                assert os.fstat(fd).st_ino==view.stat().st_ino and os.fstat(fd).st_dev==view.stat().st_dev
                assert '--env=FONTREAL_ZYPAK_APP_PATH='+str(view) in arguments
                observed.update(view=str(view),resource=(view/'teams-for-linux/resources/app.asar').read_text(),
                                wrapper=(view/'bin/teams-for-linux').read_text())
                assert (view/'teams-for-linux/teams-for-linux').read_bytes()==signature+b'111100011'+b'selected engine'
                assert (view/'share/licenses/fontreal-zypak/LICENSE').read_text()=='BSD notice'
                assert (view/'teams-for-linux/LICENSE.fontreal.txt').read_text()=='selected LICENSE.fontreal.txt'
                assert (view/'lib/new-native-module.so').read_text().startswith('native module ')
                assert (view/'bin/zypak-wrapper').is_symlink()
                os.close(fd)
            observations.append(observed)
            raise Executed()

        def call(*arguments):
            with patch.object(sys,'argv',['chromium_delivery.py',*arguments]),contextlib.redirect_stdout(io.StringIO()):
                try:delivery.main()
                except Executed:pass

        env=dict(XDG_CONFIG_HOME=str(home/'config'),XDG_DATA_HOME=str(home/'data'))
        with patch.dict(os.environ,env),patch.object(Path,'home',return_value=home),patch.object(builder,'WORK',work),\
             patch.object(builder,'run',side_effect=native_info),patch.object(delivery.os,'execv',side_effect=exec_native),\
             patch.object(delivery.subprocess,'run') as commands:
            call('enable','teams','--record',str(build))
            state_path,hooks=delivery.paths();state_bytes=state_path.read_bytes()
            call('run','teams','--','https://example.invalid/a b?x=1&y=2')
            assert observations[-1]['resource']=='current A'
            first=Path(observations[-1]['view']);identity=first.stat().st_ino
            with patch.object(shutil,'copytree',side_effect=AssertionError('cached launch assembled again')),\
                 patch.object(builder,'tree',side_effect=AssertionError('cached launch hashed a tree')):
                call('flatpak','--','run',delivery.APPLICATION,'https://example.invalid/a b?x=1&y=2')
            assert observations[-1]['view']==str(first) and first.stat().st_ino==identity
            current=deployments[1]
            call('flatpak','--','run',delivery.APPLICATION,'https://example.invalid/a b?x=1&y=2')
            assert observations[-1]['resource']=='current B' and observations[-1]['view']!=str(first)
            call('flatpak','--','--user','run',delivery.APPLICATION)
            assert observations[-1]['resource']=='current user' and '--user' in observations[-1]['argv']
            assert ['--user']==queries[-1][2:-2]
            assert state_path.read_bytes()==state_bytes
            for observed in observations[:3]:
                assert observed['argv'][-1]=='https://example.invalid/a b?x=1&y=2'
            for arguments in (['run','other.app','a b'],['run','--file-forwarding','--command=other',delivery.APPLICATION,'a b'],
                              ['run','--arch','x86_64',delivery.APPLICATION,'a b']):
                before=len(queries)
                with patch.object(delivery,'view_options',side_effect=AssertionError('native route allocated a view')):
                    call('flatpak','--',*arguments)
                assert observations[-1]==dict(argv=[delivery.NATIVE,*arguments],selected=False)
                assert len(queries)==before
            with contextlib.redirect_stdout(io.StringIO()) as out:delivery.status()
            assert json.loads(out.getvalue())['compatibility'] is None
            alternate=work/'artifacts/another/normal';shutil.copytree(source,alternate,symlinks=True)
            put(alternate/'teams-for-linux/icudtl.dat','new coherent sidecar')
            newer=dict(spec=record['spec'],views=dict(normal=dict(record['views']['normal'],directory=str(alternate),files=builder.tree(alternate))))
            newer_build=alternate.parent/'build.json';put(newer_build,json.dumps(newer))
            put(newer_build.parent/'qualification.json',json.dumps(dict(passed=True,build_sha256=delivery.target.sha(newer_build))))
            call('enable','teams','--record',str(newer_build))
            call('run','teams')
            assert observations[-1]['view']!=str(first)
            assert (Path(observations[-1]['view'])/'teams-for-linux/icudtl.dat').read_text()=='new coherent sidecar'
            foreign=hooks['command'];saved=foreign.read_bytes();foreign.write_text('foreign customization')
            before=state_path.read_bytes()
            try:call('enable','teams','--record',str(build))
            except ValueError as error:assert 'outside Fontreal' in str(error)
            else:raise AssertionError('foreign hook accepted')
            assert foreign.read_text()=='foreign customization' and state_path.read_bytes()==before
            foreign.write_bytes(saved)
            call('disable','teams')
            assert not state_path.exists() and not any(p.exists() for p in hooks.values())
            call('run','teams','--','https://example.invalid/a b')
            assert observations[-1]==dict(argv=[delivery.NATIVE,'run',delivery.APPLICATION,'https://example.invalid/a b'],selected=False)
            binary=source/'teams-for-linux/teams-for-linux';binary.unlink()
            try:call('enable','teams','--record',str(build))
            except ValueError as error:assert 'engine unavailable' in str(error)
            else:raise AssertionError('missing engine accepted')
            assert not state_path.exists() and not any(p.exists() for p in hooks.values())
            assert commands.call_count==3
            for invoked in commands.call_args_list:assert invoked.args[0]==['systemctl','--user','daemon-reload']
        assert profile.read_text()=='keep working data'
        assert all(Path(name).read_bytes()==data for name,data in baseline.items())
        result=dict(passed=True,boundaries=['B-C4-1','B-C4-2','B-C4-3','B-C4-4'],
                    native_queries=queries,observations=observations,
                    scope='Synthetic local launch contracts. No application rendering claim.')
    # Temporary native fixtures are removed; keep only the bounded contract report.
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS current application launch contracts')


if __name__=='__main__':main()
