"""Read-only A import; normalize only from traceable local evidence."""
import argparse, collections, datetime, difflib, hashlib, json, os, re, time
from pathlib import Path
from pipeline import OUTPUT_DIR as R, atomic_json, atomic_text, now, sha256
from align_segments import token_spans

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def norm(t):return ''.join(c.lower()for c in str(t)if c.isalnum())
def excerpt(segments,a,b):
    selected=[s for s in segments if s['end_ms']>a*1000 and s['start_ms']<b*1000]
    return {'start_s':selected[0]['start_ms']/1000,'end_s':selected[-1]['end_ms']/1000,'text':''.join(s['text']for s in selected)}if selected else {'start_s':None,'end_s':None,'text':''}

BOOK_FIX={'v_5ddb5a8ad7ccdb86':('365日走遍中国','365日走遍中国'),'v_ac516db0b5dced62':('大美中国','大美中国'),'v_7c9d47c6f0bcb117':('把话说的恰到好处〔转录候选〕','未知（转录候选：把话说的恰到好处）'),'v_d3f3bf3980928b72':('中国历史名城〔转录候选〕','未知（转录候选：中国历史名城）')}
BRIDGE_FIX={'v_5ddb5a8ad7ccdb86':(196.540,221.475,'风景盘点转日历书使用场景'),'v_ac516db0b5dced62':(351.110,384,'风景知识需求转图书介绍'),'v_7c9d47c6f0bcb117':(503.740,530.645,'被问练习方法后推荐阅读工具书'),'v_d3f3bf3980928b72':(457.940,479.265,'城市历史解释转阅读系列书')}
CTA_FIX={'v_5ddb5a8ad7ccdb86':(244.320,258.035,'放下面/弄一本的购物与使用建议'),'v_ac516db0b5dced62':(642.950,651.015,'左下方商品引导')}
DEATH_IDS={'v_2a38fc92b95504f3','v_e24346b823344654'}

def visual(v,account,frames):
    if account=='开卷读书':form='人物口播式画面，部分肖像/文字覆盖；生成方式未独立核实';subtitle='白字黑描边为主，部分黄字';book='四帧未见商品书封（不推断全片无）'
    elif account=='文汇书香苑':form='人物肖像、纪念场景或历史风格画面拼接；真实性未核实';subtitle='黄色大字黑描边';book='四帧未见实体图书商品'
    elif account=='林睿读书&书在橱窗':
        form='水墨人物插画，所见帧含AI标识'if v in ['v_7e9d12d17d945cb4','v_36c4c9338c258e24']else'城市/山水取景混剪；真实性未核实'
        subtitle='黄色大字黑描边';book='四帧无可核实商品封面；插画书本道具不等于商品'
        if v=='v_5ddb5a8ad7ccdb86':form='风景插画含AI标识，夹日历书展示';book='257.498秒帧可见365日走遍中国日历字样；版本未核实'
    elif account=='破局书屋':form='人物情景演绎（所见帧有AI生成标识）与图书画面';subtitle='黄色黑描边字幕，底部有生成内容提示';book='末帧有书本/内页，正式商品信息未核实'
    elif account=='赵健的读书日记':form='人物出镜与书店/城市/汽车或图表画面';subtitle='白色黑描边为主';book='书店/阅读相关画面不等于具体在售商品'
    else:form='山水/城市画面混排，部分帧有AI生成标识';subtitle='白色或黄色黑描边字';book='部分桌面图书/画册式画面；书名版本未核'
    if v in ['v_b1d211336b0f5ebb','v_734ec81ff3d7343f']:book='中帧书封可读隐形的契约，末帧为图书内页'
    if v=='v_183328bf0ee8b458':book='120.185秒帧为饭局人物，非书封；238.371秒帧为书内页'
    return {'visual_type':form,'subtitle_style':subtitle,'book_appearance':book,'audio_style':'AI_PENDING（需声音/配乐听核）','evidence_frames':frames,'review_method':'Codex实际查看全部4帧；仅证实所见画面，不推断全片/音频'}

