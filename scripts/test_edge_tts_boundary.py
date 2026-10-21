# -*- coding: utf-8 -*-
import asyncio
import edge_tts

async def test():
    text = "咱们隔辈人疼孩子，真不是给他买多少贵重玩具，而是趁咱们腿脚还利索，带他去看看祖国的大好河山。今天咱们单独精讲，最适合带孙辈去长见识的，第十座历史名城，山西平遥。很多长辈问我，为什么要带孩子去平遥？因为那里藏着一整座，保存最完整的明清县城。"
    comm = edge_tts.Communicate(text, "zh-CN-YunjianNeural", rate="-8%", pitch="-6Hz")
    sentences = []
    async for chunk in comm.stream():
        if chunk["type"] == "SentenceBoundary":
            sentences.append(chunk)
            
    print(f"Captured {len(sentences)} SentenceBoundary events:")
    for s in sentences:
        print(f"offset={s['offset']/1e7:.2f}s, dur={s['duration']/1e7:.2f}s, text={repr(s['text'])}")

if __name__ == "__main__":
    asyncio.run(test())
