"""Real independent Git and filesystem failures, using fresh temporary roots."""
import json
import fnmatch
import os
import shutil
from pathlib import Path, PureWindowsPath
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
from mas_contract import TOPICS
from mas_workspace import Workspace, key, MAX_ARTIFACT, MAX_ADOPTION, NATIVE_NAMES, NATIVE_GLOBS


def project(path):
    """Self-contained synthetic source Git; never publish through the real checkout."""
    path.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parents[1]
    for directory in ('docs/mas', 'subagents', '.codex/agents'):
        shutil.copytree(source/directory, path/directory, dirs_exist_ok=True)
    for relative in ('.gitignore','AGENTS.md','pyproject.toml','uv.lock',
                     'src/pipeline/mas_runtime.py','src/pipeline/mas_workspace.py',
                     'src/pipeline/mas_contract.py','src/pipeline/polymer_additive_bounds.py',
                     'src/pipeline/prompts/campaign_main.jinja'):
        target = path/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/relative,target)
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    for args in [('init',),('add','--','.gitignore','AGENTS.md','pyproject.toml','uv.lock','docs','subagents','.codex','src'),
                 ('-c','user.name=Synthetic','-c','user.email=synthetic@localhost','-c','commit.gpgsign=false','-c','core.hooksPath='+os.devnull,'commit','-m','Synthetic source baseline')]:
        subprocess.run(['git',*args],cwd=path,env=env,capture_output=True,check=True)
    return path


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = project(self.base/'project with spaces 한글')
        self.w = Workspace(self.source, 'campaign', 'synthetic')

    def operation(self, kind='bootstrap'):
        record = dict(id='op1', campaign=self.w.campaign, kind=kind, status='running',
                      turn_id='turn1', turns=[], decision=None)
        self.w.state['operations']['op1'] = record
        self.w.state['active'] = 'op1'
        self.w.save()
        return record

    def files(self, record):
        return {**{f'data/knowledge/synthetic/{t}':'Synthetic theory; no observation.\n' for t in TOPICS},
                self.w.round_path(record)+'/adoption.json':'{"synthetic":true}\n'}

    def pending(self, extra=None):
        native = self.w.git
        def failed(*args, **kwargs):
            if args[0]=='commit-tree':raise RuntimeError('synthetic precommit failure')
            return native(*args, **kwargs)
        record = self.operation()
        with patch.object(self.w,'git',side_effect=failed), self.assertRaisesRegex(RuntimeError,'precommit'):
            self.w.publish(record,{**self.files(record), **(extra or {})},knowledge=True)
        return record, json.loads(self.w.state_path.read_text())['pending']

    def test_explicit_project_campaign_paths_and_escape_rejection(self):
        with self.assertRaises(ValueError):Workspace(self.base,'campaign','synthetic')
        with self.assertRaises(ValueError):Workspace(self.source/'data','campaign','synthetic')
        for name in ('../bad','/absolute','',r'foo\bar'):
            with self.subTest(name=name), self.assertRaises(ValueError):self.w.path(name)
        for name in ('../escape','NUL','x/y',''):
            with self.subTest(name=name), self.assertRaises(ValueError):key(name)
        self.assertEqual(self.w.area,'data/results/campaign/mas')
        self.assertFalse((self.w.path(self.w.area)/'.git').exists())

    def test_windows_logical_relative_projection_uses_posix_boundary_and_keeps_raw_rejections(self):
        # Logical serialization only: the real boundary still runs on this host.
        projected=object.__new__(Workspace)
        projected.root=PureWindowsPath('C:/project with spaces 한글')
        received=[]
        def boundary(relative):
            received.append(relative)
            with patch('mas_workspace.Path',Path):self.w.path(relative)
            return projected.root/PureWindowsPath(relative)
        projected.path=boundary
        with patch('mas_workspace.Path',PureWindowsPath):
            for value in ('data/raw/measurement.csv',PureWindowsPath('data/results/campaign/decision.md'),
                          PureWindowsPath('C:/project with spaces 한글/data/raw/measurement.csv')):
                with self.subTest(value=str(value)):
                    expected=PureWindowsPath(value)
                    if expected.is_absolute():expected=expected.relative_to(projected.root)
                    self.assertEqual(projected.relative(value),expected.as_posix())
                    self.assertIsInstance(received[-1],str)
                    self.assertNotIn('\\',received[-1])
            for value in (r'data\raw\measurement.csv','data/../escape.csv',PureWindowsPath('data/../escape.csv')):
                with self.subTest(reject=str(value)),self.assertRaises(ValueError):projected.relative(value)
        for value in (r'data\raw\measurement.csv','data/../escape.csv'):
            with self.subTest(native_reject=value),self.assertRaises(ValueError):self.w.relative(value)

    def test_cross_campaign_host_inputs_rejected_but_scientific_inputs_remain_readable(self):
        forbidden=['.native/sqlite/state_5.sqlite','.mas-runtime.json','.mas-state.json',
                   '.transactions/token/0','.mas.lock','.pipeline.lock','.inputs/request/provenance.json']
        for suffix in forbidden:
            path=self.source/'data/results/other/mas'/suffix
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('SYNTHETIC_NONSECRET_CANARY')
            with self.subTest(forbidden=suffix),self.assertRaisesRegex(ValueError,'host/native'):
                self.w.input_path(path)
        for relative in ('data/results/other/agg.csv','data/results/other/mas/rounds/accepted/decision.md',
                         self.w.area+'/.inputs/request/selected.csv','data/raw/.native/measurement.sqlite',
                         'data/raw/.transactions/table.csv','src/pipeline/mas_contract.py'):
            path=self.source/relative
            if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Synthetic approved scientific input.')
            self.assertEqual(self.w.input_path(relative),path)

    def test_linked_worktree_git_pointer_is_never_an_input(self):
        linked=self.base/'linked project 한글'
        self.w.git('worktree','add','--detach',str(linked),'HEAD')
        pointer=linked/'.git';before=pointer.read_bytes()
        other=Workspace(linked,'linked','synthetic')
        with self.assertRaisesRegex(ValueError,'host/native'):other.input_path('.git')
        self.assertEqual(pointer.read_bytes(),before)

    def test_native_overlap_preflight_rejects_before_construction_and_workspace_io(self):
        with self.w.lock():pass
        canary=self.source/'nested-native/canary.txt';canary.parent.mkdir();canary.write_bytes(b'SYNTHETIC_NONSECRET_CANARY')
        journal=self.w.state_path.read_bytes();source=(self.source/'AGENTS.md').read_bytes()
        head=self.w.head();index=Path(self.w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
        raw=index.read_bytes()
        def lock():
            with self.w.file_lock('.unexpected.lock'):pass
        def opened():
            with self.w.lock():pass
        calls=[lambda:Workspace(self.source,'campaign','synthetic'),lambda:self.w.write('unexpected.txt','No write'),
               self.w.save,self.w._open,lock,opened,lambda:self.w.git('rev-parse','HEAD')]
        for variable in ('CODEX_HOME','CODEX_SQLITE_HOME'):
            homes=[self.source.parent,self.source/'nested-native',self.source/self.w.area,
                   self.source/self.w.area/'.inputs',self.source/self.w.area/'.inputs/request',
                   self.source/self.w.area/'.native/sqlite',self.source/self.w.area/'rounds/op/attempt-0/.codex']
            for home in homes:
                environment={'CODEX_HOME':str(self.base/'external-home'),'CODEX_SQLITE_HOME':str(self.base/'external-sqlite'),variable:str(home)}
                with patch('pathlib.Path.home',return_value=self.base/'user-home'),patch.dict(os.environ,environment):
                    for number,call in enumerate(calls):
                        with self.subTest(variable=variable,home=str(home),producer=number),self.assertRaisesRegex(ValueError,'overlap'):
                            call()
        self.assertEqual(self.w.state_path.read_bytes(),journal);self.assertEqual((self.source/'AGENTS.md').read_bytes(),source)
        self.assertEqual(self.w.head(),head);self.assertEqual(index.read_bytes(),raw)
        self.assertFalse((self.source/'unexpected.txt').exists())
        self.assertFalse((self.source/self.w.area/'.unexpected.lock').exists())
        self.assertEqual(canary.read_bytes(),b'SYNTHETIC_NONSECRET_CANARY')

    def test_interrupted_recovery_preserves_foreign_index_flags_and_identity(self):
        for flag in ('--assume-unchanged','--skip-worktree','--index-version=4'):
            with self.subTest(flag=flag):
                self.w=Workspace(project(self.base/flag.lstrip('-')),'campaign','synthetic')
                with self.w.lock():
                    self.pending()
                    self.w.git('update-index',flag,*(['--','AGENTS.md'] if flag!='--index-version=4' else []))
                    index=Path(self.w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
                    raw=index.read_bytes();flags=self.w.git('ls-files','-v').stdout;head=self.w.head()
                    pending=json.loads(json.dumps(self.w.state['pending']));journal=self.w.state_path.read_bytes()
                    try:result=self.w.recover_publication()
                    except ValueError:result=None
                    print('SYNTHETIC_RECOVERY_INDEX_OPPONENT',json.dumps(dict(flag=flag,rejected=result is None,
                        ref_unchanged=self.w.head()==head,index_unchanged=index.read_bytes()==raw,
                        flags_unchanged=self.w.git('ls-files','-v').stdout==flags,pending_retained=self.w.state['pending'] is not None)))
                    self.assertIsNone(result)
                    self.assertEqual(self.w.head(),head);self.assertEqual(index.read_bytes(),raw)
                    self.assertEqual(self.w.git('ls-files','-v').stdout,flags)
                    self.assertEqual(self.w.state['pending'],pending);self.assertEqual(self.w.state_path.read_bytes(),journal)

    def test_interrupted_recovery_allows_only_clean_unrelated_source_advance(self):
        with self.w.lock():
            self.pending();original=self.w.head()
            self.w.write('user-source.py','value = 7\n');self.w.git('add','--','user-source.py')
            self.w.git('commit','-m','Unrelated source advance');advanced=self.w.head()
            accepted=self.w.recover_publication()
            self.assertNotEqual(advanced,original)
            self.assertEqual(self.w.git('rev-parse',accepted+'^').stdout.decode().strip(),advanced)
            self.assertEqual(self.w.git('show','HEAD:user-source.py').stdout,b'value = 7\n')
            self.assertEqual(self.w.git('rev-list','--count',advanced+'..HEAD').stdout.strip(),b'1')
            self.assertIsNone(self.w.state['pending'])
            self.assertEqual(self.w.git('ls-files','-v','--','user-source.py').stdout,b'H user-source.py\n')

    def test_fsmonitor_metadata_cannot_hide_behind_a_clean_source_advance(self):
        with self.w.lock():
            self.pending()
            self.w.write('user-source.py','value = 7\n');self.w.git('add','--','user-source.py')
            self.w.git('commit','-m','Unrelated source advance')
            hook=self.base/'synthetic-fsmonitor'
            hook.write_text('#!/bin/sh\nprintf x >> "$0.calls"\nprintf "SYNTHETIC_TOKEN\\000"\n');hook.chmod(0o700)
            options=('-c','core.fsmonitor='+str(hook),'-c','core.fsmonitorHookVersion=2')
            self.w.git(*options,'update-index','--fsmonitor','--fsmonitor-valid','--','AGENTS.md')
            visible=self.w.git(*options,'ls-files','-f','--','AGENTS.md').stdout
            self.assertEqual(visible,b'h AGENTS.md\n')
            self.assertEqual(self.w.git('ls-files','-v','--','AGENTS.md').stdout,b'H AGENTS.md\n')
            self.assertEqual(self.w.git('ls-files','-f','--','AGENTS.md').stdout,b'H AGENTS.md\n')
            self.w.git('config','--local','core.fsmonitor',str(hook))
            calls=Path(str(hook)+'.calls');called=calls.read_bytes()
            index=Path(self.w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
            raw=index.read_bytes();head=self.w.head();pending=json.loads(json.dumps(self.w.state['pending']))
            try:result=self.w.recover_publication()
            except ValueError:result=None
            print('SYNTHETIC_FSMONITOR_OPPONENT',json.dumps(dict(rejected=result is None,index_unchanged=index.read_bytes()==raw,
                ref_unchanged=self.w.head()==head,configured_provider_not_run=calls.read_bytes()==called)))
            self.assertIsNone(result)
            self.assertEqual(index.read_bytes(),raw);self.assertEqual(self.w.head(),head)
            self.assertEqual(self.w.state['pending'],pending);self.assertEqual(calls.read_bytes(),called)

    def test_lock_excludes_second_writer_and_releases_after_error(self):
        with self.assertRaisesRegex(RuntimeError,'synthetic failure'):
            with self.w.lock():
                with self.assertRaisesRegex(RuntimeError,'locked'):
                    with Workspace(self.source,'campaign','synthetic').lock():self.fail('Concurrent writer')
                raise RuntimeError('synthetic failure')
        with Workspace(self.source,'campaign','synthetic').lock() as cold:self.assertIsNone(cold.state['thread_id'])

    def test_caller_lock_serializes_without_rewriting_native_state(self):
        with self.w.lock():original=self.w.state_path.read_bytes()
        with self.w.file_lock('.pipeline.lock'):
            other=Workspace(self.source,'campaign','synthetic')
            with self.assertRaisesRegex(RuntimeError,'locked'):
                with other.file_lock('.pipeline.lock'):self.fail('Concurrent caller')
            with other.lock():self.assertEqual(other.state_path.read_bytes(),original)

    def test_atomic_publication_has_one_non_self_referencing_checkpoint(self):
        baseline=self.w.head()
        with self.w.lock():
            record=self.operation();head=self.w.publish(record,self.files(record),knowledge=True)
            self.assertEqual(self.w.state['knowledge_commit'],head)
            self.assertEqual(record['commit'],head)
            self.assertEqual(record['status'],'completed')
            self.assertEqual(record['turns'],['turn1']);self.assertIsNone(record['turn_id'])
            self.assertEqual(self.w.git('rev-list','--count',baseline+'..HEAD').stdout.strip(),b'1')
            checkpoint=json.loads(self.w.path(self.w.checkpoint).read_text())
            self.assertNotIn('head',checkpoint);self.assertNotIn('knowledge_commit',checkpoint)
            self.assertNotIn('commit',checkpoint['operations']['op1'])
            self.assertNotIn(head,self.w.path(self.w.checkpoint).read_text())
            self.assertEqual(self.w.publication_commit(checkpoint['publication_id']),head)
            changed=set(self.w.git('diff-tree','--no-commit-id','--name-only','-r',head).stdout.decode().splitlines())
            self.assertEqual(changed,set(self.files(record))|{self.w.checkpoint})
            self.assertRegex(self.w.git('log','-1','--format=%s').stdout.decode(),r'^\d{6}-\d{2}-\d{2} docs adopt MAS knowledge [a-f0-9]+')
            self.assertFalse(self.w.git('diff','--cached','--name-only').stdout.strip())

    def test_publication_late_working_edits_preserve_bytes_and_pending(self):
        for phase in ('snapshot','read-tree','write-tree','update-ref'):
            with self.subTest(phase=phase):
                w=Workspace(project(self.base/('late-'+phase)),'campaign','synthetic');self.w=w
                with w.lock():
                    record=self.operation();target='data/knowledge/synthetic/'+TOPICS[0]
                    foreign=b'SYNTHETIC_EXTERNAL_DURING_PUBLICATION\n';native=w.git;write=w.write;once=[True]
                    def edit():
                        w.path(target).parent.mkdir(parents=True,exist_ok=True);w.path(target).write_bytes(foreign)
                    def intercepted(*args,**kwargs):
                        value=native(*args,**kwargs)
                        if phase==args[0] and once[0]:once[0]=False;edit()
                        return value
                    def snapshot(path,data):
                        value=write(path,data)
                        if phase=='snapshot' and '/.transactions/' in path and once[0]:once[0]=False;edit()
                        return value
                    before=w.head()
                    with patch.object(w,'git',side_effect=intercepted),patch.object(w,'write',side_effect=snapshot):
                        with self.assertRaises(ValueError):w.publish(record,self.files(record),knowledge=True)
                    self.assertFalse(once[0]);self.assertEqual(w.path(target).read_bytes(),foreign)
                    self.assertIsNotNone(w.state['pending']);self.assertEqual(record['status'],'running')
                    self.assertEqual(w.head()==before,phase!='update-ref')

    def test_unrelated_staged_and_working_changes_are_never_adopted_or_reverted(self):
        with self.w.lock():
            record=self.operation();path=self.source/'AGENTS.md';path.write_text(path.read_text()+'\nUser work.\n')
            original=path.read_bytes();self.w.git('add','--','AGENTS.md')
            index=self.w.git('ls-files','--stage','-z').stdout;head=self.w.head()
            with self.assertRaisesRegex(ValueError,'staged'):self.w.publish(record,self.files(record),knowledge=True)
            self.assertEqual(self.w.git('ls-files','--stage','-z').stdout,index);self.assertEqual(self.w.head(),head)
            self.assertEqual(path.read_bytes(),original)
            # Explicit test-owned user commit, not cleanup by the publication routine.
            self.w.git('commit','-m','Synthetic user source commit')
            path.write_bytes(original+b'Unstaged user change.\n');dirty=path.read_bytes()
            head=self.w.publish(record,self.files(record),knowledge=True)
            self.assertEqual(path.read_bytes(),dirty)
            self.assertNotIn('AGENTS.md',self.w.git('diff-tree','--no-commit-id','--name-only','-r',head).stdout.decode())

    def test_unrelated_code_commits_do_not_invalidate_accepted_mas_content(self):
        with self.w.lock():
            record=self.operation();accepted=self.w.publish(record,self.files(record),knowledge=True)
            self.w.write('user-code.py','value = 7\n');self.w.git('add','--','user-code.py');self.w.git('commit','-m','User source update')
        with Workspace(self.source,'campaign','synthetic').lock() as cold:
            self.assertNotEqual(cold.head(),accepted);self.assertEqual(cold.state['knowledge_commit'],accepted)
            self.assertEqual(cold.state['operations']['op1']['commit'],accepted)

    def test_precommit_failure_and_lost_cas_ack_recover_without_duplicate_commit(self):
        for lost in (False,True):
            with self.subTest(lost=lost):
                self.w=Workspace(self.source,'case-'+str(lost),'synthetic')
                with self.w.lock():
                    record=self.operation();native=self.w.git;before=self.w.head()
                    def fail(*args,**kwargs):
                        if args[0]==('update-ref' if lost else 'commit-tree'):
                            if lost:native(*args,**kwargs)
                            raise RuntimeError('synthetic lost publication')
                        return native(*args,**kwargs)
                    with patch.object(self.w,'git',side_effect=fail), self.assertRaises(RuntimeError):
                        self.w.publish(record,self.files(record),knowledge=True)
                    self.assertIsNotNone(self.w.state['pending'])
                with Workspace(self.source,self.w.campaign,'synthetic').lock() as cold:
                    committed=cold.recover_publication()
                    self.assertEqual(cold.state['knowledge_commit'],committed);self.assertIsNone(cold.state['pending'])
                    self.assertEqual(cold.git('rev-list','--count',before+'..HEAD').stdout.strip(),b'1')

    def test_cas_race_is_preserved_then_rebound_only_for_unchanged_owned_paths(self):
        with self.w.lock():
            record=self.operation();native=self.w.git;once=[True]
            def raced(*args,**kwargs):
                if args[0]=='update-ref' and once[0]:
                    once[0]=False;base=self.w.head()
                    tree=native('rev-parse',base+'^{tree}').stdout.decode().strip()
                    foreign=native('commit-tree',tree,'-p',base,'-m','Concurrent source commit').stdout.decode().strip()
                    native('update-ref',args[3],foreign,base)
                return native(*args,**kwargs)
            with patch.object(self.w,'git',side_effect=raced),self.assertRaises(RuntimeError):
                self.w.publish(record,self.files(record),knowledge=True)
            pending=json.loads(self.w.state_path.read_text())['pending'];foreign=self.w.head()
            self.assertNotEqual(foreign,pending['base'])
            committed=self.w.recover_publication()
            self.assertEqual(self.w.git('rev-parse',committed+'^').stdout.decode().strip(),foreign)
            self.assertEqual(self.w.state['operations']['op1']['commit'],committed)

    def test_foreign_index_lock_and_conflicting_pending_payload_are_preserved(self):
        with self.w.lock():
            record,tx=self.pending()
            lock=Path(self.w.git('rev-parse','--path-format=absolute','--git-path','index.lock').stdout.decode().strip())
            lock.write_bytes(b'foreign lock')
            with self.assertRaisesRegex(ValueError,'Foreign'):self.w.recover_publication()
            self.assertEqual(lock.read_bytes(),b'foreign lock');lock.unlink()  # Test-owned adversary only.
            snapshot=self.w.path(next(iter(tx['prepared'].values()))['snapshot']);snapshot.write_text('changed')
            with self.assertRaisesRegex(ValueError,'payload'):self.w.recover_publication()
            self.assertIsNotNone(self.w.state['pending'])

    def test_pending_working_mode_missing_and_index_conflicts_are_not_overwritten(self):
        for defect in ('working','mode','missing','index'):
            with self.subTest(defect=defect):
                self.w=Workspace(project(self.base/('conflict-'+defect)),'campaign','synthetic')
                with self.w.lock():
                    report=self.w.area+'/rounds/op1/attempt-0/report.md';self.w.write(report,'Original report.\n')
                    record,tx=self.pending({report:'Original report.\n'});target=self.w.path(report)
                    if defect=='working':target.write_text('Foreign edit.\n')
                    elif defect=='mode':target.chmod(0o755)
                    elif defect=='missing':target.unlink()
                    else:self.w.write('foreign.txt','Foreign.\n');self.w.git('add','--','foreign.txt')
                    before=target.read_bytes() if target.exists() else None;head=self.w.head()
                    with self.assertRaises(ValueError):self.w.recover_publication()
                    self.assertEqual(target.read_bytes() if target.exists() else None,before);self.assertEqual(self.w.head(),head)
                    if defect=='index':self.w.git('commit','-m','Test-owned foreign stage')

    def test_shared_bank_reuse_new_main_and_explicit_reconciliation(self):
        with self.w.lock():
            record=self.operation();first=self.w.publish(record,self.files(record),knowledge=True)
        other=Workspace(self.source,'other-campaign','synthetic')
        with other.lock():
            self.assertEqual(other.state['knowledge_commit'],first);self.assertIsNone(other.state['thread_id'])
            self.w=other;record=self.operation();changed=self.files(record);changed['data/knowledge/synthetic/'+TOPICS[0]]='New reviewed theory.\n'
            second=other.publish(record,changed,knowledge=True)
        original=Workspace(self.source,'campaign','synthetic')
        with self.assertRaisesRegex(ValueError,'reconsideration'):
            with original.lock():self.fail('Silent bank adoption')
        with original.lock(reconcile=True):self.assertEqual(original.state['knowledge_commit'],second)
        with self.assertRaisesRegex(ValueError,'binding'):
            with Workspace(self.source,'campaign','different').lock():self.fail('Material rebind')

    def test_unreviewed_material_commit_and_owned_content_drift_rejected(self):
        with self.w.lock():
            record=self.operation();self.w.publish(record,self.files(record),knowledge=True)
            target='data/knowledge/synthetic/'+TOPICS[0];self.w.write(target,'Unreviewed.\n');self.w.git('add','--',target);self.w.git('commit','-m','Manual bank edit')
        for campaign in ('campaign','new-campaign'):
            with self.assertRaises(ValueError):
                with Workspace(self.source,campaign,'synthetic').lock():self.fail('Unreviewed bank')

    def test_checkpoint_only_clone_is_portable_and_does_not_create_native_history(self):
        with self.w.lock():
            record=self.operation();self.w.state['thread_id']='saved-native-id';accepted=self.w.publish(record,self.files(record),knowledge=True)
        relocated=self.base/'relocated 한글';shutil.copytree(self.source,relocated)
        (relocated/self.w.area/'.mas-runtime.json').unlink()
        with Workspace(relocated,'campaign','synthetic').lock() as cold:
            self.assertEqual(cold.state['head'],accepted);self.assertEqual(cold.state['thread_id'],'saved-native-id')
            self.assertNotIn(str(self.source),json.dumps(cold._stable(cold.state)))
            self.assertFalse((relocated/'sessions').exists())

    def test_local_cache_cannot_rewrite_accepted_completion_or_native_identity(self):
        with self.w.lock():
            record=self.operation();self.w.state['thread_id']='saved-main'
            self.w.publish(record,self.files(record),knowledge=True)
        original=self.w.state_path.read_bytes()
        for defect in ('status','decision','thread','history'):
            value=json.loads(original)
            if defect=='status':value['operations']['op1']['status']='running'
            elif defect=='decision':value['operations']['op1']['decision']={'action':'run','reason':'Forged cache'}
            elif defect=='thread':value['thread_id']='replacement-main'
            else:value['operations'].pop('op1')
            self.w.state_path.write_text(json.dumps(value))
            with self.subTest(defect=defect),self.assertRaisesRegex(ValueError,'checkpoint|binding|history'):
                with Workspace(self.source,'campaign','synthetic').lock():self.fail('Forged accepted cache')
            self.assertEqual(json.loads(self.w.state_path.read_text()),value)
        self.w.state_path.write_bytes(original)

    def test_retired_external_state_and_unsafe_links_are_rejected_without_cleanup(self):
        old=self.source/'.mas-state.json';old.write_text('{"version":1}')
        with self.assertRaisesRegex(ValueError,'Retired'):
            with self.w.lock():self.fail('Old state')
        self.assertEqual(old.read_text(),'{"version":1}')
        outside=self.base/'outside.md';outside.write_text('original')
        (self.source/'alias.md').symlink_to(outside)
        os.link(outside,self.source/'hard.md')
        for name in ('alias.md','hard.md'):
            with self.assertRaises(ValueError):self.w.path(name)
        self.assertEqual(outside.read_text(),'original')

    def test_derived_artifacts_preserve_real_code_tables_figures_and_reject_raw_type_size(self):
        with self.w.lock():
            record=self.operation();base=self.w.attempt_path(record)+'/artifacts/'
            content={'code/analysis.py':b'print(1 + 2)\n','tables/result.csv':b'name,value\nSYNTHETIC,3\n',
                     'figures/result.svg':b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1 1"/></svg>'}
            files=self.files(record)
            for name,data in content.items():
                relative=base+name;self.w.write(relative,data);path,kind=self.w.artifact(record,relative)
                self.assertEqual(kind,name.split('/')[0]);files[relative]=path.read_bytes()
            for name,data in {'tables/raw/original.csv':b'a,b\n1,2','tables/auth.json':b'{}','figures/bad.png':b'not PNG',
                              'code/bad.py':b'not valid python !!!','tables/bad.csv':b'a,b\n1'}.items():
                self.w.write(base+name,data)
                with self.subTest(name=name),self.assertRaises((ValueError,SyntaxError)):self.w.artifact(record,base+name)
            self.w.write(base+'tables/large.json',b' '*(MAX_ARTIFACT+1))
            with self.assertRaisesRegex(ValueError,'16 MiB'):self.w.artifact(record,base+'tables/large.json')
            accepted=self.w.publish(record,files,knowledge=True)
            for name,data in content.items():self.assertEqual(self.w.git('show',accepted+':'+base+name).stdout,data)

    def test_native_ignores_do_not_hide_metadata_or_arbitrary_measured_files(self):
        for p in ('auth.json','auth.json.lock','sessions/a.jsonl','thread-writer-locks/one.lock','state_5.sqlite-wal','logs_5.sqlite-shm',self.w.area+'/.mas-runtime.json',self.w.area+'/.transactions/x'):
            self.assertEqual(self.w.git('check-ignore','--',p,check=False).returncode,0,p)
        for p in ('AGENTS.md','.codex/agents/hypothesis-qa.toml','logs/run_synthetic.log','data/raw/auth.json','data/raw/measurement.sqlite','data/results/campaign/figure.png',self.w.checkpoint):
            self.assertNotEqual(self.w.git('check-ignore','--',p,check=False).returncode,0,p)

    def test_root_native_metadata_names_are_ignored_and_excluded_from_scientific_reads(self):
        from mas_runtime import _attempt_config
        with self.w.lock():
            profile=_attempt_config(self.w,self.operation())['permissions']['mas']['filesystem']
        for name in ('installation_id','.sandbox_migration'):
            path=self.source/name;path.write_bytes(b'SYNTHETIC_NONSECRET_NATIVE_METADATA')
            with self.subTest(name=name,guard='ignore'):
                self.assertEqual(self.w.git('check-ignore','--',name,check=False).returncode,0)
            with self.subTest(name=name,guard='input'),self.assertRaisesRegex(ValueError,'host/native'):
                self.w.input_path(name)
            with self.subTest(name=name,guard='operator-context'),self.assertRaisesRegex(ValueError,'native/host'):
                Workspace.operator_context_path(self.source,path)
            with self.subTest(name=name,guard='production-profile'):
                self.assertEqual(profile.get(str(path)),'deny')
            self.assertEqual(path.read_bytes(),b'SYNTHETIC_NONSECRET_NATIVE_METADATA')

    def test_nested_native_metadata_names_and_existing_project_data_remain_readable(self):
        from mas_runtime import _attempt_config
        with self.w.lock():
            profile=_attempt_config(self.w,self.operation())['permissions']['mas']['filesystem']
        for relative in ('data/raw/installation_id','data/raw/.sandbox_migration',
                         'data/results/other/measurements/installation_id',
                         'data/results/other/measurements/.sandbox_migration','logs/run_synthetic.log'):
            with self.subTest(relative=relative):
                path=self.source/relative;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('Synthetic ordinary measurement or pipeline history.\n')
                self.assertNotEqual(self.w.git('check-ignore','--',relative,check=False).returncode,0)
                self.assertEqual(self.w.input_path(relative),path)
                self.assertEqual(Workspace.operator_context_path(self.source,path),path)
                self.assertFalse(any(mode=='deny' and any(fnmatch.fnmatchcase(str(parent),pattern)
                    for parent in (path,*path.parents)) for pattern,mode in profile.items()))
        role=self.source/'.codex/agents/hypothesis-qa.toml'
        self.assertTrue(role.is_file())
        self.assertNotEqual(self.w.git('check-ignore','--','.codex/agents/hypothesis-qa.toml',check=False).returncode,0)
        self.assertFalse(any(mode=='deny' and any(fnmatch.fnmatchcase(str(parent),pattern)
            for parent in (role,*role.parents)) for pattern,mode in profile.items()))

    def test_aggregate_adoption_size_rejects_individually_valid_derived_files(self):
        self.assertEqual(MAX_ARTIFACT,16*1024*1024)
        self.assertEqual(MAX_ADOPTION,64*1024*1024)
        head=self.w.head()
        with self.w.lock():
            record=self.operation();files=self.files(record)
            data=b'"'+b'x'*(13*1024*1024)+b'"'
            for i in range(5):
                path=self.w.attempt_path(record)+f'/artifacts/tables/derived-{i}.json'
                self.w.write(path,data);self.w.artifact(record,path)
                files[path]=data
            with self.assertRaisesRegex(ValueError,'64 MiB'):
                self.w.publish(record,files,knowledge=True)
            self.assertIsNone(self.w.state['pending'])
            self.assertFalse(self.w.path(self.w.checkpoint).exists())
            self.assertEqual(self.w.head(),head)

    def test_native_names_preserve_tracked_pipeline_logs_and_have_no_root_collision(self):
        legacy = self.source/'logs/run_synthetic.log'
        legacy.parent.mkdir();legacy.write_text('Synthetic legacy pipeline history.\n')
        self.w.git('add','--','logs/run_synthetic.log')
        self.w.git('commit','-m','Synthetic legacy history')
        self.assertEqual(self.w.input_path(legacy),legacy)
        from mas_runtime import _attempt_config
        with self.w.lock():
            record=self.operation()
            profile=_attempt_config(self.w,record)['permissions']['mas']['filesystem']
            self.assertNotIn(str(self.source/'logs'),profile)
            self.w.publish(record,self.files(record),knowledge=True)
        self.assertEqual(self.w.git('show','HEAD:logs/run_synthetic.log').stdout,legacy.read_bytes())
        # Inspect names only in the actual source checkout; never mutate it.
        actual=Path(__file__).resolve().parents[1]
        paths=subprocess.check_output(['git','ls-files','-z'],cwd=actual).decode().split('\0')
        self.assertTrue(any(p.startswith('logs/') for p in paths))
        for p in filter(None,paths):
            first=p.split('/')[0]
            self.assertFalse(first in NATIVE_NAMES or any(fnmatch.fnmatchcase(first,g) for g in NATIVE_GLOBS),p)

    def renewal(self):
        original=self.operation();self.w.publish(original,self.files(original),knowledge=True)
        record=dict(id='op2',campaign=self.w.campaign,kind='knowledge',status='running',turn_id='turn2',turns=[],decision=None)
        self.w.state['operations'][record['id']]=record;self.w.state['active']=record['id'];self.w.save()
        files=self.files(record);files['data/knowledge/synthetic/'+TOPICS[0]]='New reviewed synthetic theory.\n'
        return record,files

    def test_capture_boundary_preserves_each_unexpected_object_and_new_target(self):
        for defect in ('bytes','mode','missing','symlink','hardlink','directory','new-target','parent','old-fd'):
            with self.subTest(defect=defect):
                self.w=Workspace(project(self.base/('capture-'+defect)),'campaign','synthetic');w=self.w
                with w.lock():
                    record,files=self.renewal();relative='data/knowledge/synthetic/'+TOPICS[0];target=w.root/relative
                    original=target.read_bytes();before=w.head();native=os.rename;once=[True]
                    foreign=self.base/('foreign-'+defect);foreign.mkdir();outside=foreign/TOPICS[0];outside.write_bytes(b'FOREIGN\n')
                    descriptor=os.open(target,os.O_WRONLY) if defect=='old-fd' else None
                    def intercepted(source,destination,*args,**kwargs):
                        selected=source==TOPICS[0] and destination=='capture' and once[0]
                        if selected:
                            once[0]=False
                            if defect=='bytes':target.write_bytes(b'FOREIGN\n')
                            elif defect=='mode':target.chmod(0o755)
                            elif defect=='missing':target.unlink()
                            elif defect=='symlink':target.unlink();target.symlink_to(outside)
                            elif defect=='hardlink':target.unlink();os.link(outside,target)
                            elif defect=='directory':target.unlink();target.mkdir();(target/'opaque').write_bytes(b'FOREIGN\n')
                            elif defect=='parent':
                                native(target.parent,target.parent.with_name('moved-synthetic'));target.parent.symlink_to(foreign)
                        result=native(source,destination,*args,**kwargs)
                        if selected and defect=='new-target':target.write_bytes(b'FOREIGN\n')
                        if selected and defect=='old-fd':os.write(descriptor,b'FOREIGN\n');os.ftruncate(descriptor,8);os.fsync(descriptor)
                        return result
                    try:
                        with patch('mas_workspace.os.rename',side_effect=intercepted),self.assertRaises(ValueError):w.publish(record,files,knowledge=True)
                    finally:
                        if descriptor is not None:os.close(descriptor)
                    self.assertFalse(once[0]);self.assertEqual(w.head(),before);self.assertEqual(record['status'],'running')
                    tx=w.state['pending'];self.assertIsNotNone(tx)
                    capture=w.root/tx['prepared'][relative]['slot']/'capture'
                    if defect in ('bytes','old-fd'):self.assertEqual(capture.read_bytes(),b'FOREIGN\n')
                    elif defect=='mode':self.assertEqual(capture.stat().st_mode&0o777,0o755)
                    elif defect=='missing':self.assertFalse(capture.exists());self.assertFalse(target.exists())
                    elif defect=='symlink':self.assertTrue(capture.is_symlink());self.assertEqual(os.readlink(capture),str(outside))
                    elif defect=='hardlink':self.assertEqual(capture.stat().st_ino,outside.stat().st_ino);self.assertEqual(capture.stat().st_nlink,2)
                    elif defect=='directory':self.assertTrue(capture.is_dir());self.assertEqual((capture/'opaque').read_bytes(),b'FOREIGN\n')
                    elif defect=='new-target':self.assertEqual(target.read_bytes(),b'FOREIGN\n');self.assertEqual(capture.read_bytes(),original)
                    elif defect=='parent':self.assertEqual(outside.read_bytes(),b'FOREIGN\n');self.assertEqual(capture.read_bytes(),original)
                    self.assertEqual(outside.read_bytes(),b'FOREIGN\n')

    def test_capture_link_and_unlink_interruptions_cold_resume_exactly_once(self):
        for point in ('capture','link','unlink','index-capture','index-link','index-unlink',
                      'checkpoint-capture','checkpoint-link','checkpoint-unlink','adoption-link','decision-link'):
            with self.subTest(point=point):
                self.w=Workspace(project(self.base/('interrupt-'+point)),'campaign','synthetic');w=self.w
                with w.lock():
                    record,files=self.renewal();before=w.head();once=[True]
                    if point=='decision-link':files[w.round_path(record)+'/decision.md']='Synthetic managed decision.\n'
                    operation=os.rename if point.endswith('capture') else os.link if point.endswith('link') and not point.endswith('unlink') else os.unlink
                    def intercepted(source,*args,**kwargs):
                        result=operation(source,*args,**kwargs)
                        is_index=point.startswith('index-')
                        capture_name='index' if is_index else '.mas-state.json' if point.startswith('checkpoint-') else TOPICS[0]
                        chosen=source==capture_name if point.endswith('capture') else source=='image'
                        if source=='image':
                            fd=kwargs.get('src_dir_fd') if 'link' in point and not point.endswith('unlink') else kwargs.get('dir_fd')
                            # Identify only this registered index or first canonical image.
                            slot='index-install' if is_index else 'target-0'
                            pending=w.state['pending'];relative=w._transaction_path(pending,slot)
                            if point.startswith('checkpoint-'):relative=pending['prepared'][w.checkpoint]['slot']
                            elif point=='adoption-link':relative=pending['prepared'][w.round_path(record)+'/adoption.json']['slot']
                            elif point=='decision-link':relative=pending['prepared'][w.round_path(record)+'/decision.md']['slot']
                            directory=w.path(relative)
                            expected=directory.stat() if directory.exists() else None
                            chosen=fd is not None and expected is not None and (os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(expected.st_dev,expected.st_ino)
                        if chosen and once[0]:once[0]=False;raise KeyboardInterrupt('Synthetic abrupt stop')
                        return result
                    name='rename' if point.endswith('capture') else 'link' if point.endswith('link') and not point.endswith('unlink') else 'unlink'
                    with patch('mas_workspace.os.'+name,side_effect=intercepted),self.assertRaises(KeyboardInterrupt):w.publish(record,files,knowledge=True)
                    self.assertFalse(once[0]);self.assertIsNotNone(w.state['pending'])
                with Workspace(w.root,w.campaign,w.material).lock() as cold:
                    committed=cold.recover_publication();self.assertIsNone(cold.state['pending'])
                    self.assertEqual(cold.state['operations']['op2']['commit'],committed)
                    self.assertEqual(cold.state['operations']['op2']['status'],'published')
                    self.assertEqual(cold.git('rev-list','--count',before+'..HEAD').stdout.strip(),b'1')
                    cold._verify_frontier();self.assertFalse(cold.git('diff','--cached','--name-only').stdout.strip())

    def test_closing_drift_and_abrupt_pending_none_keep_cold_evidence(self):
        for phase in ('journal','receipt','finalized','abrupt-journal'):
            with self.subTest(phase=phase):
                self.w=Workspace(project(self.base/('close-'+phase)),'campaign','synthetic');w=self.w
                with w.lock():
                    record=self.operation();before=w.head();write=w.write;once=[True];target=w.root/'data/knowledge/synthetic'/TOPICS[0]
                    def intercepted(path,data):
                        result=write(path,data)
                        pending=w.state['pending']
                        prospective=path.endswith('/.mas-runtime.json') and pending is None and w.state['publication_id']
                        chosen=prospective if phase in ('journal','abrupt-journal') else path.endswith('/receipt.json') if phase=='receipt' else path.endswith('/transaction.json') and '"phase": "finalized"' in str(data)
                        if chosen and once[0]:
                            once[0]=False;target.write_bytes(b'CLOSING_FOREIGN\n')
                            if phase=='abrupt-journal':raise KeyboardInterrupt('Synthetic crash with prospective journal')
                        return result
                    error=KeyboardInterrupt if phase=='abrupt-journal' else ValueError
                    with patch.object(w,'write',side_effect=intercepted),self.assertRaises(error):w.publish(record,self.files(record),knowledge=True)
                    self.assertFalse(once[0]);self.assertNotEqual(w.head(),before);self.assertEqual(record['status'],'running')
                    self.assertEqual(target.read_bytes(),b'CLOSING_FOREIGN\n')
                with Workspace(w.root,w.campaign,w.material).lock() as cold:
                    self.assertIsNotNone(cold.state['pending'])
                    with self.assertRaises(ValueError):cold.recover_publication()
                    self.assertEqual(target.read_bytes(),b'CLOSING_FOREIGN\n')
                    # Explicit test-operator resolution in the SAME registered inode.
                    tx=cold.state['pending'];entry=tx['prepared']['data/knowledge/synthetic/'+TOPICS[0]]
                    target.write_bytes(cold.path(entry['snapshot']).read_bytes())
                    candidate=cold.recover_publication();self.assertIsNone(cold.state['pending'])
                    self.assertEqual(candidate,cold.head());cold._verify_frontier()
                    self.assertEqual(cold.git('rev-list','--count',before+'..HEAD').stdout.strip(),b'1')

    def test_index_capture_preserves_foreign_special_bytes_and_gap(self):
        for when in ('before','gap'):
            with self.subTest(when=when):
                self.w=Workspace(project(self.base/('index-'+when)),'campaign','synthetic');w=self.w
                with w.lock():
                    record=self.operation();base=w.head();native=os.rename;once=[True]
                    index=Path(w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
                    alternate=self.base/('special-'+when);alternate.write_bytes(index.read_bytes())
                    w.git('update-index','--assume-unchanged','--','AGENTS.md',index=alternate);foreign=alternate.read_bytes()
                    def intercepted(source,destination,*args,**kwargs):
                        selected=source=='index' and destination=='capture' and once[0]
                        if selected and when=='before':index.write_bytes(foreign)
                        result=native(source,destination,*args,**kwargs)
                        if selected:
                            once[0]=False
                            if when=='gap':index.write_bytes(foreign)
                        return result
                    with patch('mas_workspace.os.rename',side_effect=intercepted),self.assertRaises(ValueError):w.publish(record,self.files(record),knowledge=True)
                    self.assertFalse(once[0]);self.assertNotEqual(w.head(),base);self.assertIsNotNone(w.state['pending'])
                    tx=w.state['pending'];capture=w.root/tx['index_install']['slot']/'capture'
                    if when=='before':self.assertFalse(index.exists());self.assertEqual(capture.read_bytes(),foreign)
                    else:self.assertEqual(index.read_bytes(),foreign);self.assertNotEqual(capture.read_bytes(),foreign)
                    self.assertEqual(record['status'],'running')

    def test_successive_pointer_later_operations_and_tracked_only_clone(self):
        with self.w.lock():
            record,files=self.renewal();old=self.w.state['local_publication']
            self.w.publish(record,files,knowledge=True);new=self.w.state['local_publication'];self.assertNotEqual(old,new)
            self.w.state['operations']['later']=dict(id='later',campaign='campaign',kind='decision',status='running',turn_id='next-native',turns=[],decision=None)
            self.w.state['active']='later';self.w.save();saved=json.loads(json.dumps(self.w.state))
        with Workspace(self.source,'campaign','synthetic').lock() as cold:
            self.assertEqual(cold.state,saved);self.assertEqual(cold.state['operations']['later']['turn_id'],'next-native')
        clone=self.base/'tracked-only';self.w.git('clone','--no-hardlinks',str(self.source),str(clone))
        self.assertFalse((clone/self.w.area/'.transactions').exists())
        for repeat in range(2):
            with Workspace(clone,'campaign','synthetic').lock() as cold:
                self.assertEqual(cold.state['publication_id'],new);self.assertEqual(cold.state['operations']['op2']['status'],'published')
                self.assertNotIn('later',cold.state['operations']);self.assertIsNone(cold.state['pending'])

    def test_missing_corrupt_or_old_active_evidence_is_preserved(self):
        for defect in ('pointer','intent','receipt','corrupt','old-pending'):
            with self.subTest(defect=defect):
                w=Workspace(project(self.base/('evidence-'+defect)),'campaign','synthetic');self.w=w
                with w.lock():
                    record=self.operation();w.publish(record,self.files(record),knowledge=True)
                    pointer=w.path(w.area+'/.transactions/active.json');active=json.loads(pointer.read_text())
                    if defect=='pointer':pointer.unlink()
                    elif defect=='intent':w.path(w._transaction_path(active,'intent.json')).unlink()
                    elif defect=='receipt':w.path(w._transaction_path(active,'receipt.json')).unlink()
                    elif defect=='corrupt':pointer.write_text('{corrupt')
                    else:w.state['pending']={'token':'old','candidate':None};w.save()
                    raw=w.state_path.read_bytes();head=w.head()
                with self.assertRaises(ValueError):
                    with Workspace(w.root,w.campaign,w.material).lock():self.fail('Unknown local closure accepted')
                self.assertEqual(w.state_path.read_bytes(),raw);self.assertEqual(w.head(),head)

    def test_unsupported_capture_install_and_durability_preserve_known_states(self):
        for point in ('capability','capture','install','fsync'):
            with self.subTest(point=point):
                self.w=Workspace(project(self.base/('unsupported-'+point)),'campaign','synthetic');w=self.w
                with w.lock():
                    record,files=self.renewal();base=w.head();target=w.root/'data/knowledge/synthetic'/TOPICS[0];original=target.read_bytes()
                    native=os.rename if point in ('capability','capture') else os.link if point=='install' else os.fsync
                    once=[True]
                    def intercepted(*args,**kwargs):
                        selected=(args[0]=='probe' if point=='capability' else args[0]==TOPICS[0] if point=='capture' else args[0]=='image' if point=='install' else w.state['pending'] is not None)
                        if selected and once[0]:once[0]=False;raise OSError('Synthetic unsupported filesystem primitive')
                        return native(*args,**kwargs)
                    name='rename' if point in ('capability','capture') else 'link' if point=='install' else 'fsync'
                    with patch('mas_workspace.os.'+name,side_effect=intercepted),self.assertRaises(OSError):w.publish(record,files,knowledge=True)
                    self.assertFalse(once[0]);self.assertEqual(w.head(),base);self.assertEqual(record['status'],'running')
                    if point=='install':
                        self.assertFalse(target.exists());tx=w.state['pending'];entry=tx['prepared']['data/knowledge/synthetic/'+TOPICS[0]]
                        self.assertEqual((w.root/entry['slot']/'capture').read_bytes(),original)
                    else:self.assertEqual(target.read_bytes(),original)

    def test_all_publication_target_classes_and_closing_boundaries_reject_drift(self):
        for kind in ('topic','adoption','decision','checkpoint','markdown','code','table','figure'):
            with self.subTest(kind=kind):
                w=Workspace(project(self.base/('target-'+kind)),'campaign','synthetic');self.w=w
                with w.lock():
                    record=self.operation();files=self.files(record);base=w.head()
                    paths={'topic':'data/knowledge/synthetic/'+TOPICS[0],
                        'adoption':w.round_path(record)+'/adoption.json','decision':w.round_path(record)+'/decision.md',
                        'checkpoint':w.checkpoint,'markdown':w.attempt_path(record)+'/report.md',
                        'code':w.attempt_path(record)+'/artifacts/code/analysis.py',
                        'table':w.attempt_path(record)+'/artifacts/tables/derived.csv',
                        'figure':w.attempt_path(record)+'/artifacts/figures/derived.svg'}
                    contents={'decision':'Synthetic host decision.\n','markdown':'Synthetic reviewed record.\n',
                        'code':'print(1 + 2)\n','table':'name,value\nSYNTHETIC,3\n','figure':'<svg xmlns="http://www.w3.org/2000/svg"/>'}
                    if kind in contents:
                        if kind!='decision':w.write(paths[kind],contents[kind])
                        files[paths[kind]]=contents[kind]
                    native=w.git;once=[True];target=w.root/paths[kind]
                    def intercepted(*args,**kwargs):
                        value=native(*args,**kwargs)
                        if args[0]=='write-tree' and once[0]:once[0]=False;target.write_bytes(b'FOREIGN_CLASS_BYTES\n')
                        return value
                    with patch.object(w,'git',side_effect=intercepted),self.assertRaises(ValueError):w.publish(record,files,knowledge=True)
                    self.assertEqual(w.head(),base);self.assertEqual(target.read_bytes(),b'FOREIGN_CLASS_BYTES\n')
                    self.assertIsNotNone(w.state['pending']);self.assertEqual(record['status'],'running')
        for boundary in ('inside-cas','commit-tree','index-finish','hydrate'):
            with self.subTest(boundary=boundary):
                w=Workspace(project(self.base/('boundary-'+boundary)),'campaign','synthetic');self.w=w
                with w.lock():
                    record=self.operation();before=w.head();target=w.root/'data/knowledge/synthetic'/TOPICS[0]
                    native=w.git;install=w._install_publication;hydrate=w._hydrate;once=[True]
                    def edit():once[0]=False;target.write_bytes(b'FOREIGN_BOUNDARY_BYTES\n')
                    def git(*args,**kwargs):
                        if boundary=='inside-cas' and args[0]=='update-ref' and once[0]:edit()
                        value=native(*args,**kwargs)
                        if boundary=='commit-tree' and args[0]=='commit-tree' and once[0]:edit()
                        return value
                    def installed(tx,path,entry):
                        value=install(tx,path,entry)
                        if boundary=='index-finish' and entry.get('index') and once[0]:edit()
                        return value
                    def hydrated():
                        value=hydrate()
                        if boundary=='hydrate' and once[0]:edit()
                        return value
                    with patch.object(w,'git',side_effect=git),patch.object(w,'_install_publication',side_effect=installed),patch.object(w,'_hydrate',side_effect=hydrated),self.assertRaises(ValueError):
                        w.publish(record,self.files(record),knowledge=True)
                    self.assertFalse(once[0]);self.assertEqual(target.read_bytes(),b'FOREIGN_BOUNDARY_BYTES\n')
                    self.assertEqual(w.head()==before,boundary=='commit-tree');self.assertIsNotNone(w.state['pending'])
                    self.assertEqual(record['status'],'running')

    def test_fresh_interpreter_closes_prospective_journal_without_replay(self):
        with self.w.lock():
            record=self.operation();before=self.w.head();save=self.w.save;once=[True]
            def interrupted():
                save()
                if self.w.state['pending'] is None and self.w.state['publication_id'] and once[0]:
                    once[0]=False;raise KeyboardInterrupt('Synthetic stopped closing')
            with patch.object(self.w,'save',side_effect=interrupted),self.assertRaises(KeyboardInterrupt):self.w.publish(record,self.files(record),knowledge=True)
            self.assertIsNone(json.loads(self.w.state_path.read_text())['pending'])
        script="from mas_workspace import Workspace; import json,sys; w=Workspace(sys.argv[1],'campaign','synthetic'); exec('with w.lock():\\n assert w.state[\\\"pending\\\"] is not None\\n c=w.recover_publication()\\n assert w.state[\\\"pending\\\"] is None\\n print(json.dumps(dict(commit=c,status=w.state[\\\"operations\\\"][\\\"op1\\\"][\\\"status\\\"])))')"
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src/pipeline'),'PYTHONDONTWRITEBYTECODE':'1'}
        result=subprocess.run([sys.executable,'-c',script,str(self.source)],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);receipt=json.loads(result.stdout)
        self.assertEqual(receipt['status'],'completed');self.assertEqual(receipt['commit'],self.w.head())
        self.assertEqual(self.w.git('rev-list','--count',before+'..HEAD').stdout.strip(),b'1')
        print('SYNTHETIC_FRESH_INTERPRETER_CLOSURE',result.stdout.strip())

    def test_crash_after_finalized_marker_records_incident_before_cache(self):
        with self.w.lock():
            record=self.operation();save=self.w._save_transaction;once=[True]
            target=self.w.root/'data/knowledge/synthetic'/TOPICS[0];tokens=[]
            def interrupted(tx):
                save(tx)
                if tx['phase']=='finalized' and once[0]:
                    once[0]=False;tokens.append(tx['token']);target.write_bytes(b'FOREIGN_FINALIZED_BYTES\n')
                    raise KeyboardInterrupt('Synthetic crash before final guard')
            with patch.object(self.w,'_save_transaction',side_effect=interrupted),self.assertRaises(KeyboardInterrupt):
                self.w.publish(record,self.files(record),knowledge=True)
            journal=self.w.state_path.read_bytes();self.assertIsNone(json.loads(journal)['pending'])
        with self.assertRaisesRegex(ValueError,'Accepted MAS content changed'):
            with Workspace(self.source,'campaign','synthetic').lock():self.fail('Dirty completed cache accepted')
        self.assertEqual(self.w.state_path.read_bytes(),journal)
        directory=self.w.root/self.w.area/'.transactions'/tokens[0]
        self.assertEqual(json.loads((directory/'incident.json').read_text())['type'],'AcceptedFrontierChanged')
        tx=json.loads((directory/'transaction.json').read_text());entry=tx['prepared']['data/knowledge/synthetic/'+TOPICS[0]]
        target.write_bytes(self.w.path(entry['snapshot']).read_bytes())
        with Workspace(self.source,'campaign','synthetic').lock() as cold:
            self.assertIsNone(cold.state['pending']);self.assertEqual(cold.state['operations']['op1']['status'],'completed')
            self.assertTrue((directory/'incident.json').exists())

    def test_late_native_overlap_precedes_capture_and_retains_original_path(self):
        with self.w.lock():
            record,files=self.renewal();w=self.w;target=w.root/'data/knowledge/synthetic'/TOPICS[0]
            original=target.read_bytes();before=w.head();native=w.git;once=[True]
            def intercepted(*args,**kwargs):
                value=native(*args,**kwargs)
                if args[0]=='read-tree' and once[0]:once[0]=False;os.environ['CODEX_HOME']=str(target.parent)
                return value
            with patch.dict(os.environ,{}),patch.object(w,'git',side_effect=intercepted),self.assertRaisesRegex(ValueError,'overlap'):
                w.publish(record,files,knowledge=True)
            self.assertFalse(once[0]);self.assertEqual(target.read_bytes(),original);self.assertEqual(w.head(),before)
            tx=w.state['pending'];self.assertIsNotNone(tx)
            capture=w.root/tx['prepared']['data/knowledge/synthetic/'+TOPICS[0]]['slot']/'capture'
            self.assertFalse(capture.exists());self.assertEqual(record['status'],'running')


if __name__=='__main__':unittest.main()
