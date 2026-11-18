import sqlite3,json,os
from datetime import datetime,timezone
from pathlib import Path
from app.errors import DomainError

def _now():return datetime.now(timezone.utc).isoformat()

def connection():
    path=Path(os.environ.get('DB_PATH','data/records.db'));path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10);db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, decision TEXT NOT NULL DEFAULT "待复核")')
    db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS reinstate (id TEXT PRIMARY KEY, certificate TEXT NOT NULL, ruling TEXT, status TEXT NOT NULL DEFAULT "待裁决", version INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL)')
    return db

def save(run_id, body):
    with connection() as db:
        db.execute('INSERT OR IGNORE INTO runs(id,body) VALUES (?,?)',(run_id,json.dumps(body,ensure_ascii=False)))
        db.execute("INSERT INTO meta(key,value) VALUES ('latest',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(run_id,))
    return get(run_id)

def get(run_id):
    with connection() as db:r=db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not r:raise DomainError('NOT_FOUND','批次不存在',404)
    body=json.loads(r['body']);body.update(run_id=r['id'],review_version=r['version'],decision=r['decision']);return body

def history():
    with connection() as db:rows=db.execute("SELECT id,version,decision FROM runs ORDER BY CASE WHEN id=(SELECT value FROM meta WHERE key='latest') THEN 0 ELSE 1 END,rowid DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]

def review(run_id, version, decision):
    if decision not in ('通过','退回'):raise DomainError('DECISION','复核状态无效')
    with connection() as db:
        cur=db.execute('UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?',(decision,run_id,version))
        if cur.rowcount!=1:
            if not db.execute('SELECT 1 FROM runs WHERE id=?',(run_id,)).fetchone():raise DomainError('NOT_FOUND','批次不存在',404)
            raise DomainError('STALE','复核版本已更新，请刷新',409)
    return get(run_id)

def create_case(cert):
    # 断缴凭证仅在登记时写入；同案重试返回原案，凭证不同则拒绝改写
    now=_now();body=json.dumps(cert,ensure_ascii=False,sort_keys=True)
    with connection() as db:
        db.execute('INSERT OR IGNORE INTO reinstate(id,certificate,created,updated) VALUES (?,?,?,?)',(cert['case_id'],body,now,now))
        row=db.execute('SELECT certificate FROM reinstate WHERE id=?',(cert['case_id'],)).fetchone()
        if row['certificate']!=body:raise DomainError('CONFLICT','原断缴凭证不可改写',409)
    return get_case(cert['case_id'])

def get_case(case_id):
    with connection() as db:r=db.execute('SELECT * FROM reinstate WHERE id=?',(case_id,)).fetchone()
    if not r:raise DomainError('NOT_FOUND','复效案件不存在',404)
    return dict(r)

def list_cases():
    with connection() as db:rows=db.execute('SELECT * FROM reinstate ORDER BY rowid DESC LIMIT 100').fetchall()
    return [dict(r) for r in rows]

def put_ruling(case_id, ruling, version):
    # 同一基准重试为幂等空转；替换是单条条件更新，失败则旧版原样保留
    now=_now()
    with connection() as db:
        row=db.execute('SELECT * FROM reinstate WHERE id=?',(case_id,)).fetchone()
        if not row:raise DomainError('NOT_FOUND','复效案件不存在',404)
        current=json.loads(row['ruling']) if row['ruling'] else None
        if current and current['basis']==ruling['basis']:return dict(row)
        if row['status']=='已结案':raise DomainError('CLOSED','案件已结案，裁决不可更改')
        body=json.dumps(dict(ruling,ruled_at=now),ensure_ascii=False,sort_keys=True)
        cur=db.execute("UPDATE reinstate SET ruling=?,status='已裁决',version=version+1,updated=? WHERE id=? AND version=? AND status!='已结案'",(body,now,case_id,version))
        if cur.rowcount!=1:raise DomainError('STALE','案件版本已更新，请刷新',409)
    return get_case(case_id)

def close_case(case_id, version):
    # 结案前必须已裁决恢复基准；重复结案安全返回原案
    now=_now()
    with connection() as db:
        row=db.execute('SELECT * FROM reinstate WHERE id=?',(case_id,)).fetchone()
        if not row:raise DomainError('NOT_FOUND','复效案件不存在',404)
        if row['status']=='已结案':return dict(row)
        if row['status']!='已裁决':raise DomainError('PENDING','结案前须先裁决恢复基准')
        cur=db.execute("UPDATE reinstate SET status='已结案',version=version+1,updated=? WHERE id=? AND version=? AND status='已裁决'",(now,case_id,version))
        if cur.rowcount!=1:raise DomainError('STALE','案件版本已更新，请刷新',409)
    return get_case(case_id)
