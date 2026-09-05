"""Durable local outbox. MDB files are only read by the PowerShell bridge."""
from __future__ import annotations
import argparse,hashlib,json,logging,os,sqlite3,subprocess,time,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from . import PROJECT_ROOT
from .config import load_config

class Outbox:
    def __init__(self,path:Path):
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("CREATE TABLE IF NOT EXISTS seen(key TEXT PRIMARY KEY); CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,payload TEXT NOT NULL);")
    def stage(self,rows:list[dict],collector_id:str):
        with self.db:
            fresh=[]
            for r in rows:
                if self.db.execute("INSERT OR IGNORE INTO seen VALUES(?)",(r.get("revision_key",r["source_key"]),)).rowcount:fresh.append(r)
            if fresh:
                batch=str(uuid.uuid4())
                self.db.execute("INSERT INTO outbox VALUES(?,?)",(batch,json.dumps({"batch_id":batch,"collector_id":collector_id,"rows":fresh},ensure_ascii=False)))
        return len(fresh)
    def flush(self,url:str,token:str):
        sent=0
        for bid,payload in self.db.execute("SELECT id,payload FROM outbox ORDER BY rowid").fetchall():
            req=Request(url,data=payload.encode(),headers={"Content-Type":"application/json","x-collector-token":token},method="POST")
            with urlopen(req,timeout=60) as response:
                result=json.load(response)
                if result.get("batch_id")!=bid:raise RuntimeError("Batch acknowledgement mismatch")
            with self.db:self.db.execute("DELETE FROM outbox WHERE id=?",(bid,))
            sent+=1
        return sent

def normalized(row:dict,zone:str)->dict:
    timestamp=datetime.fromisoformat(row["source_at"])
    if timestamp.tzinfo is None:timestamp=timestamp.replace(tzinfo=ZoneInfo(zone))
    row["source_at"]=timestamp.astimezone(timezone.utc).isoformat()
    canonical=json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    row["revision_key"]=hashlib.sha256(canonical.encode()).hexdigest()
    mutable = {"LastWM", "LastFert", "LastAccum", "DailyWM", "DailyFert", "DailyAccum", "Programs", "Water_Meters"}
    if row["entity"] in mutable:
        fields = ["System", "Dream", "Unit", "ObjType", "ObjSubType", "ObjNum", "Line", "Tact_Number", "Tact_Index", "ProgName", "WM_GType", "WM_Number"]
        identity = {k:row["data"].get(k) for k in fields}
        identity.update(entity=row["entity"],dream=row["dream_id"])
        if row["entity"].startswith("Daily"):identity["date"]=row["source_at"][:10]
        row["source_key"]=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    else:row["source_key"]=row["revision_key"]
    return row

def cycle(cfg:dict,outbox:Outbox,since:str):
    root=Path(cfg["discovery"]["rootPath"])
    if not root.is_absolute():root=(PROJECT_ROOT/root).resolve()
    enabled={str(d["dreamId"]) for d in cfg["dreams"] if d.get("enabled",True)}
    settings=cfg["supabase"]
    token=os.environ.get("RIEGOBOT_COLLECTOR_TOKEN")
    if not token:raise RuntimeError("Set RIEGOBOT_COLLECTOR_TOKEN in this PC environment")
    endpoint=settings["url"].rstrip("/")+"/functions/v1/ingest"
    if not endpoint.startswith("https://") and not endpoint.startswith("http://127.0.0.1:"):raise RuntimeError("HTTPS is required")
    # Flush before extracting: unavailable network never loses already-staged rows.
    try:outbox.flush(endpoint,token)
    except Exception:logging.warning("Pending batches retained; retry after extraction")
    command=["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(PROJECT_ROOT/"scripts/EXPORT_TELEMETRY.ps1"),"-DatabaseRoot",str(root),"-Since",since]
    with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8") as proc:
        chunk=[]
        assert proc.stdout
        for line in proc.stdout:
            if not line.strip():continue
            row=normalized(json.loads(line),settings.get("timezone","America/Bogota"))
            if row["dream_id"] not in enabled:continue
            chunk.append(row)
            if len(chunk)>=250:outbox.stage(chunk,settings["collectorId"]);chunk=[]
        if chunk:outbox.stage(chunk,settings["collectorId"])
        stderr=proc.stderr.read() if proc.stderr else ""
        if proc.wait()!=0:raise RuntimeError("MDB extraction failed: "+stderr[-2000:])
    outbox.flush(endpoint,token)
    # Empty heartbeat also validates authorization and enabled Dreams server-side.
    payload=json.dumps({"batch_id":str(uuid.uuid4()),"collector_id":settings["collectorId"],"rows":[]}).encode()
    with urlopen(Request(endpoint,data=payload,headers={"Content-Type":"application/json","x-collector-token":token}),timeout=30) as r:r.read()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--since",help="Initial/history scan start YYYY-MM-DD")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    cfg=load_config(PROJECT_ROOT)
    if not cfg.get("readOnly",False):raise RuntimeError("readOnly must be true")
    outbox=Outbox(PROJECT_ROOT/"runtime/outbox.sqlite")
    while True:
        since=args.since or (datetime.now()-timedelta(days=cfg.get("supabase",{}).get("lookbackDays",2))).strftime("%Y-%m-%d")
        try:cycle(cfg,outbox,since);logging.info("Cycle completed")
        except Exception:
            logging.exception("Collector cycle failed; pending batches retained")
            if args.once:raise
        if args.once:break
        time.sleep(max(30,cfg.get("supabase",{}).get("intervalSeconds",60)))
if __name__=="__main__":main()
