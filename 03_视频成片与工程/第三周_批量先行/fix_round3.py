#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 3 revisions: D1早 (strict binding + 6 pauses), D5午/D5晚/D6早/D6午/D7早, and full report corrections."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_批量先行"))
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_D1验证"))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402
from assemble_week3_all import (  # noqa: E402
    ASSETS_DIR, GEN_IMG_DIR, OUT_DIR, PREP_DIR, SUB_FONT_SIZE, VER_DIR,
    build_standard_shots, insert_book_window, render_episode, split_alternating,
)

FFMPEG = get_ffmpeg()


def fix_subtitles_round3() -> None:
    """Apply exact Round 3 subtitle line-break fixes for D5午, D5晚, D6早, D6午."""
    replacements = {
        ("D5午", "A03"): [
            "它了不起的地方",
            "就在于这几个小券：",
            "桥肩不再是实心的，",
            "这叫敞肩拱，",
            "赵州桥是隋代首创。",
        ],
        ("D5晚", "A07"): [
            "《中国式人情世故》",
            "讲的就是这个理：",
            "交情在平时的往来里，",
            "不在临时的热闹里。",
        ],
        ("D6早", "A06"): [
            "第三，不翻旧账：",
            "别说",
            "「你小时候我也没这么管过你」。",
        ],
        ("D6早", "A10"): [
            "撑得住，",
            "一家人的规矩",
            "才说得到一块儿去。",
        ],
        ("D6午", "A01"): [
            "霜打过的白菜晾在院子里，",
            "老辈人这几天就开始",
            "刷大缸了——今天小雪。",
        ],
        ("D6午", "A07"): [
            "各家做法不一样：有干腌的，",
            "有做泡菜的，",
            "泡菜讲究",
            "坛沿那圈水勤看着点儿。",
        ],
        ("D6午", "A08"): [
            "如今什么菜都买得到，",
            "可不少老人到小雪",
            "还是要腌上一缸——",
            "腌的不是菜，是过日子的节奏，",
            "是老辈人迎冬的讲究。",
        ],
    }

    for ep in ("D5午", "D5晚", "D6早", "D6午"):
        sub_path = PREP_DIR / ep / "subtitles_prep.json"
        meta_path = PREP_DIR / ep / "audio" / "tts_meta.json"
        subs = json.loads(sub_path.read_text(encoding="utf-8"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        line_map = {l["id"]: l for l in meta["lines"]}

        new_subs = []
        handled = set()
        screen_idx = 1
        for l in meta["lines"]:
            lid = l["id"]
            if (ep, lid) in replacements:
                chunks = replacements[(ep, lid)]
                assert "".join(chunks) == l["text"], f"Mismatch {ep} {lid}: {''.join(chunks)} != {l['text']}"
                for ch in chunks:
                    assert len(ch) <= 14 or ch.startswith("「"), f"Too long {ep} {lid}: {ch} ({len(ch)})"
                    new_subs.append({"screen": screen_idx, "line_id": lid, "role": l["role"], "text": ch, "chars": len(ch)})
                    screen_idx += 1
                handled.add(lid)
            else:
                for s in subs:
                    if s["line_id"] == lid:
                        s2 = dict(s)
                        s2["screen"] = screen_idx
                        new_subs.append(s2)
                        screen_idx += 1
        sub_path.write_text(json.dumps(new_subs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[SUBS FIXED] {ep}: lines={sorted(handled)} | total_screens={len(new_subs)}")


def rebuild_d1_zao_audio_round3(ep_dir: Path) -> tuple[Path, dict]:
    """Restore 6 specified pauses to 0.5-0.6s on D1早 while keeping remaining gaps <=0.6s."""
    src_audio_dir = VER_DIR / "D1早" / "audio"
    orig_meta = json.loads((src_audio_dir / "tts_meta.json").read_text(encoding="utf-8"))
    fix_dir = ep_dir / "audio_fixed_r3"
    fix_dir.mkdir(parents=True, exist_ok=True)

    # Specified pauses: A02=500, A03=500, A06=600, A09=500, A11=600; others=350ms
    pause_map = {"A02": 500, "A03": 500, "A06": 600, "A09": 500, "A11": 600}
    concat_list: list[Path] = []
    new_lines: list[dict] = []
    cursor_ms = 0
    for item in orig_meta["lines"]:
        lid = item["id"]
        raw_mp3 = src_audio_dir / f"{lid}_raw.mp3"
        trim_wav = fix_dir / f"{lid}_trim.wav"
        subprocess.run(
            [
                FFMPEG, "-y", "-i", str(raw_mp3),
                "-af", "silenceremove=start_periods=1:start_threshold=-36dB,areverse,silenceremove=start_periods=1:start_threshold=-36dB,areverse",
                "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(trim_wav),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        dur_ms = probe_duration_ms(FFMPEG, trim_wav)
        pause_ms = pause_map.get(lid, 350)
        sil_wav = fix_dir / f"{lid}_sil.wav"
        subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{pause_ms/1000:.3f}", "-c:a", "pcm_s16le", str(sil_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        start_ms = cursor_ms
        end_ms = start_ms + dur_ms
        cursor_ms = end_ms + pause_ms
        concat_list.extend([trim_wav, sil_wav])
        nl = dict(item)
        nl["speech_ms"] = dur_ms
        nl["pause_after_ms"] = pause_ms
        nl["start_ms"] = start_ms
        nl["end_ms"] = end_ms
        new_lines.append(nl)

    list_txt = fix_dir / "concat.txt"
    list_txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in concat_list), encoding="utf-8")
    full_wav = fix_dir / "full_voice.wav"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt), "-c:a", "pcm_s16le", str(full_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    total_ms = probe_duration_ms(FFMPEG, full_wav)
    new_meta = {"total_ms": total_ms, "total_chars": orig_meta["total_chars"], "lines": new_lines}
    (fix_dir / "tts_meta.json").write_text(json.dumps(new_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return full_wav, new_meta


def split_strict_within_group(img: Path, s_ms: int, e_ms: int, max_ms: int = 5600) -> list[tuple[Path, int, int, bool]]:
    """Split [s_ms, e_ms] into segments <= max_ms using ONLY `img` (zero cross-group bleeding)."""
    dur = e_ms - s_ms
    n = max(1, (dur + max_ms - 1) // max_ms)
    step = dur // n
    out = []
    cur = s_ms
    for i in range(n):
        nxt = e_ms if i == n - 1 else cur + step
        out.append((img, cur, nxt, False))
        cur = nxt
    return out


def main() -> None:
    fix_subtitles_round3()

    # 1. Re-render D1早 (strict per-group binding + 6 specified pauses + 11 segments)
    z_wav, z_meta = rebuild_d1_zao_audio_round3(PREP_DIR / "D1早")
    z_lines = z_meta["lines"]
    z_total = z_meta["total_ms"]
    def z_win(s_i: int, e_i: int) -> tuple[int, int]:
        return z_lines[s_i]["start_ms"], (z_total if e_i == len(z_lines) - 1 else z_lines[e_i + 1]["start_ms"])

    z_shots = []
    z_shots.extend(split_strict_within_group(GEN_IMG_DIR / "D1早_IMG01_B.jpg", *z_win(0, 2)))
    z_shots.extend(split_strict_within_group(GEN_IMG_DIR / "D1早_IMG02.jpg", *z_win(3, 4)))
    z_shots.extend(split_strict_within_group(GEN_IMG_DIR / "D1早_IMG03_B.jpg", *z_win(5, 6)))
    z_shots.extend(split_strict_within_group(GEN_IMG_DIR / "D1早_IMG04_B.jpg", *z_win(7, 8)))
    z_shots.extend(split_strict_within_group(GEN_IMG_DIR / "D1早_IMG05.jpg", *z_win(9, 10)))

    r_z = render_episode(
        "D1早", "11-17 周二 07:00", "管教·对话A", "孙子下棋 输了就哭", None,
        z_meta, z_wav, z_shots, "第三周_D1早_成片_返修版.mp4",
        deviation_note="停顿按第三轮返修单恢复 6 处 0.5–0.6s 停顿（A02=0.5s、A03=0.5s、A06=0.6s、A09=0.5s、A11=0.6s），其余句间 ≤0.5s；「生成图片」中 D1早 每组 1 张共 5 张，各组内按 ≤5.6s 切分 Ken Burns 运镜，绝不跨组混绑。",
        extra_notes=[
            "第三轮全段重绑：`A01–A03`=`D1早_IMG01_B.jpg`、`A04–A05`=`D1早_IMG02.jpg`、`A06–A07`=`D1早_IMG03_B.jpg`、`A08–A09`=`D1早_IMG04_B.jpg`、`A10–A11`=`D1早_IMG05.jpg`（无眼镜修正版）。",
            "工具与清理：Codex 生图（1080×1920 JPEG）、MiniMax `speech-2.8-hd` 配音；验收通过后清理本地 `render_v2` 中间产物。",
        ],
    )
    print("R3 D1早:", r_z)

    # 2. Re-render D5午, D5晚, D6早, D6午, D7早
    card_rqsg = ASSETS_DIR / "card_人情世故.png"

    # D5午
    m = json.loads((PREP_DIR / "D5午" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s = build_standard_shots("D5午", m, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,6),("IMG05",7,7)])
    print("R3 D5午:", render_episode("D5午", "11-21 周六 12:30", "名城：赵州桥", "赵州桥 活了千年", None, m, PREP_DIR / "D5午" / "audio" / "full_voice.wav", s, "第三周_D5午_成片.mp4", deviation_note="停顿为已定版 MiniMax 主音轨自然停顿（全周裁定接受）；已修正 A03「这几个小券：」断行。"))

    # D5晚
    m = json.loads((PREP_DIR / "D5晚" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s = build_standard_shots("D5晚", m, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)])
    a07_s = m["lines"][6]["start_ms"]
    b_s, b_e = a07_s, a07_s + 2770
    s = insert_book_window(s, card_rqsg, b_s, b_e)
    print("R3 D5晚:", render_episode("D5晚", "11-21 周六 19:00", "人情：老同学突然发请帖", "老同学请帖 去不去", "人情冷暖", m, PREP_DIR / "D5晚" / "audio" / "full_voice.wav", s, "第三周_D5晚_成片.mp4", book_note=f"官方《中国式人情世故》封面轻露：{b_s/1000:.2f}–{b_e/1000:.2f}s（2.77s ≤8.0s，与 A07 同步，无箭头，A09 已移除书图）", deviation_note="停顿为已定版 MiniMax 主音轨自然停顿；已修正 A07「讲的就是这个理：」断行并将书图移至 A07 段内。"))

    # D6早
    m = json.loads((PREP_DIR / "D6早" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s = build_standard_shots("D6早", m, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)])
    print("R3 D6早:", render_episode("D6早", "11-22 周日 07:00", "管教·单人对照B", "管娃时 别当靠山", None, m, PREP_DIR / "D6早" / "audio" / "full_voice.wav", s, "第三周_D6早_成片.mp4", deviation_note="停顿为已定版 MiniMax 主音轨自然停顿；已修正 A06 引文整句不断屏与 A10「才说得到一块儿去。」断行。"))

    # D6午
    m = json.loads((PREP_DIR / "D6午" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s = build_standard_shots("D6午", m, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)])
    print("R3 D6午:", render_episode("D6午", "11-22 周日 12:30", "饮食民俗：小雪腌菜", "小雪到了 该腌菜了", None, m, PREP_DIR / "D6午" / "audio" / "full_voice.wav", s, "第三周_D6午_成片.mp4", deviation_note="停顿为已定版 MiniMax 主音轨自然停顿；已修正 A01「刷大缸了——今天小雪。」、A07「坛沿那圈水勤看着点儿。」、A08「还是要腌上一缸——」三处断行。"))

    # D7早 (swap A06 soaking vs A07 rinsing)
    m = json.loads((PREP_DIR / "D7早" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s = build_standard_shots("D7早", m, [("IMG01",0,2),("IMG02",3,5),("IMG03",6,7),("IMG04",8,9),("IMG05",10,11)])
    print("R3 D7早:", render_episode("D7早", "11-23 周一 07:00", "冷知识对照（全周唯一）", "切洋葱 为啥流泪", None, m, PREP_DIR / "D7早" / "audio" / "full_voice.wav", s, "第三周_D7早_成片.mp4", deviation_note="停顿为已定版 MiniMax 主音轨自然停顿；已将 A06 末句「把洋葱泡一泡凉水」绑回泡水图 `D7早_IMG02_B.jpg`，`D7早_IMG03` 冲刀图后移至 A07–A08。"))


if __name__ == "__main__":
    main()
