import tempfile
import unittest
import sqlite3
import io,zipfile,json
from pathlib import Path
from contextlib import closing
from job_seeker.cloud import pack,unpack
from job_seeker.backups import verify_archive,restore_payload

class BackupTests(unittest.TestCase):
    def test_restore_keeps_current_financial_records_and_waiting_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);old=base/'old';live=base/'live';old.mkdir();live.mkdir()
            for root,value in [(old,1),(live,9)]:
                (root/'runs').mkdir();(root/'config.toml').write_text('version='+str(value))
                with closing(sqlite3.connect(root/'runs/budget.sqlite3')) as db,db:db.execute('CREATE TABLE balance(value INTEGER)');db.execute('INSERT INTO balance VALUES(?)',(value,))
            ident='a'*32;folder=live/'runs'/ident;folder.mkdir();(folder/'checkpoint.json').write_text(json.dumps({'status':'waiting_user'}))
            restored=restore_payload(pack(old),pack(live));out=base/'out';out.mkdir();unpack(restored,out)
            with closing(sqlite3.connect(out/'runs/budget.sqlite3')) as db:self.assertEqual(db.execute('SELECT value FROM balance').fetchone()[0],9)
            self.assertEqual((out/'config.toml').read_text(),'version=9');self.assertTrue((out/'runs'/ident/'checkpoint.json').exists())
    def test_checksum_and_archive_paths_fail_closed(self):
        with self.assertRaises(ValueError):verify_archive(b'not-a-zip','incorrect-checksum')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('../escape','bad')
        with self.assertRaises(ValueError):verify_archive(stream.getvalue())
    def test_missing_current_spending_ledger_prevents_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'runs').mkdir()
            data=pack(root)
            with self.assertRaises(ValueError):restore_payload(data,data)
