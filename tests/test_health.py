import io
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from job_seeker.cloud import pack
from job_seeker.health import inspect_snapshot,diagnose_cloud


class HealthTests(unittest.TestCase):
    def test_integrity_missing_ledger_and_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'runs').mkdir()
            self.assertEqual(inspect_snapshot(pack(root))['status'],'blocked')
            with closing(sqlite3.connect(root/'runs/budget.sqlite3')) as db,db:db.execute('CREATE TABLE ledger(id TEXT)')
            data=pack(root);report=inspect_snapshot(data)
            self.assertEqual(report['status'],'ok')
            self.assertNotIn('ledger',str(report))
            with patch('job_seeker.cloud.MAX_SIZE',int(report['expanded_bytes']/0.8)):
                self.assertEqual(inspect_snapshot(data)['status'],'warning')
            with patch('job_seeker.cloud.MAX_SIZE',int(report['expanded_bytes']/0.95)):
                self.assertEqual(inspect_snapshot(data)['status'],'blocked')
            (root/'runs/catalog.sqlite3').write_bytes(b'corrupt')
            self.assertEqual(inspect_snapshot(pack(root))['status'],'blocked')

    def test_invalid_archive_fails_without_exposing_content(self):
        report=inspect_snapshot(b'private secret not a ZIP')
        self.assertEqual(report['status'],'blocked');self.assertNotIn('private secret',str(report))

    def test_diagnostics_only_reads_state_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=pack(Path(tmp));calls=[]
            class Cloud:
                def request(self,path,method='GET',body=None,**kwargs):
                    calls.append((path,method));return (data,'"version"') if path=='state' else {'saved':True}
            report=diagnose_cloud(Cloud())
            self.assertEqual(report['state_etag'],'"version"')
            self.assertEqual(calls,[('state','GET'),('health','PUT')])

    def test_blocked_preflight_never_reserves_or_invokes_research(self):
        from job_seeker.cloud import run_cloud
        from job_seeker.settings import Settings
        settings=Settings(search={'queries':[{'track':'ai','query':'AI roles'}]});calls=[]
        class Cloud:
            def request(self,path,method='GET',body=None,**kwargs):
                calls.append(path)
                if path=='state':return b'archive','"version"'
                if path=='settings':return {}
                if path=='health':return {'saved':True}
                raise AssertionError('Unexpected paid or state-changing call')
        with tempfile.TemporaryDirectory() as tmp,patch('job_seeker.cloud.ROOT',Path(tmp)),patch('job_seeker.cloud.Cloud',Cloud),patch('job_seeker.cloud.unpack'),patch('job_seeker.cloud.load_settings',return_value=(settings,Path(tmp))),patch('job_seeker.health.inspect_snapshot',return_value={'status':'blocked'}),patch.dict('os.environ',{'GITHUB_ACTIONS':'true'}):
            with self.assertRaisesRegex(ValueError,'health check blocked'):run_cloud()
        self.assertEqual(calls,['state','settings','health'])
