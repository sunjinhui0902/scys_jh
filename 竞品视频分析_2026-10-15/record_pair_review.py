"""Record the actual Codex text inspection performed in this session."""
import json
from pipeline import OUTPUT_DIR as R, atomic_json, atomic_text, now

selection=json.loads((R/'manifest/similarity_review_selection.json').read_text(encoding='utf-8'))
notes={
 2:'不同引入，项目签约/夸奖回应场景及荐书段大量重合；顺序匹配约0.699，保留全文相似，不称完全同稿。',
 3:'同类饭局开头与相同闲谈高手荐书段；顺序匹配约0.633，已从全文降为段落。',
 5:'共用放心拿回去看/一句一句教等促单段；开头不同，不能当成同故事。',
 6:'父母、伴侣、孩子与爱自己文案几乎逐句相同，仅少数字词与标点不同，保留全文/开头相似。',
 9:'供应商项目故事与荐书结尾大段相同，左侧多一段前置口号；保留全文/开头相似。',
 10:'后备箱茅台故事同一骨架，开头儿子/姑娘角色变化；全文与尾段相似成立，非文件完全重复。',
 11:'古村落与秋日风光主题不同，共用大美中国引书段；仅段落复用。',
 12:'不同情境引入，共用闲谈高手荐书段；顺序匹配约0.499，已从全文降为段落。',
 15:'共用社交场合价值及促单尾段；开头不同，不推断同故事。',
 21:'自驾路线与公路盘点不同，共用365日日历书介绍；仅段落复用。'
}
review=[]
for p in selection['pairs']:
    n=p['review_number']
    note=notes.get(n,'共用荐书价值/书中例句段，开头场景不同；保留公共段落复用，不据此判定同一故事。')
    review.append({'review_number':n,'left':p['left'],'right':p['right'],'kinds':p['kinds'],'decision':'KEEP_RECORDED_TEXT_RELATION','note':note,'evidence':{'left_quote':p['left_quote'][:110],'right_quote':p['right_quote'][:110],'left_path':p['left_transcript_path'],'right_path':p['right_transcript_path']}})
pairs=[json.loads(z)for z in (R/'clusters/similarity_pairs.jsonl').read_text(encoding='utf-8').splitlines()if z]
fixes=[]
for left,right in [('v_b0b6a297a846159f','v_fe40c7adb68b182d'),('v_3299545e93c3d39e','v_919ec11f532d97b9')]:
    p=next(z for z in pairs if z['left']==left and z['right']==right)
    assert 'FULL_TEXT' not in p['kinds'] and 'STORY_PASSAGE'in p['kinds']
    fixes.append({'left':left,'right':right,'old':'FULL_TEXT + STORY_PASSAGE','new':p['kinds'],'ordered_match_ratio':p['ordered_match_ratio'],'reason':'Common book/CTA tail over-weighted by global bag of ngrams; sequential match only about half the text'})
result={'at':now(),'reviewer':'Codex','review_mode':'Direct comparison of actual ASR excerpts, openings/endings and source transcript paths in tool outputs; not a human user review or audio listening audit','random_seed':selection['random_seed'],'random_pairs':20,'additional_account_coverage_pairs':1,'final_pairs_reviewed':len(review),'final_pair_population':len(pairs),'status':'PASS','scope':'Text relation labels only; story semantics/ASR wording/native video interpretation remain pending','corrections':fixes,'records':review}
assert len(review)==21
atomic_json(R/'manifest/similarity_pair_review.json',result)
lines=['# 相似配对文本复核记录','',f'时间：{result["at"]}；复核者：Codex。最终规则下固定种子20261015随机抽20对，并补1对林睿账号，共21对。另保留调整前20对抽样快照。','', '## 已做的修正','', '发现两对词频全文相似受共用荐书结尾影响，顺序匹配仅约0.5；新增全文顺序匹配≥0.65门槛后降为公共段落关系。全部配对与簇已按新规则重算。','', '段落复用中多数是引书、书中例句、价值主张或促单话术，不直接称故事相同。没有命中跨账号文案阈值，不等于不存在跨账号同题材或同书提及。','', '本次是Codex逐对阅读实际转录、开头/结尾及引用证据的文本复核，未冒充用户人工审阅或逐句耳听。ASR词名、故事真实性、真实画面仍由A/人工进一步核对。','', '|序号|左ID|右ID|最终关系|复核意见|','|---:|---|---|---|---|']
lines += [f'|{p["review_number"]}|{p["left"]}|{p["right"]}|{", ".join(p["kinds"])}|{p["note"]}|'for p in review]
atomic_text(R/'reports/相似配对抽查.md','\n'.join(lines)+'\n')
atomic_json(R/'manifest/asr_tail_review.json',{'video_id':'v_2fe34883cba71ae1','tail_start_s':493,'duration_s':30.377,'rms_dbfs':-39.5607545465,'peak_dbfs':-21.86376968,'zero_sample_fraction':0.43450636995,'method':'Read existing 16kHz PCM WAV samples; no upload/API','status':'REVIEW_PENDING','conclusion':'Nonzero low-volume tail; RMS alone cannot distinguish music from quiet speech. Last ASR text ends at492.615s; retain review flag, do not invent text or call pure silence.'})
print(json.dumps({'pairs_reviewed':len(review),'known_false_full_text_edges_corrected':len(fixes),'status':result['status']},ensure_ascii=False))
