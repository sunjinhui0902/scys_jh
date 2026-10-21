# -*- coding: utf-8 -*-
import asyncio
import edge_tts
from pathlib import Path
import json

async def test():
    md_path = Path("03_视频成片与工程/01_平遥古城_单集精讲/01_文案与分镜/口播文案.md")
    content = md_path.read_text(encoding="utf-8")
    
    # parse pure text
    import re
    pure_match = re.search(r"## 纯净口播文案\s*[\n\r]+([^\n\r#].*?)(?=\n## |\Z)", content, re.DOTALL)
    text = pure_match.group(1).strip()
    print(f"Total text length: {len(text)} chars")
    
    comm = edge_tts.Communicate(text, "zh-CN-YunjianNeural", rate="-8%", pitch="-6Hz")
    sentences = []
    audio_bytes = 0
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio_bytes += len(chunk["data"])
        elif chunk["type"] == "SentenceBoundary":
            sentences.append(chunk)
            
    print(f"Synthesized audio: {audio_bytes} bytes")
    print(f"Captured {len(sentences)} SentenceBoundary events")
    for i, s in enumerate(sentences[:10]):
        print(f"[{i+1}] {s['offset']/1e7:.2f}s - {(s['offset']+s['duration'])/1e7:.2f}s ({s['duration']/1e7:.2f}s): {repr(s['text'][:30])}")
        
    # Check "说到这儿" and "肚子里的词儿就不够用了"
    for i, s in enumerate(sentences):
        if "说到这儿" in s["text"]:
            print(f"MATCH '说到这儿': {s['offset']/1e7:.2f}s - {(s['offset']+s['duration'])/1e7:.2f}s: {repr(s['text'])}")
        if "肚子里的词儿" in s["text"]:
            print(f"MATCH '肚子里的词儿': {s['offset']/1e7:.2f}s - {(s['offset']+s['duration'])/1e7:.2f}s: {repr(s['text'])}")

if __name__ == "__main__":
    asyncio.run(test())
