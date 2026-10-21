# -*- coding: utf-8 -*-
import asyncio
import edge_tts
from pathlib import Path

async def test_pronunciations():
    words = [
        ("拙政园", "当您带孩子走进苏州的拙政园和留园"),
        ("疏浚西湖", "大文豪苏东坡在杭州当官时，是怎么带着老百姓疏浚西湖"),
        ("水光潋滟", "孩子一下子就懂了什么叫水光潋滟晴方好"),
        ("苏堤", "一条长长的苏堤像绿丝带一样横跨湖面"),
        ("日升昌", "您一定要带孩子走进日升昌票号"),
        ("神龟", "整个城池就像一只巨大的神龟")
    ]
    out_dir = Path("01_配音与音色库/专名读音抽听")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for tag, sentence in words:
        comm = edge_tts.Communicate(sentence, "zh-CN-YunjianNeural", rate="-8%", pitch="-6Hz")
        out_f = out_dir / f"check_{tag}.mp3"
        await comm.save(str(out_f))
        print(f"Synthesized: {tag} -> {out_f} ({out_f.stat().st_size} bytes)")

if __name__ == "__main__":
    asyncio.run(test_pronunciations())