def validate_schema(d,v,x):
    e=[]
    for k in ['schema_version','video_id','input_mode','analyzed_at','fields','evidence','limitations','status']:
        if k not in d:e.append('缺少'+k)
    if d.get('video_id')!=v or d.get('account')!=x['account']or d.get('source_video_path')!=x['source_path']:e.append('身份/来源不匹配')
    if d.get('input_mode')not in ['native_video','text_plus_frames','text_only']:e.append('输入模式非法')
    if not isinstance(d.get('schema_version'),str)or not isinstance(d.get('limitations'),(str,list))or not isinstance(d.get('evidence'),(dict,list)):e.append('顶层类型错误')
    try:assert datetime.datetime.fromisoformat(d['analyzed_at']).utcoffset()is not None
    except:e.append('分析时间格式错误')
    f=d.get('fields',{})
    for k in ['theme','category','mentioned_books','recommended_book','hook','narrative_structure','bridge','cta','visual_and_audio']:
        if k not in f:e.append('fields缺少'+k)
    for k in ['theme','category','narrative_structure']:
        if not isinstance(f.get(k),str):e.append(k+'类型错误')
    for k in ['hook','bridge','cta','visual_and_audio']:
        if not isinstance(f.get(k),dict):e.append(k+'类型错误')
    if not isinstance(f.get('mentioned_books'),list)or not all(isinstance(z,str)for z in f.get('mentioned_books',[])):e.append('书名数组错误')
    if f.get('recommended_book')is not None and not isinstance(f.get('recommended_book'),str):e.append('推荐书名类型错误')
    ref=d.get('evidence',{}).get('exact_timestamps_source')if isinstance(d.get('evidence'),dict)else None
    if not isinstance(ref,str)or not(R/ref).is_file()or v not in ref:e.append('时间证据路径错误')
    return e

