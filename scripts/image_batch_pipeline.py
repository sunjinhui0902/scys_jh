"""Incremental image delivery. Generation stays in the Codex tool session."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone, timedelta
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

SCHEMA_VERSION = 1
SHOT_ID = re.compile(r"shot_\d{2,4}\Z")
REPO_ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    if dt > datetime.now(timezone.utc) + timedelta(seconds=5):
        raise ValueError("Timestamp is in the future")
    return dt


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def inside(root, rel):
    if Path(rel).is_absolute():
        raise ValueError("Output paths must be relative")
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError("Output path escapes run directory")
    return p


def database(root):
    if not (root / "state.db").is_file():
        raise ValueError("Run not initialized")
    db = sqlite3.connect(root / "state.db", timeout=30)
    db.row_factory = sqlite3.Row
    return db


def meta(db):
    return {r[0]: json.loads(r[1]) for r in db.execute("SELECT key,value FROM meta")}


def put(db, key, value):
    db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))


def mutable(db):
    if meta(db).get("finalized_at"):
        raise ValueError("Finalized run is frozen; create a new run for revisions")


def initialize(config_path, root):
    config_path, root = Path(config_path).resolve(), Path(root).resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    jobs = cfg.get("shots", [])
    if not jobs:
        raise ValueError("shots must be nonempty")
    ids = [j["id"] for j in jobs]
    if len(ids) != len(set(ids)) or any(not SHOT_ID.fullmatch(s) for s in ids):
        raise ValueError("Unique shot_NN identifiers required")
    if ids != [f"shot_{i:02d}" for i in range(1, len(jobs) + 1)]:
        raise ValueError("Shots must be ordered and contiguous from shot_01")
    if any(not isinstance(j.get("prompt"), str) or not j["prompt"].strip()
           or j["prompt"].startswith("REPLACE_") for j in jobs):
        raise ValueError("Every shot needs its final individual prompt")
    size = cfg.get("target_size", [1080, 1920])
    if size != [1080, 1920]:
        raise ValueError("This delivery standard requires 1080x1920")
    if cfg.get("execution_mode", "live") not in {"live", "replay"}:
        raise ValueError("execution_mode must be live or replay")
    tolerance = cfg.get("aspect_tolerance", 0.01)
    if not isinstance(tolerance, (int, float)) or not 0 <= tolerance <= 0.02:
        raise ValueError("aspect_tolerance must be between 0 and 0.02")
    if type(cfg.get("concurrency", 3)) is not int or not 1 <= cfg.get("concurrency", 3) <= 4:
        raise ValueError("concurrency must be an integer from 1 to 4")
    books = cfg.get("books", [])
    if [b.get("id") for b in books] != ["book_01", "book_02", "book_03"]:
        raise ValueError("Exactly book_01, book_02, book_03 are required")
    checked = []
    for book in books:
        src = (config_path.parent / book["source"]).resolve()
        if src.suffix.lower() != ".png":
            raise ValueError("Preserved book sources must be PNG, no disguised conversion")
        with Image.open(src) as im:
            im.load()
            if im.format != "PNG":
                raise ValueError("Book source must actually be PNG")
            dims = list(im.size)
        checked.append((book, src, dims, sha(src)))
    # Validate before creating anything. Existing runs are never reinitialized.
    root.mkdir(parents=True, exist_ok=False)
    try:
        (root / "books").mkdir()
        (root / "images").mkdir()
        (root / "originals").mkdir()
        (root / "thumbnails").mkdir()
        book_records = []
        for book, src, dims, digest in checked:
            dest = root / "books" / (book["id"] + ".png")
            shutil.copy2(src, dest)
            if sha(dest) != digest:
                raise ValueError("Book copy checksum mismatch")
            book_records.append({"path": dest.relative_to(root).as_posix(), "kind": "provided_book",
                                 "size": dest.stat().st_size, "sha256": digest, "dimensions": dims,
                                 "source_name": src.name, "preserved_bytes": True})
        write_json(root / "prompts.json", {"shots": jobs})
        db = sqlite3.connect(root / "state.db")
        with db:
            db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("""CREATE TABLE shots(id TEXT PRIMARY KEY,ordinal INTEGER,prompt TEXT,
                status TEXT,attempt INTEGER DEFAULT 0,initial_received_at TEXT,selected_received_at TEXT,
                current_path TEXT,native_path TEXT,sha256 TEXT,native_sha256 TEXT,
                width INTEGER,height INTEGER,error TEXT)""")
            for i, job in enumerate(jobs):
                db.execute("INSERT INTO shots(id,ordinal,prompt,status) VALUES (?,?,?,'pending')",
                           (job["id"], i, job["prompt"]))
            for k, v in {"schema_version": SCHEMA_VERSION, "created_at": now(), "config": cfg,
                         "books": book_records, "repairs": [], "failed_attempts": []}.items():
                put(db, k, v)
        db.close()
    except Exception:
        # Leave partial files for diagnosis; never remove a user-supplied directory.
        raise
    return {"run_dir": str(root), "shot_count": len(jobs), "books_copied": 3}


def plan(root):
    with database(root) as db:
        m = meta(db)
        rows = [dict(r) for r in db.execute("SELECT * FROM shots ORDER BY ordinal")]
        return {"execution_mode": m["config"].get("execution_mode", "live"),
                "concurrency": m["config"].get("concurrency", 3), "finalized": bool(m.get("finalized_at")),
                "pending": [{"id": r["id"], "prompt": r["prompt"]} for r in rows if r["status"] == "pending"],
                "active": [r["id"] for r in rows if r["status"] in {"running", "repairing"}],
                "failed": [r["id"] for r in rows if r["status"] in {"failed", "repair_failed"}],
                "archived": [r["id"] for r in rows if r["status"] == "archived"], "total": len(rows)}


def start(root, shot_id, repair=False):
    db = database(root)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            mutable(db)
            row = db.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown shot id")
            if not repair and row["status"] == "archived":
                return {"claimed": False, "id": shot_id}
            expected = {"archived"} if repair else {"pending"}
            if row["status"] not in expected:
                raise ValueError("Shot cannot be submitted in its current state")
            attempt, at = row["attempt"] + 1, now()
            db.execute("UPDATE shots SET status=?,attempt=?,error=NULL WHERE id=?",
                       ("repairing" if repair else "running", attempt, shot_id))
            m = meta(db)
            if not repair and not m.get("first_submitted_at"):
                put(db, "first_submitted_at", at)
            if repair:
                repairs = m["repairs"]
                repairs.append({"id": shot_id, "attempt": attempt, "started_at": at, "received_at": None})
                put(db, "repairs", repairs)
            return {"claimed": True, "id": shot_id, "attempt": attempt,
                    "phase": "repair" if repair else "initial", "submitted_at": at}
    finally:
        db.close()


def fail(root, shot_id, attempt, error):
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        mutable(db)
        row = db.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone()
        if row is None or row["attempt"] != attempt or row["status"] not in {"running", "repairing"}:
            raise ValueError("Stale or inactive failure report")
        status = "repair_failed" if row["status"] == "repairing" else "failed"
        # Do not persist SDK errors or source paths: they can contain credentials.
        code = error if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", error) else "external_failure"
        db.execute("UPDATE shots SET status=?,error=? WHERE id=?", (status, code, shot_id))
        m = meta(db)
        failures = m["failed_attempts"]
        failures.append({"id": shot_id, "attempt": attempt, "at": now(), "phase": status})
        put(db, "failed_attempts", failures)
    return {"id": shot_id, "status": status}


def ingest(root, shot_id, attempt, source, received_at=None, publish_dir=None, publish_name=None):
    source, at = Path(source).resolve(), received_at or now()
    timestamp(at)
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        mutable(db)
        row = db.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone()
        if row is None or attempt != row["attempt"]:
            raise ValueError("Unknown shot or stale attempt")
        digest = sha(source)
        if row["status"] == "archived" and row["native_sha256"] == digest:
            if sha(inside(root, row["current_path"])) != row["sha256"]:
                raise ValueError("Archived delivery image changed")
            return {"id": shot_id, "status": "archived", "duplicate": True}
        if row["status"] not in {"running", "repairing"}:
            raise ValueError("Shot was not submitted or already has a different result")
        m = meta(db)
        if publish_dir is None:
            job = next(j for j in m["config"]["shots"] if j["id"] == shot_id)
            if job.get("delivery_path"):
                destination = inside(REPO_ROOT, job["delivery_path"])
                publish_dir, publish_name = destination.parent, destination.name
        if timestamp(at) < timestamp(m["first_submitted_at"]):
            raise ValueError("Result timestamp precedes first submission")
        with Image.open(source) as im:
            im.load()
            width, height = im.size
            target = (1080, 1920)
            deviation = abs((width / height) / (9 / 16) - 1)
            if deviation > m["config"].get("aspect_tolerance", 0.01):
                raise ValueError("Image aspect ratio outside tolerance; no automatic large crop")
            native = root / "originals" / f"{shot_id}_v{attempt:03d}.png"
            if im.format != "PNG":
                raise ValueError("Generated source must be a PNG")
            if native.exists():
                if sha(native) != digest:
                    raise ValueError("Existing original differs; refusing overwrite")
            else:
                shutil.copy2(source, native)
            # Keep the original bytes. Only export sizing is performed locally.
            image = ImageOps.fit(im.convert("RGB"), target, Image.Resampling.LANCZOS)
        output = root / "images" / f"{shot_id}.png"
        if output.exists() and row["status"] != "repairing":
            # Resume after a crash between file write and DB commit only if identical.
            with Image.open(output) as existing:
                if existing.size != image.size or existing.convert("RGB").tobytes() != image.tobytes():
                    raise ValueError("Existing delivery image differs; refusing overwrite")
        fd, temp = tempfile.mkstemp(suffix=".png", dir=root / "images")
        os.close(fd)
        try:
            image.save(temp, format="PNG", compress_level=3)
            os.replace(temp, output)
        finally:
            Path(temp).unlink(missing_ok=True)
        thumb = ImageOps.contain(image, (180, 320), Image.Resampling.LANCZOS)
        thumb.save(root / "thumbnails" / f"{shot_id}.jpg", quality=85)
        if sha(source) != digest or sha(native) != digest:
            raise ValueError("Source changed during archive")
        if publish_dir is not None:
            name = publish_name or (shot_id + ".png")
            if not re.fullmatch(r"shot_\d{2,4}\.png", name):
                raise ValueError("Published image must use a shot_NN.png filename")
            destination = Path(publish_dir).resolve() / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            exported_sha = sha(output)
            replace_selected = False
            if destination.exists() and sha(destination) != exported_sha:
                if row["status"] != "repairing" or sha(destination) != row["sha256"]:
                    raise ValueError("Published image already differs; preserve it and use a new batch")
                historical = destination.parent / "revisions" / f"{Path(name).stem}_v{attempt-1:03d}.png"
                historical.parent.mkdir(exist_ok=True)
                if historical.exists() and sha(historical) != row["sha256"]:
                    raise ValueError("Existing published revision differs")
                if not historical.exists():
                    shutil.copy2(destination, historical)
                replace_selected = True
            if not destination.exists() or replace_selected:
                fd, published_temp = tempfile.mkstemp(suffix=".png", dir=destination.parent)
                os.close(fd)
                try:
                    shutil.copy2(output, published_temp)
                    if sha(Path(published_temp)) != exported_sha:
                        raise ValueError("Published copy checksum mismatch")
                    os.replace(published_temp, destination)
                finally:
                    Path(published_temp).unlink(missing_ok=True)
        db.execute("""UPDATE shots SET status='archived',initial_received_at=COALESCE(initial_received_at,?),
            selected_received_at=?,current_path=?,native_path=?,sha256=?,native_sha256=?,width=?,height=?,error=NULL
            WHERE id=?""", (at, at, output.relative_to(root).as_posix(), native.relative_to(root).as_posix(),
                             sha(output), digest, width, height, shot_id))
        if row["status"] == "repairing":
            repairs = m["repairs"]
            next(r for r in repairs if r["id"] == shot_id and r["attempt"] == attempt)["received_at"] = at
            put(db, "repairs", repairs)
    return {"id": shot_id, "status": "archived", "attempt": attempt, "dimensions": [1080, 1920]}


def resume(root, reset_inflight=False):
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        mutable(db)
        if not reset_inflight and db.execute("SELECT 1 FROM shots WHERE status IN ('running','repairing')").fetchone():
            raise ValueError("Confirm previous submissions stopped with --reset-inflight")
        # Repair failure must not silently select the older image as final.
        if db.execute("SELECT 1 FROM shots WHERE status IN ('repairing','repair_failed')").fetchone():
            raise ValueError("Unfinished repair: explicitly retry-repair or restore-selected")
        db.execute("UPDATE shots SET status='pending',error=NULL WHERE status IN ('failed','running')")
    return plan(root)


def repair_recovery(root, shot_id, restore=False):
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        mutable(db)
        row = db.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone()
        if row is None or row["status"] not in {"repairing", "repair_failed"}:
            raise ValueError("No unfinished repair for this shot")
        if restore and sha(inside(root, row["current_path"])) != row["sha256"]:
            # Recover a crash after replacement but before the DB transaction committed.
            native = inside(root, row["native_path"])
            if sha(native) != row["native_sha256"]:
                raise ValueError("Selected original changed; cannot restore")
            output = inside(root, row["current_path"])
            with Image.open(native) as im:
                image = ImageOps.fit(im.convert("RGB"), (1080, 1920), Image.Resampling.LANCZOS)
                fd, temp = tempfile.mkstemp(suffix=".png", dir=root / "images")
                os.close(fd)
                try:
                    image.save(temp, format="PNG", compress_level=3)
                    if sha(Path(temp)) != row["sha256"]:
                        raise ValueError("Restored export differs; preserve both versions")
                    os.replace(temp, output)
                finally:
                    Path(temp).unlink(missing_ok=True)
        if restore:
            with Image.open(inside(root, row["current_path"])) as im:
                ImageOps.contain(im.convert("RGB"), (180, 320), Image.Resampling.LANCZOS).save(
                    root / "thumbnails" / f"{shot_id}.jpg", quality=85)
        db.execute("UPDATE shots SET status='archived',error=NULL WHERE id=?", (shot_id,))
        m = meta(db)
        for r in m["repairs"]:
            if r["id"] == shot_id and not r.get("received_at") and not r.get("cancelled_at"):
                r["cancelled_at"] = now()
        put(db, "repairs", m["repairs"])
    return {"restored_selected": shot_id} if restore else start(root, shot_id, repair=True)


def timing(m, rows, completed_at):
    first = m["first_submitted_at"]
    initial = max((r["initial_received_at"] for r in rows), key=timestamp)
    final = max((r["selected_received_at"] for r in rows), key=timestamp)
    repairs = m["repairs"]
    ends = [r.get("received_at") or r.get("cancelled_at") for r in repairs]
    if repairs and not all(ends):
        raise ValueError("Unfinished repair prevents timing and finalization")
    elapsed = lambda a, b: round((timestamp(b) - timestamp(a)).total_seconds(), 3)
    result = {
        "measurement_mode": m["config"].get("execution_mode", "live"),
        "T1": {"started_at": first, "finished_at": initial, "elapsed_seconds": elapsed(first, initial)},
        "T2": {"started_at": min((r["started_at"] for r in repairs), key=timestamp) if repairs else None,
               "finished_at": max(ends, key=timestamp) if repairs else None,
               "elapsed_seconds": elapsed(min((r["started_at"] for r in repairs), key=timestamp), max(ends, key=timestamp)) if repairs else 0,
               "repair_count": len(repairs)},
        "T3": {"started_at": final, "finished_at": completed_at,
               "elapsed_seconds": elapsed(final, completed_at), "target_seconds": 60,
               "target_met": elapsed(final, completed_at) < 60},
        "created_at": m["created_at"],
        "total_to_local_seconds": elapsed(m["created_at"], completed_at),
        "failed_attempts": len(m["failed_attempts"]),
        "backup": m.get("backup"),
        "note": "Wall-clock stage spans may overlap. Replay is not a generation benchmark. Backup is separate.",
    }
    if m.get("backup"):
        result["total_through_backup_seconds"] = elapsed(m["created_at"], m["backup"]["finished_at"])
    return result


def assemble_delivery(root, m, generated):
    """Optional multi-project delivery, including explicitly configured reused shots."""
    slots = m["config"].get("delivery_slots")
    if not slots:
        return None
    by_id = {Path(r["path"]).stem: r for r in generated}
    specified = [s["generation_id"] for s in slots if s["kind"] == "generated"]
    if len(specified) != len(set(specified)) or set(specified) != set(by_id):
        raise ValueError("Delivery mapping must bind every generated image exactly once")
    book_hashes = {b["sha256"] for b in m["books"]}
    records, projects = [], {}
    def copy_exact(source, target):
        digest = sha(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha(target) != digest:
                raise ValueError("Delivery target differs; refusing overwrite: " + target.name)
        else:
            shutil.copy2(source, target)
        if sha(target) != digest:
            raise ValueError("Delivery copy checksum mismatch")
        return digest
    for slot in slots:
        if not SHOT_ID.fullmatch(slot["shot"]):
            raise ValueError("Invalid delivery shot identity")
        target = inside(REPO_ROOT, slot["target"])
        if target.name != slot["shot"] + ".png":
            raise ValueError("Delivery target filename differs from shot identity")
        if slot["kind"] == "generated":
            source = inside(root, by_id[slot["generation_id"]]["path"])
        elif slot["kind"] in {"reuse", "book"}:
            source = inside(REPO_ROOT, slot["source"])
        else:
            raise ValueError("Unknown delivery source kind")
        if slot["kind"] == "book" and sha(source) not in book_hashes:
            raise ValueError("Book source changed since initialization")
        digest = copy_exact(source, target)
        snapshot = inside(root, "delivery/" + slot["project"] + "/" + target.name)
        copy_exact(target, snapshot)
        with Image.open(snapshot) as im:
            dimensions = list(im.size)
        if slot["kind"] != "book" and dimensions != [1080, 1920]:
            raise ValueError("AI delivery must be 1080x1920")
        ref = {"path": snapshot.relative_to(root).as_posix(), "kind": slot["kind"],
               "delivery_target": slot["target"], "sha256": digest,
               "size": snapshot.stat().st_size, "dimensions": dimensions,
               "generation_id": slot.get("generation_id"), "reuse_source": slot.get("source")}
        records.append(ref)
        projects.setdefault(slot["project"], []).append(ref)
    for project, items in projects.items():
        folder = inside(root, "delivery/" + project)
        preview = Image.new("RGB", (800, math.ceil(len(items)/4)*360), "#f4f1e9")
        draw = ImageDraw.Draw(preview)
        for i, ref in enumerate(items):
            with Image.open(inside(root, ref["path"])) as im:
                thumb = ImageOps.contain(im.convert("RGB"), (180, 320), Image.Resampling.LANCZOS)
                x, y = (i%4)*200, (i//4)*360
                preview.paste(thumb, (x+(200-thumb.width)//2, y+8+(320-thumb.height)//2))
                draw.text((x+10,y+334),Path(ref["path"]).stem,fill="#252525")
        preview.save(folder/"preview.jpg", quality=90)
        write_json(folder/"manifest.json", {"project": project, "files": items})
        target_folder = inside(REPO_ROOT, items[0]["delivery_target"]).parent
        for name in ["preview.jpg", "manifest.json"]:
            artifact = folder/name
            copy_exact(artifact, target_folder/(Path(name).stem+"_"+root.name+Path(name).suffix))
            records.append({"path":artifact.relative_to(root).as_posix(),"kind":"project_support",
                            "sha256":sha(artifact),"size":artifact.stat().st_size})
    return records


def finalize(root):
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        m = meta(db)
        if m.get("finalized_at"):
            verify(root)
            return json.loads((root / "timing.json").read_text(encoding="utf-8"))
        rows = [dict(r) for r in db.execute("SELECT * FROM shots ORDER BY ordinal")]
        if any(r["status"] != "archived" for r in rows):
            raise ValueError("Missing, failed, or active shots; refusing incomplete ZIP")
        for r in rows:
            if sha(inside(root, r["current_path"])) != r["sha256"]:
                raise ValueError("Delivery image changed since ingest")
        for b in m["books"]:
            if sha(inside(root, b["path"])) != b["sha256"]:
                raise ValueError("Preserved book changed")
        # Validate repair closure before writing any final artifacts.
        timing(m, rows, now())
        cols = min(6, len(rows) + 3)
        count = len(rows) + 3
        sheet = Image.new("RGB", (cols * 200, math.ceil(count / cols) * 360), "#f4f1e9")
        draw, font = ImageDraw.Draw(sheet), ImageFont.load_default()
        items = [(r["id"], root / "thumbnails" / (r["id"] + ".jpg")) for r in rows]
        items += [(Path(b["path"]).stem, inside(root, b["path"])) for b in m["books"]]
        for i, (label, p) in enumerate(items):
            x, y = (i % cols) * 200, (i // cols) * 360
            with Image.open(p) as im:
                thumbnail = ImageOps.contain(im.convert("RGB"), (180, 320), Image.Resampling.LANCZOS)
                sheet.paste(thumbnail, (x + (200 - thumbnail.width) // 2, y + 8 + (320 - thumbnail.height) // 2))
            draw.text((x + 10, y + 334), label, fill="#252525", font=font)
        sheet.save(root / "preview.jpg", quality=90)
        files = [{"path": r["current_path"], "kind": "AI_atmosphere", "sha256": r["sha256"],
                  "size": inside(root, r["current_path"]).stat().st_size, "dimensions": [1080, 1920],
                  "native_dimensions": [r["width"], r["height"]], "native_sha256": r["native_sha256"]} for r in rows]
        generation_records = files.copy()
        delivery = assemble_delivery(root, m, generation_records)
        files = delivery if delivery is not None else files + m["books"]
        for name in ["preview.jpg", "prompts.json"] + (["README.md"] if (root/"README.md").exists() else []):
            p = root / name
            files.append({"path": name, "kind": "support", "sha256": sha(p), "size": p.stat().st_size})
        manifest = {"schema_version": SCHEMA_VERSION, "shot_count": len(rows), "book_count": 3,
                    "measurement_mode": m["config"].get("execution_mode", "live"), "files": files,
                    "generation_records": generation_records}
        write_json(root / "manifest.json", manifest)
        archive, tmp = root / "images.zip", root / "images.zip.partial"
        if archive.exists():
            raise ValueError("Unregistered ZIP exists; preserve it and investigate before continuing")
        # PNG/JPEG are already compressed. Store them to avoid costly recompression.
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for r in files:
                z.write(inside(root, r["path"]), r["path"])
            z.write(root / "manifest.json", "manifest.json")
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None:
                raise ValueError("ZIP CRC failure")
            for r in files:
                h = hashlib.sha256()
                with z.open(r["path"]) as f:
                    for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                        h.update(chunk)
                if h.hexdigest() != r["sha256"]:
                    raise ValueError("ZIP entry checksum mismatch")
        digest = sha(tmp)
        os.replace(tmp, archive)
        (root / "zip_sha256.txt").write_text(digest + "  images.zip\n", encoding="utf-8")
        done = now()
        result = timing(m, rows, done)
        result["zip_sha256"] = digest
        result["zip_size"] = archive.stat().st_size
        write_json(root / "timing.json", result)
        put(db, "finalized_at", done)
        put(db, "final_manifest_sha256", sha(root / "manifest.json"))
        return result


def verify(root):
    with database(root) as db:
        expected_manifest = meta(db).get("final_manifest_sha256")
    if expected_manifest and sha(root / "manifest.json") != expected_manifest:
        raise ValueError("Frozen manifest checksum mismatch")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for r in manifest["files"]:
        p = inside(root, r["path"])
        if sha(p) != r["sha256"]:
            raise ValueError("Manifest checksum mismatch: " + r["path"])
    expected = (root / "zip_sha256.txt").read_text(encoding="utf-8").split()[0]
    if sha(root / "images.zip") != expected:
        raise ValueError("ZIP checksum mismatch")
    with zipfile.ZipFile(root / "images.zip") as z:
        if z.testzip() is not None or z.read("manifest.json") != (root / "manifest.json").read_bytes():
            raise ValueError("ZIP manifest or CRC mismatch")
    return {"verified": True, "shot_count": manifest["shot_count"], "book_count": manifest["book_count"]}


def record_backup(root, started_at, finished_at):
    if timestamp(finished_at) < timestamp(started_at):
        raise ValueError("Negative backup duration")
    with database(root) as db:
        m = meta(db)
        if not m.get("finalized_at"):
            raise ValueError("Finish local delivery before recording backup")
        if timestamp(finished_at) < timestamp(m["finalized_at"]):
            raise ValueError("Backup completion cannot precede local delivery")
        backup = {"started_at": started_at, "finished_at": finished_at,
                  "elapsed_seconds": round((timestamp(finished_at) - timestamp(started_at)).total_seconds(), 3)}
        put(db, "backup", backup)
        report = json.loads((root / "timing.json").read_text(encoding="utf-8"))
        report["backup"] = backup
        report["total_through_backup_seconds"] = round((timestamp(finished_at) - timestamp(m["created_at"])).total_seconds(), 3)
        write_json(root / "timing.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, required=True)
    for name in ["plan", "start", "start-repair", "ingest", "fail", "resume", "retry-repair", "restore-selected", "finalize", "verify", "record-backup"]:
        p = sub.add_parser(name)
        p.add_argument("--run-dir", type=Path, required=True)
        if name in {"start", "start-repair", "ingest", "fail", "retry-repair", "restore-selected"}:
            p.add_argument("--shot-id", required=True)
        if name in {"ingest", "fail"}:
            p.add_argument("--attempt", type=int, required=True)
        if name == "ingest":
            p.add_argument("--source", type=Path, required=True)
            p.add_argument("--received-at")
            p.add_argument("--publish-dir", type=Path)
            p.add_argument("--publish-name")
        if name == "fail":
            p.add_argument("--error", default="generation_or_archive_failed")
        if name == "resume":
            p.add_argument("--reset-inflight", action="store_true")
        if name == "record-backup":
            p.add_argument("--started-at", required=True)
            p.add_argument("--finished-at", required=True)
    a = parser.parse_args(argv)
    root = a.run_dir.resolve()
    try:
        if a.command == "init": result = initialize(a.config, root)
        elif a.command == "plan": result = plan(root)
        elif a.command in {"start", "start-repair"}: result = start(root, a.shot_id, a.command == "start-repair")
        elif a.command == "ingest": result = ingest(root, a.shot_id, a.attempt, a.source, a.received_at, a.publish_dir, a.publish_name)
        elif a.command == "fail": result = fail(root, a.shot_id, a.attempt, a.error)
        elif a.command == "resume": result = resume(root, a.reset_inflight)
        elif a.command in {"retry-repair", "restore-selected"}: result = repair_recovery(root, a.shot_id, a.command == "restore-selected")
        elif a.command == "finalize": result = finalize(root)
        elif a.command == "verify": result = verify(root)
        else: result = record_backup(root, a.started_at, a.finished_at)
        print(json.dumps(result, ensure_ascii=False))
        if a.command == "finalize":
            for key, label in [("T1", "初版出齐耗时"), ("T2", "修图耗时"), ("T3", "归档打包耗时")]:
                phase = result[key]
                print(f"[{key}: {label}] {phase['elapsed_seconds']:.3f}秒 | {phase['started_at']} → {phase['finished_at']}", file=sys.stderr)
        return 0
    except Exception as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
