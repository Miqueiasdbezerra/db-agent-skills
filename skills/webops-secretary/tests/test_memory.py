"""Memory invariants with isolated synthetic data. No network or user memory."""
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from memory import Store, is_link, origin_only

ORIGIN = 'https://portal.example.test'


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='webops-memory-test-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'private'
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.task = self.store.create_task('demo', ORIGIN, 'Update a fictional record')

    def test_persistent_history_and_last_confirmed_state(self):
        self.store.plan(self.task,'save','Save fictional record')
        self.store.start(self.task,'save')
        self.store.resolve(self.task,'save','verified','Reloaded record shows expected fields')
        self.store.plan(self.task,'upload','Upload synthetic attachment')
        with Store(self.path) as reopened:
            state = reopened.resume(self.task)
        self.assertEqual(len(state['completed']),1)
        self.assertEqual(state['last_confirmed']['action_key'],'save')
        self.assertEqual(state['pending'][0]['action_key'],'upload')
        self.assertEqual([e['kind'] for e in state['history']],['created','planned','in_flight','verified','planned'])

    def test_crash_leaves_uncertain_never_retryable(self):
        self.store.plan(self.task,'save','Save fictional record')
        self.store.start(self.task,'save')
        with Store(self.path) as reopened:
            self.assertEqual(reopened.resume(self.task)['uncertain'][0]['state'],'in_flight')
            with self.assertRaises(ValueError): reopened.start(self.task,'save')
            reopened.resolve(self.task,'save','unknown','Request timed out; outcome not yet observed')
            with self.assertRaises(ValueError): reopened.start(self.task,'save')
            reopened.resolve(self.task,'save','verified','Record exists after reload; no resubmission')
        self.assertEqual(len(self.store.resume(self.task)['completed']),1)

    def test_duplicate_plan_is_idempotent_but_cannot_change_identity(self):
        first = self.store.plan(self.task,'save','Save fictional record')
        self.assertEqual(first,self.store.plan(self.task,'save','Save fictional record'))
        with self.assertRaises(ValueError): self.store.plan(self.task,'save','Delete a different record')
        self.assertEqual(len(self.store.resume(self.task)['actions']),1)

    def test_approval_reference_required_for_consequential_actions(self):
        for risk in ('financial','destructive','public','sensitive'):
            self.store.plan(self.task,risk,'Consequential fictional action',risk)
            with self.assertRaises(PermissionError): self.store.start(self.task,risk)
            result = self.store.start(self.task,risk,'user-message-2-specific-approval')
            self.assertEqual(result['state'],'in_flight')
            self.store.resolve(self.task,risk,'verified','Fictional outcome independently verified')

    def test_verified_action_is_immutable_and_completion_requires_evidence(self):
        self.store.plan(self.task,'save','Save fictional record')
        with self.assertRaises(ValueError): self.store.resolve(self.task,'save','verified','No action performed')
        with self.assertRaises(ValueError): self.store.checkpoint(self.task,'complete','Claimed complete')
        self.store.start(self.task,'save')
        self.store.resolve(self.task,'save','verified','Confirmed in reloaded list')
        with self.assertRaises(ValueError): self.store.resolve(self.task,'save','failed','Overwrite result')
        self.store.checkpoint(self.task,'complete','All requested fields verified')
        with self.assertRaises(ValueError): self.store.plan(self.task,'extra','Unrequested operation')

    def test_pause_blocks_mutation_until_resumed(self):
        self.store.plan(self.task,'save','Save fictional record')
        self.store.checkpoint(self.task,'paused','Waiting for fresh authorized session')
        with self.assertRaises(ValueError): self.store.start(self.task,'save')
        self.store.checkpoint(self.task,'active','Session and record revalidated')
        self.store.start(self.task,'save')

    def test_failed_action_cannot_silently_retry(self):
        self.store.plan(self.task,'save','Save fictional record')
        self.store.start(self.task,'save')
        self.store.resolve(self.task,'save','failed','Validation rejected the form before any commit')
        with self.assertRaises(ValueError): self.store.start(self.task,'save')
        self.assertEqual(len(self.store.resume(self.task)['failed']),1)

    def test_uncertain_result_blocks_later_action(self):
        self.store.plan(self.task,'save','Save fictional record')
        self.store.plan(self.task,'upload','Upload fictional note')
        self.store.start(self.task,'save')
        with self.assertRaises(ValueError): self.store.start(self.task,'upload')
        self.store.resolve(self.task,'save','verified','Record persisted after interrupted session')
        self.store.start(self.task,'upload')

    def test_reconciled_failed_attempt_and_verified_retry_can_finish(self):
        self.store.plan(self.task,'save','Save fictional record')
        self.store.start(self.task,'save')
        self.store.resolve(self.task,'save','failed','Form validation rejected before writing')
        with self.assertRaises(ValueError): self.store.checkpoint(self.task,'complete','No verified outcome')
        self.store.plan(self.task,'save-corrected','Save corrected fictional record after confirming no prior write')
        self.store.start(self.task,'save-corrected')
        self.store.resolve(self.task,'save-corrected','verified','Reloaded record matches requested fields')
        self.store.checkpoint(self.task,'complete','All requested outcomes verified; failed attempt retained')

    def test_playbooks_persist_and_are_isolated_by_site_and_scope(self):
        first = self.store.save_playbook('demo',ORIGIN,'records','Use labelled controls then inspect the reloaded list','v1','medium',True,'Synthetic record persisted')
        self.assertIsNotNone(first['last_validated_at'])
        with Store(self.path) as reopened:
            found = reopened.recall('demo',ORIGIN,'reloaded')
            self.assertEqual(found[0]['validation_count'],1)
            self.assertEqual(reopened.recall('other',ORIGIN),[])
            self.assertEqual(reopened.recall('demo','https://other.example.test'),[])
        self.assertEqual(self.store.recall('demo',ORIGIN,"' OR 1=1 --"),[])

    def test_interface_change_invalidates_prior_confidence(self):
        self.store.save_playbook('demo',ORIGIN,'records','Inspect old form','v1','high',True,'Confirmed synthetic result')
        self.store.invalidate_playbook('demo',ORIGIN,'records','Field labels changed on new interface')
        old = self.store.recall('demo',ORIGIN)[0]
        self.assertEqual((old['status'],old['confidence']),('stale','low'))
        self.assertIsNotNone(old['last_validated_at'])
        changed = self.store.save_playbook('demo',ORIGIN,'records','Inspect revised form','v2','low')
        self.assertEqual(changed['status'],'draft')
        self.assertIsNone(changed['last_validated_at'])

    def test_empty_validation_evidence_is_not_accepted(self):
        with self.assertRaises(ValueError): self.store.save_playbook('demo',ORIGIN,'records','Inspect form','v1',validated=True)

    def test_rejects_secret_values_without_echoing_them_or_persisting(self):
        samples = ['ghp_'+'A'*30, 'password'+'=fictional-secret', 'Authorization'+':Bearer-fake', 'https://portal.example.test/?'+'token'+'=fake']
        for value in samples:
            with self.assertRaises(ValueError) as caught:
                self.store.plan(self.task,'secret','Do not store '+value)
            self.assertNotIn(value,str(caught.exception))
        self.assertEqual(self.store.resume(self.task)['actions'],[])

    def test_rejects_personal_email_and_allows_reserved_fictional_domain(self):
        with self.assertRaises(ValueError): self.store.plan(self.task,'pii','Contact '+'person'+'@'+'private.invalid')
        self.store.plan(self.task,'fictional','Use demo@example.test in the synthetic form')

    def test_quoted_credentials_and_short_values_are_not_persisted(self):
        for field in ('pass'+'word', 'coo'+'kie', 'session_'+'id', 'to'+'ken'):
            for quote in ('"', "'"):
                value = '{'+quote+field+quote+': '+quote+'x7'+quote+'}'
                with self.subTest(field=field, quote=quote):
                    with self.assertRaises(ValueError) as caught:
                        self.store.plan(self.task,'private-value',value)
                    self.assertNotIn(value,str(caught.exception))
        self.assertEqual(self.store.resume(self.task)['actions'],[])

    def test_provider_credentials_cannot_be_stored_as_identifiers(self):
        value = 'gh'+'p_'+'a'*30
        with self.assertRaises(ValueError) as caught:
            self.store.create_task(value,ORIGIN,'Read fictional list')
        self.assertNotIn(value,str(caught.exception))

    def test_origin_rejects_credentials_paths_and_fragments(self):
        for value in ('https://user:pass'+'@'+'portal.example.test','https://portal.example.test/records','https://portal.example.test/#session','file:///private','https://portal.example.test:bad'):
            with self.assertRaises(ValueError): origin_only(value)

    def test_memory_inside_public_root_or_git_tree_is_rejected(self):
        public = Path(self.tmp.name)/'public'
        public.mkdir()
        with self.assertRaises(PermissionError): Store(public/'private',public_roots=[public])
        (public/'.git').write_text('gitdir: elsewhere',encoding='utf-8')
        with self.assertRaises(PermissionError): Store(public/'nested'/'private')
        self.assertFalse((public/'private').exists())
        with self.assertRaises(PermissionError): Store(ROOT/'private-test-memory')

    def test_symlink_root_and_database_are_rejected(self):
        link = Path(self.tmp.name)/'alias'
        try: link.symlink_to(self.path,target_is_directory=True)
        except OSError: self.skipTest('OS does not grant symlink creation')
        with self.assertRaises(PermissionError): Store(link)
        other = Path(self.tmp.name)/'other'; other.mkdir()
        (other/'memory.sqlite3').symlink_to(self.path/'memory.sqlite3')
        with self.assertRaises(PermissionError): Store(other)

    def test_portable_link_metadata_detection(self):
        # Synthetic metadata tests do not establish OS symlink privileges.
        for mode, attributes, expected in (
            (stat.S_IFLNK,0,True),
            (stat.S_IFDIR,0x400,True),
            (stat.S_IFREG,0,False),
        ):
            with self.subTest(mode=mode, attributes=attributes):
                info = SimpleNamespace(st_mode=mode,st_file_attributes=attributes)
                with patch.object(Path,'lstat',return_value=info):
                    self.assertEqual(is_link(self.path),expected)
        with patch.object(Path,'lstat',side_effect=FileNotFoundError):
            self.assertFalse(is_link(self.path))

    def test_portable_reparse_ancestor_blocks_memory_creation(self):
        candidate = Path(self.tmp.name)/'linked-parent'/'new-private'
        original = Path.lstat
        def metadata(path,*args,**kwargs):
            if path == candidate.parent:
                return SimpleNamespace(st_mode=stat.S_IFDIR,st_file_attributes=0x400)
            return original(path,*args,**kwargs)
        with patch.object(Path,'lstat',metadata):
            with self.assertRaises(PermissionError): Store(candidate)
        self.assertFalse(candidate.exists())

    def test_portable_database_sidecar_links_are_rejected(self):
        original = Path.lstat
        for name in ('memory.sqlite3','memory.sqlite3-journal','memory.sqlite3-wal','memory.sqlite3-shm'):
            for mode, attributes in ((stat.S_IFLNK,0),(stat.S_IFREG,0x400)):
                candidate = self.path/name
                def metadata(path,*args,**kwargs):
                    if path == candidate:
                        return SimpleNamespace(st_mode=mode,st_file_attributes=attributes)
                    return original(path,*args,**kwargs)
                with self.subTest(name=name,mode=mode):
                    with patch.object(Path,'lstat',metadata):
                        with self.assertRaises(PermissionError): Store(self.path)

    @unittest.skipUnless(os.name == 'nt','Windows junction test')
    def test_junction_memory_root_is_rejected(self):
        import _winapi
        link = Path(self.tmp.name)/'junction'
        try: _winapi.CreateJunction(str(self.path),str(link))
        except (AttributeError,OSError): self.skipTest('Junction creation unavailable')
        try:
            with self.assertRaises(PermissionError): Store(link)
        finally:
            link.rmdir()
        self.assertTrue((self.path/'memory.sqlite3').exists())

    def test_cross_process_cli_round_trip(self):
        command = [sys.executable,str(ROOT/'scripts/memory.py'),'--root',str(self.path)]
        result = subprocess.run(command+['create','--scope','cli','--origin',ORIGIN,'--objective','Read fictional list'],capture_output=True,text=True,check=True)
        task = json.loads(result.stdout)['task_id']
        self.assertEqual(self.store.resume(task)['task']['scope'],'cli')
        result = subprocess.run(command+['resume',task],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['task']['objective'],'Read fictional list')

    def test_second_connection_cannot_start_same_action_twice(self):
        self.store.plan(self.task,'save','Save fictional record')
        with Store(self.path) as other:
            self.store.start(self.task,'save')
            with self.assertRaises(ValueError): other.start(self.task,'save')
        self.assertEqual(len(self.store.resume(self.task)['uncertain']),1)

    def test_unknown_schema_is_not_overwritten(self):
        other = Path(self.tmp.name)/'future'; other.mkdir()
        with sqlite3.connect(other/'memory.sqlite3') as database:
            database.execute('PRAGMA user_version=99')
        database.close()
        with self.assertRaises(ValueError): Store(other)


if __name__ == '__main__':
    unittest.main()
