import tempfile,unittest
from pathlib import Path
from dreamreader.collector import Outbox,normalized
from dreamreader.discovery import discover_dreams
class CollectorTests(unittest.TestCase):
    def test_durable_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"outbox.sqlite";o=Outbox(p)
            row=normalized({"dream_id":"11","entity":"LastWM","source_at":"2026-09-02T14:00:00","data":{"ValueA":12}},"UTC")
            self.assertEqual(o.stage([row],"c"),1);self.assertEqual(o.stage([row],"c"),0)
            o.db.close();o=Outbox(p)
            self.assertEqual(o.db.execute("select count(*) from outbox").fetchone()[0],1);o.db.close()
    def test_mutable_observation_has_stable_identity_and_changed_revision(self):
        a=normalized({"dream_id":"11","entity":"LastWM","source_at":"2026-09-02T14:00:00","data":{"ObjSubType":22,"ObjNum":1,"ValueA":12}},"UTC")
        b=normalized({"dream_id":"11","entity":"LastWM","source_at":"2026-09-02T14:01:00","data":{"ObjSubType":22,"ObjNum":1,"ValueA":15}},"UTC")
        self.assertEqual(a["source_key"],b["source_key"])
        self.assertNotEqual(a["revision_key"],b["revision_key"])
    def test_missing_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg={"collector":{"siteId":"S","collectorId":"C"},"discovery":{"rootPath":tmp,"dreamPattern":"Dream*_1.mdb"},"dreams":[{"dreamId":"11"},{"dreamId":"13","enabled":False}]}
            result=discover_dreams(Path(tmp),cfg)
            self.assertEqual([r["status"] for r in result],["UNKNOWN","DISABLED"])
if __name__=="__main__":unittest.main()
