"""Offline behavior tests; no generation or network calls."""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock

from PIL import Image

SPEC = importlib.util.spec_from_file_location("image_batch_pipeline", Path(__file__).resolve().parents[1] / "scripts/image_batch_pipeline.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        for i in range(1, 4):
            Image.new("RGB", (73+i, 101+i), (10*i, 40, 80)).save(self.base/f"book_{i:02d}.png")
        self.good = self.base/"good.png"
        self.other = self.base/"other.png"
        self.wrong = self.base/"wrong.png"
        Image.new("RGB", (90, 160), "blue").save(self.good)
        Image.new("RGB", (90, 160), "green").save(self.other)
        Image.new("RGB", (160, 90), "red").save(self.wrong)
        self.cfg = {"execution_mode":"replay", "concurrency":3,
                    "books":[{"id":f"book_{i:02d}","source":f"book_{i:02d}.png"} for i in range(1,4)],
                    "shots":[{"id":f"shot_{i:02d}","prompt":f"exact prompt {i}"} for i in range(1,4)]}
        self.config=self.base/"batch.json"
        p.write_json(self.config,self.cfg)
        self.run=self.base/"run"
        p.initialize(self.config,self.run)

    def tearDown(self):
        self.temp.cleanup()

    def receive(self, id, source=None):
        claim=p.start(self.run,id)
        p.ingest(self.run,id,claim["attempt"],source or self.good)
        return claim

    def complete(self):
        for i in [3,1,2]:
            self.receive(f"shot_{i:02d}", self.other if i==2 else self.good)

    def test_photo_layout_preserves_evidence_pixels_and_classification(self):
        result = p.import_photo(self.run, "shot_01", self.wrong, [10, 10, 150, 80])
        box = result["photo"]["content_box"]
        with Image.open(self.wrong) as source, Image.open(self.run/"images/shot_01.png") as output:
            self.assertEqual(output.crop(tuple(box)).tobytes(), source.convert("RGB").crop((10,10,150,80)).tobytes())
        self.assertEqual((self.run/result["photo"]["path"]).read_bytes(), self.wrong.read_bytes())
        self.receive("shot_02")
        self.receive("shot_03")
        p.finalize(self.run)
        manifest = json.loads((self.run/"manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["generation_records"][0]["kind"], "photograph_layout")
        self.assertTrue(p.verify(self.run)["verified"])

    def test_photo_import_rejects_invalid_crop_without_claim(self):
        with self.assertRaisesRegex(ValueError, "crop"):
            p.import_photo(self.run, "shot_01", self.wrong, [-1,0,20,20])
        self.assertEqual(len(p.plan(self.run)["pending"]), 3)

    def test_out_of_order_identity_books_zip_and_freeze(self):
        self.complete()
        report=p.finalize(self.run)
        self.assertEqual(report["measurement_mode"],"replay")
        self.assertEqual(report["T2"]["elapsed_seconds"],0)
        self.assertTrue(report["T3"]["target_met"])
        self.assertEqual(p.verify(self.run)["shot_count"],3)
        self.assertEqual(p.finalize(self.run)["zip_sha256"],report["zip_sha256"])
        with Image.open(self.run/"images/shot_02.png") as im:
            self.assertEqual(im.size,(1080,1920))
            self.assertEqual(im.getpixel((500,500)),(0,128,0))
        for i in range(1,4):
            name=f"book_{i:02d}.png"
            self.assertEqual((self.run/"books"/name).read_bytes(),(self.base/name).read_bytes())
        with zipfile.ZipFile(self.run/"images.zip") as z:
            self.assertIn("manifest.json",z.namelist())
            self.assertNotIn("state.db",z.namelist())
            self.assertNotIn("timing.json",z.namelist())
        with self.assertRaisesRegex(ValueError,"frozen"):
            p.start(self.run,"shot_01",True)

    def test_missing_bad_ratio_and_partial_resume(self):
        self.receive("shot_01")
        with self.assertRaisesRegex(ValueError,"incomplete ZIP"):
            p.finalize(self.run)
        c=p.start(self.run,"shot_02")
        with self.assertRaisesRegex(ValueError,"aspect ratio"):
            p.ingest(self.run,"shot_02",c["attempt"],self.wrong)
        p.fail(self.run,"shot_02",c["attempt"],"archive_failed")
        p.start(self.run,"shot_03")
        with self.assertRaisesRegex(ValueError,"reset-inflight"):
            p.resume(self.run)
        resumed=p.resume(self.run,True)
        self.assertEqual(resumed["archived"],["shot_01"])
        self.assertEqual([j["id"] for j in resumed["pending"]],["shot_02","shot_03"])
        for id in ["shot_02","shot_03"]:self.receive(id)
        self.assertEqual(p.finalize(self.run)["failed_attempts"],1)

    def test_duplicate_stale_claim_and_repair_preserves_original(self):
        c=self.receive("shot_01")
        self.assertTrue(p.ingest(self.run,"shot_01",c["attempt"],self.good)["duplicate"])
        with self.assertRaisesRegex(ValueError,"different result"):
            p.ingest(self.run,"shot_01",c["attempt"],self.other)
        repair=p.start(self.run,"shot_01",True)
        with self.assertRaisesRegex(ValueError,"stale attempt"):
            p.ingest(self.run,"shot_01",c["attempt"],self.good)
        p.ingest(self.run,"shot_01",repair["attempt"],self.other)
        self.assertEqual((self.run/"originals/shot_01_v001.png").read_bytes(),self.good.read_bytes())
        self.assertEqual((self.run/"originals/shot_01_v002.png").read_bytes(),self.other.read_bytes())
        for id in ["shot_02","shot_03"]:self.receive(id)
        report=p.finalize(self.run)
        self.assertEqual(report["T2"]["repair_count"],1)
        self.assertGreaterEqual(report["T2"]["elapsed_seconds"],0)

    def test_repair_failure_must_be_explicitly_resolved(self):
        self.complete()
        c=p.start(self.run,"shot_01",True)
        p.fail(self.run,"shot_01",c["attempt"],"generation_failed")
        with self.assertRaisesRegex(ValueError,"Unfinished repair"):
            p.resume(self.run,True)
        c=p.repair_recovery(self.run,"shot_01")
        p.ingest(self.run,"shot_01",c["attempt"],self.other)
        self.assertEqual(p.finalize(self.run)["T2"]["repair_count"],2)

    def test_explicit_restore_and_tamper_detection(self):
        self.complete()
        p.start(self.run,"shot_01",True)
        # Simulate a process interruption after writing the repaired export.
        Image.new("RGB",(1080,1920),"red").save(self.run/"images/shot_01.png")
        p.repair_recovery(self.run,"shot_01",restore=True)
        p.finalize(self.run)
        (self.run/"books/book_01.png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"checksum"):
            p.verify(self.run)

    def test_concurrent_claim_has_single_winner(self):
        def claim(_):
            try:return p.start(self.run,"shot_01")["claimed"]
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            self.assertEqual(sum(pool.map(claim,range(3))),1)

    def test_publish_to_bound_project_name_and_refuse_overwrite(self):
        c=p.start(self.run,"shot_01")
        target=self.base/"project/assets"
        p.ingest(self.run,"shot_01",c["attempt"],self.good,publish_dir=target,publish_name="shot_12.png")
        self.assertEqual(p.sha(target/"shot_12.png"),p.sha(self.run/"images/shot_01.png"))
        c=p.start(self.run,"shot_02")
        with self.assertRaisesRegex(ValueError,"already differs"):
            p.ingest(self.run,"shot_02",c["attempt"],self.other,publish_dir=target,publish_name="shot_12.png")
        self.assertEqual(p.plan(self.run)["active"],["shot_02"])
        repair=p.start(self.run,"shot_01",True)
        p.ingest(self.run,"shot_01",repair["attempt"],self.other,publish_dir=target,publish_name="shot_12.png")
        self.assertEqual(p.sha(target/"shot_12.png"),p.sha(self.run/"images/shot_01.png"))
        self.assertNotEqual(p.sha(target/"revisions/shot_12_v001.png"),p.sha(target/"shot_12.png"))

    def test_automatic_publication_from_frozen_config(self):
        with p.database(self.run) as db:
            cfg=p.meta(db)['config']
            cfg['shots'][0]['delivery_path']='p1/assets/shot_12.png'
            p.put(db,'config',cfg)
        claim=p.start(self.run,'shot_01')
        with mock.patch.object(p,'REPO_ROOT',self.base):
            p.ingest(self.run,'shot_01',claim['attempt'],self.good)
        self.assertEqual(p.sha(self.base/'p1/assets/shot_12.png'),p.sha(self.run/'images/shot_01.png'))

    def test_bad_config_does_not_create_run(self):
        dest=self.base/"other_run"
        self.cfg["shots"][1]["id"]="shot_01"
        p.write_json(self.config,self.cfg)
        with self.assertRaisesRegex(ValueError,"Unique"):
            p.initialize(self.config,dest)
        self.assertFalse(dest.exists())
        with self.assertRaisesRegex(ValueError,"escapes"):
            p.inside(self.run,"../outside")

    def test_multi_project_delivery_reuse_and_original_shot_numbers(self):
        self.complete()
        slots=[{'project':'p1','shot':f'shot_{i:02d}','target':f'p1/assets/shot_{i:02d}.png',
                'kind':'generated','generation_id':f'shot_{i:02d}'} for i in range(1,4)]
        slots += [{'project':'p1','shot':'shot_09','target':'p1/assets/shot_09.png','kind':'book','source':'book_01.png'},
                  {'project':'p2','shot':'shot_12','target':'p2/assets/shot_12.png','kind':'reuse','source':'p1/assets/shot_01.png'}]
        with p.database(self.run) as db:
            cfg=p.meta(db)['config'];cfg['delivery_slots']=slots;p.put(db,'config',cfg)
        with mock.patch.object(p,'REPO_ROOT',self.base):
            p.finalize(self.run)
        self.assertEqual(p.sha(self.base/'p2/assets/shot_12.png'),p.sha(self.run/'images/shot_01.png'))
        self.assertEqual((self.base/'p1/assets/shot_09.png').read_bytes(),(self.base/'book_01.png').read_bytes())
        with zipfile.ZipFile(self.run/'images.zip') as z:
            self.assertIn('delivery/p2/shot_12.png',z.namelist())
            self.assertNotIn('images/shot_01.png',z.namelist())
        self.assertTrue(p.verify(self.run)['verified'])

    def test_backup_is_separate_and_never_zeroed(self):
        self.complete()
        report=p.finalize(self.run)
        local=report["T3"].copy()
        end=p.now()
        updated=p.record_backup(self.run,report["T3"]["finished_at"],end)
        self.assertEqual(updated["T3"],local)
        self.assertIsNotNone(updated["backup"])
        self.assertGreaterEqual(updated["total_through_backup_seconds"],updated["total_to_local_seconds"])


if __name__ == "__main__":unittest.main()
