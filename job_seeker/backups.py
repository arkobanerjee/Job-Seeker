"""Private archive validation and restore policy. Financial continuity is preserved."""
import hashlib
import io
import tempfile
import zipfile
from pathlib import Path
from contextlib import closing

CONTINUITY=('runs/budget.sqlite3','runs/outbox.sqlite3','runs/questions.sqlite3')

def restore_payload(backup,current):
    from .cloud import unpack,pack
    with tempfile.TemporaryDirectory() as old_tmp,tempfile.TemporaryDirectory() as live_tmp:
        old,live=Path(old_tmp),Path(live_tmp);unpack(backup,old);unpack(current,live)
        ledger=live/'runs/budget.sqlite3'
        if not ledger.exists():raise ValueError('Current spending ledger is required for restore')
        import sqlite3
        with closing(sqlite3.connect(ledger)) as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Current spending ledger is invalid')
        for name in CONTINUITY:
            target=old/name;source=live/name
            if source.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            elif target.exists():target.unlink()
        # Preserve unresolved or terminal task states and their question references.
        import json,shutil
        preserve=set()
        for checkpoint in (live/'runs').glob('*/checkpoint.json'):
            state=json.loads(checkpoint.read_text(encoding='utf-8'))
            if state.get('status') in ('waiting_user','paused','cancelled'):preserve.add(checkpoint.parent.name)
        questions=live/'runs/questions.sqlite3'
        if questions.exists():
            with closing(sqlite3.connect(questions)) as db:
                preserve.update(r[0] for r in db.execute('SELECT run_id FROM questions WHERE answer IS NULL'))
        for ident in preserve:
            import re
            if not re.fullmatch(r'[a-f0-9]{32}',ident):continue
            source=live/'runs'/ident
            if source.is_dir():
                for file in source.iterdir():
                    if file.is_file() and file.suffix in ('.json','.md'):
                        target=old/'runs'/ident/file.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
        # Current private preferences remain current; restore research data only.
        for name in ('config.toml','prompts/master.md','private/profile.md','private/resume.md'):
            source=live/name;target=old/name
            if source.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            elif target.exists():target.unlink()
        return pack(old)

def verify_archive(data,expected_sha=None):
    from .cloud import unpack
    if expected_sha and hashlib.sha256(data).hexdigest()!=expected_sha:raise ValueError('Backup checksum mismatch')
    with tempfile.TemporaryDirectory() as tmp:unpack(data,Path(tmp))
    return hashlib.sha256(data).hexdigest()