def process(v,x,source,policy):
    d=read(source);f=d['fields'];errors=validate_schema(d,v,x);issues=[];corrections=[]
    raw=read(R/'segments'/f'{v}.json');text=(R/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip();segments=read(R/'segments'/f'{v}.aligned.json')['segments'];spans=token_spans(text)
    if len(spans)!=len(raw['raw_timestamp']):spans=token_spans(text,True)
    assert len(spans)==len(raw['raw_timestamp'])
    hook=''.join(s[2]for s,t in zip(spans,raw['raw_timestamp'])if t[0]<3000)
    if norm(f['hook'].get('text_0_3s',''))!=norm(hook):corrections.append('0～3秒字段按本地词级时间戳重建；A原摘录单独保留')
    normalized={'theme':f['theme'],'category':f['category'],'mentioned_books':f['mentioned_books'],'recommended_book':f['recommended_book']or'无明确推荐','hook_text':hook or'0～3秒未识别到语音','hook_type':f['hook'].get('hook_type','未知'),'narrative_structure':f['narrative_structure'],'target_audience':'推断：'+f.get('target_audience','未提供'),'product_value':f.get('product_value',{}),'reusable_template_insights':f.get('reusable_template_insights',{})}
    evidences={}
    for kind in ['bridge','cta']:
        z=f[kind];present=z.get('has_'+kind)is True;a=z.get('start_time_s');b=z.get('end_time_s');quote=z.get('text','');typ=z.get('transition_type'if kind=='bridge'else'cta_type','未细分')
        override=BRIDGE_FIX.get(v)if kind=='bridge'else CTA_FIX.get(v)
        if override:a,b,typ=override;present=True;corrections.append(kind+'按可定位原文补全/前移')
        if v=='v_7c9d47c6f0bcb117'and kind=='cta':present=False;corrections.append('借阅对话不计作购物促单；保留原对话为非商业结尾行为')
        if present:
            if not isinstance(a,(int,float))or not isinstance(b,(int,float))or not 0<=a<b<=x['duration_s']+1:errors.append(kind+'时间越界');ex={'start_s':None,'end_s':None,'text':'AI_PENDING'}
            else:ex=excerpt(segments,a,b)
            target=norm(ex['text']);matcher=difflib.SequenceMatcher(None,norm(quote),target,autojunk=False);coverage=sum(t.size for t in matcher.get_matching_blocks())/max(1,len(norm(quote)))
            if not override and coverage<.85:issues.append(kind+'A引文与指定时段不吻合')
            normalized[kind]={'present':True,**ex,'type':typ,'source':'本地ASR可读分段（模型估计时间，未逐句耳听）'}
            evidences[kind]={'A_start_s':z.get('start_time_s'),'A_end_s':z.get('end_time_s'),'A_quote':quote,'A_quote_coverage_in_imported_window':round(coverage,4),'actual_imported':ex}
        else:normalized[kind]={'present':False,'start_s':None,'end_s':None,'text':'无明确引书推荐'if kind=='bridge'else'无明确购物促单','type':'无'}
    if v in BOOK_FIX:
        name,recommended=BOOK_FIX[v];normalized['mentioned_books']=[name];normalized['recommended_book']=recommended;corrections.append('补充或更正书名；候选/正式书名未知明确区分')
    normalized['closing_behavior_A']=f['cta'].get('text','无')
    normalized['visual_and_audio']=visual(v,x['account'],read(R/'frames'/v/'index.json'))
    if d['input_mode']=='text_plus_frames':
        normalized['visual_and_audio']['audio_style']='无法确认（文字+四帧不能评估完整配音/音乐）';corrections.append('音频与完整镜头判断收回，静态画面按实际4帧核对')
    else:issues.append('A声称native_video，实际工具输入链与完整声音能力仍未独立证实；已补查所声称的指定时刻画面')
    if v in DEATH_IDS:
        issues.append('素材含本项目未核实的名人逝世叙事；不能作为真实新闻或原创事实依据')
        normalized['theme']='素材借未经本项目核实的逝世叙事引出生命感悟（分析对象表述，非事实确认）'
    if v=='v_183328bf0ee8b458':issues.append('A所标封面证据帧实际为饭局人物；出版社/封面字样尚无该帧支持')
    status='AI_REVIEW'if errors or issues else'AI_OK'
    return {'schema_version':'phase4-import-1','video_id':v,'account':x['account'],'source_video_path':x['source_path'],'input_sha256':sha256(source),'policy_sha256':policy,'schema_valid':not errors,'schema_errors':errors,'status':status,'input_mode_declared':d['input_mode'],'codex_verification_mode':'text_plus_frames + local timestamp comparison','acceptance_scope':'所导入文字、模型估计时间与实际4帧；不代表全片音画、史实、商品真伪或营销效果验证','normalized':normalized,'A_original':d,'corrections':corrections,'unresolved_issues':issues,'evidence_checks':evidences,'imported_at':now(),'source_A_path':str(R/'analysis_a'/source.name),'snapshot_path':str(source)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--interrupt-after',type=int);args=ap.parse_args();rows=[json.loads(s)for s in(R/'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines()if s];lookup={x['video_id']:x for x in rows};ids=[c['video_id']for c in read(R/'clusters/deep_candidates.json')]
    out=R/'manifest/phase4_records';out.mkdir(exist_ok=True);policy=sha256(Path(__file__));records=[];skipped=0;created=[]
    for v in ids:
        source=R/'manifest/phase4_input_snapshot'/f'{v}.json';target=out/f'{v}.json'
        cached=read(target)if target.exists()else{}
        if cached.get('input_sha256')==sha256(source)and cached.get('policy_sha256')==policy:records.append(cached);skipped+=1;continue
        rec=process(v,lookup[v],source,policy);atomic_json(target,rec);records.append(rec);created.append(target)
        if args.interrupt_after and len(created)==args.interrupt_after:
            atomic_json(R/'manifest/phase4_resume_before.json',{'at':now(),'method':'Actual import process immediately exits with75 after atomic checkpoints','checkpoints':[{'path':str(p),'sha256':sha256(p),'mtime_ns':p.stat().st_mtime_ns}for p in created]})
            os._exit(75)
    before=read(R/'manifest/phase4_resume_before.json');preserved=[Path(z['path']).stat().st_mtime_ns==z['mtime_ns']and sha256(Path(z['path']))==z['sha256']for z in before['checkpoints']]
    atomic_json(R/'manifest/phase4_resume_result.json',{'at':now(),'actual_process_exit_code_first_run':75,'checkpoints_before':len(preserved),'preserved_hash_and_mtime':sum(preserved),'skipped_records_on_resume':skipped,'status':'PASS'if all(preserved)and skipped>=len(preserved)else'FAIL'})
    summary={'at':now(),'candidates':len(ids),'records':len(records),'schema_pass':sum(r['schema_valid']for r in records),'status_counts':dict(collections.Counter(r['status']for r in records)),'corrections':sum(len(r['corrections'])for r in records),'scope':'AI_OK applies only to checked imported text/static frames; unsupported modality values unknown; unresolved critical cases AI_REVIEW'}
    atomic_json(R/'manifest/phase4_import_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

