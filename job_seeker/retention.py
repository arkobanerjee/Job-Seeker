"""Archive terminal evidence only after a verified private copy exists."""
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime,timezone,timedelta


def candidates(root,keep=20,days=30,now=None):
    now=now or datetime.now(timezone.utc);rows=[];protected=set();question_runs={}
    questions=root/'runs/questions.sqlite3'
    if questions.exists():
        with closing(sqlite3.connect(questions)) as db:
            protected.update(r[0] for r in db.execute('SELECT run_id FROM questions WHERE answer IS NULL AND cancelled=0'))
            question_runs=dict(db.execute('SELECT id,run_id FROM questions'))
    outbox=root/'runs/outbox.sqlite3'
    if outbox.exists():
        with closing(sqlite3.connect(outbox)) as db:
            for ident, in db.execute("SELECT id FROM notifications WHERE status NOT IN ('sent','cancelled')"):
                protected.update(re.findall(r'(?<![a-f0-9])[a-f0-9]{32}(?![a-f0-9])',ident))
                if ident.startswith('question:') and ident[9:] in question_runs:protected.add(question_runs[ident[9:]])
    for file in (root/'runs').glob('*/checkpoint.json'):
        if file.parent.is_symlink() or not file.resolve().is_relative_to(root.resolve()):continue
        if not re.fullmatch('[a-f0-9]{32}',file.parent.name):continue
        try:
            state=json.loads(file.read_text(encoding='utf-8'))
            date=datetime.fromisoformat(state['started_at']);
            if date.tzinfo is None:continue
            rows.append((date,file.parent.name,state.get('status')))
        except (ValueError,KeyError):continue
    rows.sort(reverse=True)
    recent={ident for _,ident,_ in rows[:keep]}
    return [ident for date,ident,status in rows if ident not in protected|recent and date<now-timedelta(days=days) and status in ('completed','cancelled')]


def evidence_archive(root,ident):
    from .cloud import allowed,MAX_SIZE
    if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Invalid archive ID')
    directory=root/'runs'/ident
    if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe archive directory')
    stream=io.BytesIO();total=0
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in sorted((root/'runs'/ident).iterdir()):
            name=file.relative_to(root).as_posix()
            if file.is_file() and not file.is_symlink() and allowed(name):
                total+=file.stat().st_size
                if total>MAX_SIZE:raise ValueError('Run evidence exceeds archive limit')
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,file.read_bytes())
    return stream.getvalue()


def archive_terminal_runs(cloud,root,keep=20,days=30):
    from .backups import verify_archive
    from .cloud import pack
    from .catalog import Catalog
    from .registry import Registry
    ids=candidates(root,keep,days)
    # Materialize all summaries before moving raw evidence out of hot state.
    Catalog(root/'runs/catalog.sqlite3').import_runs(root/'runs')
    Registry(root/'runs/registry.sqlite3').import_runs(root/'runs')
    for ident in ids:
        data=evidence_archive(root,ident);digest=verify_archive(data)
        receipt=cloud.request('run-archive/'+ident,'PUT',data,True)
        if receipt['sha256']!=digest:raise ValueError('Archived evidence checksum mismatch')
        downloaded=cloud.request('run-archive/'+ident)
        if hashlib.sha256(downloaded).hexdigest()!=digest:raise ValueError('Archive readback failed; hot evidence retained')
        # Only exact allowlisted files under this validated run directory are removed.
        from .cloud import allowed
        for file in (root/'runs'/ident).iterdir():
            if file.is_file() and not file.is_symlink() and allowed(file.relative_to(root).as_posix()):file.unlink()
    return ids,pack(root)
