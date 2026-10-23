import json
import tempfile
import unittest
from pathlib import Path
from job_seeker.history import run_history

class HistoryTests(unittest.TestCase):
    def test_summary_omits_sensitive_inputs_and_reports_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/('a'*32);folder.mkdir()
            state={'run_id':'a'*32,'status':'partial','cloud_envelope':True,'started_at':'2026-10-23','config':{'monitoring':{'enabled':True}},'prompt':'private profile','sources':{'url':{'text':'raw private input'}},'limitations':['Page unavailable'],'model_calls':1}
            (folder/'checkpoint.json').write_text(json.dumps(state))
            rows=run_history(root);self.assertTrue(rows[0]['can_resume']);self.assertEqual(rows[0]['mode'],'monitor')
            self.assertNotIn('private',json.dumps(rows));self.assertNotIn('sources',rows[0]);self.assertIsNone(rows[0]['observed_estimate_usd'])
            state['cloud_envelope']=False;(folder/'checkpoint.json').write_text(json.dumps(state))
            self.assertFalse(run_history(root)[0]['can_resume'])
