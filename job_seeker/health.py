"""Read-only snapshot diagnostics. Reports contain counts, never candidate text."""
import hashlib
import io
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def inspect_snapshot(data):
    from .cloud import MAX_SIZE, unpack
    checks=[]
    report={'checked_at':datetime.now(timezone.utc).isoformat(),
            'sha256':hashlib.sha256(data).hexdigest(),'archive_bytes':len(data),
            'expanded_bytes':0,'files':0,'size_limit_bytes':MAX_SIZE,'file_limit':2000,
            'checks':checks,'status':'blocked'}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);unpack(data,root)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                report.update(expanded_bytes=sum(x.file_size for x in archive.infolist()),files=len(archive.infolist()))
            checks.append({'check':'archive','status':'ok'})
            ratio=max(report['expanded_bytes']/MAX_SIZE,report['archive_bytes']/MAX_SIZE,report['files']/2000)
            checks.append({'check':'capacity','status':'blocked' if ratio>=.9 else 'warning' if ratio>=.75 else 'ok'})
            for name in ('budget','catalog','questions','registry','outbox'):
                file=root/'runs'/f'{name}.sqlite3'
                status='missing' if name=='budget' else 'not_initialized'
                if file.exists():
                    try:
                        with closing(sqlite3.connect(file.as_uri()+'?mode=ro',uri=True)) as db:
                            status='ok' if db.execute('PRAGMA quick_check').fetchone()[0]=='ok' else 'blocked'
                    except sqlite3.DatabaseError:status='blocked'
                checks.append({'check':name+'_database','status':status})
    except (ValueError,zipfile.BadZipFile,RuntimeError,OSError):
        checks.append({'check':'archive','status':'blocked'})
    statuses={x['status'] for x in checks}
    report['status']='blocked' if statuses & {'blocked','missing'} else 'warning' if 'warning' in statuses else 'ok'
    return report


def diagnose_cloud(cloud):
    data,etag=cloud.request('state',return_etag=True)
    report=inspect_snapshot(data);report['state_etag']=etag or ''
    cloud.request('health','PUT',report)
    return report
