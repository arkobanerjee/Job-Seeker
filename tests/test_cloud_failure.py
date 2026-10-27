import json
import tempfile
import unittest
from pathlib import Path
from job_seeker.cloud import record_cloud_failure
from job_seeker.history import run_history


class CloudFailureTests(unittest.TestCase):
    def test_initial_upload_failure_is_terminal_without_touching_older_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for ident,status in [('a'*32,'running'),('b'*32,'running'),('c'*32,'completed')]:
                folder=root/'runs'/ident;folder.mkdir(parents=True)
                (folder/'checkpoint.json').write_text(json.dumps({'run_id':ident,'status':status,'cloud_envelope':True}))
            record_cloud_failure(root,{'a'*32},None,ValueError('Cloud request failed: HTTP 404'))
            rows={r['run_id']:r for r in run_history(root/'runs')}
            self.assertEqual(rows['a'*32]['status'],'running')
            self.assertEqual(rows['c'*32]['status'],'completed')
            failed=rows['b'*32]
            self.assertEqual(failed['status'],'failed')
            self.assertIn('HTTP 404',failed['failure_reason'])
            self.assertTrue(failed['can_resume'])
            self.assertIsNotNone(failed['finished_at'])

    def test_resume_failure_uses_new_finish_time_and_never_exports_exception_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ident='a'*32;folder=root/'runs'/ident;folder.mkdir(parents=True)
            (folder/'checkpoint.json').write_text(json.dumps({'run_id':ident,'status':'running'}))
            (folder/'result.json').write_text(json.dumps({'finished_at':'2020-01-01T00:00:00Z'}))
            record_cloud_failure(root,{ident},ident,RuntimeError('SECRET_TOKEN private response'))
            row=run_history(root/'runs')[0]
            self.assertEqual(row['status'],'failed')
            self.assertNotEqual(row['finished_at'],'2020-01-01T00:00:00Z')
            self.assertNotIn('SECRET',json.dumps(row))
