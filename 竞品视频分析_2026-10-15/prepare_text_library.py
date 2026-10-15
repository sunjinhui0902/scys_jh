import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / 'content_library'
PACK = ROOT / 'handoff' / 'text_light_v1'
NOW = dt.datetime.now().astimezone().isoformat(timespec='seconds')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(value, encoding='utf-8')
    os.replace(tmp, path)


def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def md(value):
    return str(value).replace('|', '／').replace('\n', ' ').replace('\r', ' ')


assert not PACK.exists(), 'Preserve an existing batch; inspect before rerunning.'
assert not LIB.exists(), 'Preserve an existing library; inspect before rerunning.'
rows = [json.loads(s) for s in (ROOT / 'manifest/manifest.jsonl').read_text(encoding='utf-8-sig').splitlines()]
canonical = [r for r in rows if r.get('canonical_video_id', r['video_id']) == r['video_id']]
features = read(ROOT / 'clusters/video_features.json')
sources = collections.defaultdict(list)
for row in rows:
    sources[row['sha256']].append({'video_id': row['video_id'], 'account': row['account'],
                                   'source_path': row['source_path']})
legacy = {p.stem: read(p) for p in (ROOT / 'manifest/phase4_records').glob('v_*.json')}
protected = [ROOT / 'manifest/manifest.jsonl', ROOT / '阅见生活_竞品视频分析_终版.xlsx',
             ROOT / 'reports/最终验收报告.md', ROOT / 'reports/原创带货模板库_验收整理版.md']
protected += [p for p in (ROOT / 'analysis_a').rglob('*') if p.is_file() and p.suffix != '.tmp']
before = [sha(p) for p in protected]
source_before = {r['source_path']: (Path(r['source_path']).stat().st_size,
                                   Path(r['source_path']).stat().st_mtime_ns) for r in rows}

# Ideas are newly written questions and structures, not factual claims or finished ads.
# Fields: series, title, original opening, narrative, conditional book bridge, verification, production.
ideas = [
('读图与路线','第一次去一座城，先看景点清单，还是先看地图？','把地图上的景点名遮住，你还看得懂这座城吗？','认方向→找河流和道路→按一种兴趣排路线','目录确有地图和对应地点时，用一页地图展示读法，再邀请查看目录','地图方向、比例、地名与实际版本；路线只作阅读示例','自绘简图＋自摄图书，低难度'),
('读图与路线','同一座城，给爱拍照和爱散步的人各排一条路线','同一个周末，为什么两个人想去的地方完全不同？','明确两种兴趣→比较停留方式→解释选择标准','用书中不同主题的章节，帮助读者按兴趣选读','目录是否真正覆盖两种兴趣；实际出行另查开放与交通信息','两色路线示意＋目录，低难度'),
('读图与路线','一页风景图，能不能读出三个问题？','这张风景图除了好看，还能告诉你什么？','先观察→提出地形与生活问题→寻找页内解释','仅在实书有图注或解释时，展示从图片读到信息的过程','图片来源、图注内容和地理结论；未找到答案就保留问题','一页自摄图书＋三个标注，低难度'),
('读图与路线','旅行攻略里的“必去”，适合你的周末吗？','行程塞满以后，最容易被忘掉的可能是你自己想看什么。','列出自己的兴趣→比较两种安排→保留一个阅读问题','把书作为选题和背景阅读工具，展示相关目录供选择','不承诺路线最优；书中是否有对应内容','原创行程卡＋目录，低难度'),
('读图与路线','不出门的晚上，也能从一张地图开始读旅行书吗？','今晚不做远行计划，只在地图上挑一个你想弄明白的地方。','选点→读图注→记一个下次可观察的问题','展示该书能否支持这种读法，由真实页面决定','书内地图、图注与适读难度；不许诺替代实地旅行','桌面阅读演示，低难度'),
('河流与城市','旅行照里有一条河，下一次能不能多看懂一点？','下次站到河边，除了拍照，还可以先问哪三个问题？','河在哪里→桥连接哪里→两岸怎么被使用','实书确有相关地图时，连接到河流与城市的章节','具体河名、流向、桥梁与街区，均须核对','自绘河岸示意＋许可画面，低至中难度'),
('河流与城市','一座桥，为什么值得单独留十分钟？','如果暂时不看桥的名字，你会先观察它的哪一部分？','位置→连接对象→桥上与桥下的使用场景','若实书有桥梁图解或当地介绍，再指向该页','桥的位置、年代、功能；不把传说当史实','观察卡＋对应图书页，中难度'),
('河流与城市','河岸两边，为什么可能长出不同的街巷？','过一座桥，街道的感觉为什么可能就变了？','提出观察→找地图差异→列出待验证的解释','借助实书的地图或城市章节继续查证','不能仅凭画面推断地形、历史或居民特征','左右对照示意＋地图，中难度'),
('河流与城市','沿一条河读几座城，怎样避免变成地名清单？','今天不比谁去过的城市多，只比较一个共同问题。','选同一观察维度→比较不同城市→给出下一次观察任务','对应章节足够时，展示跨章节比较的阅读方法','城市与水系关系、选择标准和页面覆盖','统一版式的三张城市卡，中难度'),
('河流与城市','水边的老街，哪些是看见的，哪些是我们猜的？','看到一条水边老街，你会不会立刻替它编出一段故事？','列可见细节→区分解释与猜测→提出查证路径','用实书资料作待核线索，再补可靠资料','街区历史、图片地点、传说出处','可见／待查两栏＋实书，中难度'),
('山地与道路','旅行地图上一条弯路，值得先问什么？','地图上这条路为什么绕过去？先别急着猜答案。','观察弯曲位置→对照地形→列可能原因→查证','书中确有地形或交通图时，演示如何对照阅读','实际路线与地形，避免单因果推断','自绘地形与道路示意，低至中难度'),
('山地与道路','同样叫“山”，旅行照片应该怎么比较？','两张山景照都好看，我们能不能比较得更具体？','设定观察维度→描述形态→查相关解释','从实书图像与图注学习描述，而不是只背形容词','地貌术语、照片地点及成因；未核实不定论','图书图像局部＋原创描述卡，中难度'),
('山地与道路','一座山城，怎么从地图读到步行体验？','地图上的一厘米，到了坡上还是同样的感觉吗？','识别坡地→比较道路关系→提出步行观察','若书中有城市与地形解释，用它补充背景','海拔、坡度、道路通行；不作安全路线保证','示意剖面＋路线卡，中难度'),
('山地与道路','旅行看山，怎样把“壮观”说得更具体？','下次看到山，你想只说一句壮观，还是多说出一个观察？','描述轮廓→比较尺度与视角→提出知识问题','用实书的图注或地貌页继续阅读','尺度与地貌名称；禁止用镜头效果冒充真实比例','同图不同观察标注，低至中难度'),
('山地与道路','山口、河谷和道路，能不能放在一张图里看？','把山、河和路分开看，可能会漏掉什么联系？','分别定位→放回同图→提出联系假设→查证','对应地图齐备时，用一页带出跨图阅读','地形交通关系不能只凭示意图下结论','自绘三层示意，中难度'),
('古城与建筑','走进古城，先观察街道，还是先找故事？','先不听传说，只看这条街，你能记住哪三个细节？','可见空间→形成问题→资料核对→回看空间','实际城市章节存在时，引到地图与建筑说明','地点、年代、修复情况、引文出处','街巷示意＋实书，中难度'),
('古城与建筑','一座城门，怎样变成一个阅读问题？','城门为什么在这里？这个问题比背名字更值得展开。','地图定位→提出边界和道路问题→查两类资料','若有城址图或城市史章节，再引到相应内容','城门位置、迁建与年代；相关事实须另核','城址示意＋图书页，中至高难度'),
('古城与建筑','看到古塔，除了“高”和“老”还能看什么？','不排第几，也不比谁最神秘，今天只看塔的一个细节。','选择形制细节→描述→提出解释问题→查证','书内有结构图解时展示相应阅读价值','建筑名称、形制术语、年代和开放信息','结构示意＋许可图片，中至高难度'),
('古城与建筑','老地名和新地名，怎么讲成一个有出处的故事？','一个名字改变过几次，答案应该去哪里找？','提出问题→列不同资料→核对时间与来源→说明未知','以实书作为线索，再用可靠资料完成事实核验','地名沿革、具体时间、别名适用范围','时间线卡＋出处卡，高难度'),
('古城与建筑','建筑细节看不懂，能不能从一个问题开始？','这次不用记住一整座建筑，只挑一个你不明白的地方。','局部观察→问题→图解阅读→重新描述','图书有对应图解时，展示问题如何得到解释','图解是否对应实物，术语与建筑真实性','局部图解＋自绘标注，中难度'),
('亲子共读','带孩子旅行前，先一起找三个问题','攻略不用先背完，出门前先各写下一个想弄明白的问题。','大人提问→孩子选择→一起查页面→记录实地观察','目录和内容适合时，示范亲子一起查图的过程','适读年龄仅按实际内容判断，不承诺教育效果','桌面提问卡＋图书，低难度'),
('亲子共读','孩子问“为什么”，大人也能说“我们一起查”','旅行里最难的一句话，可能是坦然说：这个我也不知道。','呈现原创问答→找线索→分清答案与猜测','用真实书页演示查找，没查到就换资料','不虚构书中答案，孩子反应为演绎时明确性质','原创问答卡＋实书，低难度'),
('亲子共读','旅行后不写流水账，试做一张观察卡','这次旅行，你最想留下的是一个地点，还是一个问题？','照片→观察→疑问→查证→一句自己的解释','相关页面存在时，示范旅行后回到书里查证','照片权利、地点、解释来源','自制观察卡＋自摄素材，低难度'),
('亲子共读','家里一张地图，怎么成为周末共读起点？','先不问孩子记住多少地名，看看他想先找哪里。','兴趣选择→地图定位→图注阅读→共同提问','真实版本有地图及图注时，展示阅读步骤','地图适读性、准确性和内容覆盖','俯拍桌面＋定位卡，低难度'),
('亲子共读','旅行前的问题，旅行后有没有变？','出门前你想知道的，回来以后还一样吗？','前测问题→实地观察→新问题→延伸阅读','书内有相关章节时，支持旅行前后两次阅读','体验只作个人示例，不外推儿童成长效果','前后两张问题卡，低难度'),
('旅行阅读习惯','同一本旅行书，周末前和周末后怎么读？','出发前找线索，回来后找答案，同一本书可以试两种读法。','出发前选问题→回来整理观察→回书查证','用真实目录和页内内容演示，不保证每个问题都有答案','实际目录、图片与使用体验','桌面阅读＋两张便签，低难度'),
('旅行阅读习惯','不追“必去榜”，按一个兴趣翻旅行书','如果这次只选一个兴趣，你会从哪一页开始？','给出兴趣例子→定位章节→比较内容→形成自己的选择','目录与兴趣匹配时，展示按需选读','不声称官方排名或最佳路线','目录＋兴趣标签，低难度'),
('旅行阅读习惯','一张照片配一个问题，做自己的旅行笔记','同一张照片，写下“真好看”以外的第二句话。','选照片→描述可见→提出问题→记录查证','实书可作查阅工具，演示真实找到的内容','照片来源与地点；猜测和事实分开','原创笔记版式＋图书，低难度'),
('旅行阅读习惯','买旅行地理书之前，先翻哪几处？','别只看封面，先看看目录、图注和你最关心的那一页。','明确阅读需求→比较目录→看图注→读样页','展示当前真实版本的内容边界，邀请自行比较','书名版本、目录、纸张和图像均按实物描述','实书翻阅演示，低难度'),
('旅行阅读习惯','把“去过哪里”换成“这次看懂了什么”','一趟旅行结束，能不能只认真回答一个自己的问题？','选择问题→展示观察→说明出处→留待下次验证','相关页面确有解释时，再连到延伸阅读','不把个人体会当通用知识，不编造所读内容','个人笔记＋真实书页，低至中难度'),
]
assert len(ideas) == 30
priority_ids = {1, 3, 6, 11, 21, 26}
topic_records = []
for n, (series, title, opening, narrative, bridge, verify, production) in enumerate(ideas, 1):
    topic_records.append({
        'topic_id': f'GEO_{n:03d}', 'series': series, 'title': title,
        'priority': '首批建议' if n in priority_ids else '储备',
        'status': 'DRAFT_TOPIC_NOT_SCRIPT', 'product_status': 'SKU_AND_CONTENT_PENDING',
        'book_direction': '大美中国／365日走遍中国类旅行地理读物；正式品名与版本未核',
        'original_opening': opening, 'narrative_outline': narrative, 'conditional_book_bridge': bridge,
        'cta_method': '只依据已核实内容说明适合谁，再邀请查看目录或商品详情；购买引导待商品确认',
        'verification_needed': verify, 'production_suggestion': production,
        'duration_test_suggestion': '首批可尝试60～90秒；实际由文案与试读决定，不是效果结论',
        'research_structure': 'T05；必要时参考T03单样本草案，不把草案计为已验证模板',
        'reference_video_ids': ['v_d00cee56eff9e90d', 'v_ac516db0b5dced62', 'v_5ddb5a8ad7ccdb86'],
        'reference_scope': '仅参考提出问题、展开内容、引向阅读的抽象结构；不证明本选题事实或营销效果',
        'created_by': 'Codex原创提议', 'created_at': NOW,
    })
dump(LIB / '旅行地理选题库.json', topic_records)

library = []
units = []
original_char_count = 0
canonical.sort(key=lambda r: (0 if set(features[r['video_id']]['book_candidates']) & {'大美中国', '365日走遍中国'}
                              else 1 if r['account'] in {'锦绣千秋录', '林睿读书&书在橱窗'} else 2,
                              r['account'], r['video_id']))
for row in canonical:
    vid = row['video_id']
    text = Path(row['transcript_path']).read_text(encoding='utf-8-sig')
    original_char_count += len(text)
    aligned = read(row['segments_path'])
    segments = [{'segment_id': f'{vid}_s{i:05d}', 'start_ms': s['start_ms'], 'end_ms': s['end_ms'], 'text': s['text']}
                for i, s in enumerate(aligned['segments'], 1)]
    assert ''.join(s['text'] for s in segments) == text.strip()
    groups, current, chars = [], [], 0
    for segment in segments:
        if current and chars + len(segment['text']) > 6000:
            groups.append(current)
            current, chars = [], 0
        current.append(segment)
        chars += len(segment['text'])
    if current:
        groups.append(current)
    assert groups
    unit_ids = [f'{vid}_u{i:02d}' for i in range(1, len(groups) + 1)]
    start_idx = 0
    row_units = []
    for index, group in enumerate(groups, 1):
        uid = unit_ids[index - 1]
        entry = {
            'schema_version': 'text-light-input-1.0', 'unit_id': uid, 'video_id': vid,
            'account': row['account'], 'source_title': row.get('db', {}).get('title', Path(row['source_path']).stem),
            'title_is_metadata_not_transcript': True, 'input_mode': 'text_only', 'status': 'AI_PENDING',
            'unit_index': index, 'unit_count': len(groups), 'all_video_unit_ids': unit_ids,
            'duration_s': row['duration_s'], 'text_source': 'FunASR转录，未全量逐字听核；时间为模型估计',
            'core_text': ''.join(s['text'] for s in group), 'segments': group,
            'previous_context': segments[max(0, start_idx - 2):start_idx],
            'following_context': segments[start_idx + len(group):start_idx + len(group) + 2],
            'context_policy': '邻段只辅助理解；每个核心分段仅在一个单元计数；引用必须回指核心分段',
            'book_rule_hints': features[vid]['book_candidates'], 'rule_hints_are_not_semantic_results': True,
            'source_transcript_sha256': sha(row['transcript_path'])['sha256'],
            'source_segments_sha256': sha(row['segments_path'])['sha256'],
            'legacy_deep_status': legacy.get(vid, {}).get('status', 'AI_PENDING'),
            'legacy_deep_status_does_not_complete_this_text_task': True,
        }
        path = PACK / 'inputs' / f'{uid}.json'
        dump(path, entry)
        refs = sha(path)
        info = {'unit_id': uid, 'video_id': vid, 'account': row['account'], 'input_path': str(path),
                'input_sha256': refs['sha256'], 'core_characters': len(entry['core_text']),
                'core_segments': len(group), 'status': 'AI_PENDING',
                'expected_unit_output': str(ROOT / 'analysis_a/text_light_v1/units' / f'{uid}.json')}
        units.append(info)
        row_units.append(uid)
        start_idx += len(group)
    library.append({
        'video_id': vid, 'account': row['account'], 'sha256': row['sha256'],
        'all_source_mappings': sources[row['sha256']], 'duration_s': row['duration_s'],
        'source_title': row.get('db', {}).get('title', Path(row['source_path']).stem),
        'transcript_path': row['transcript_path'], 'segments_path': row['segments_path'],
        'text_characters': len(text), 'opening_asr_excerpt': text[:90].strip(),
        'book_rule_candidates': features[vid]['book_candidates'],
        'rule_cluster_ids': features[vid]['similarity_clusters'],
        'legacy_deep_status': legacy.get(vid, {}).get('status', 'AI_PENDING'),
        'text_semantic_status': 'AI_PENDING', 'semantic_output_path': str(ROOT / 'analysis_a/text_light_v1/videos' / f'{vid}.json'),
        'unit_ids': row_units, 'facts_verified': False, 'sales_performance_verified': False,
    })
assert len(library) == 317 and sum(len(x['all_source_mappings']) for x in library) == 332
write(LIB / '文案索引.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in library))

# Keep each reading batch bounded; long transcripts are split without dropping the tail.
batches, current, char_count = [], [], 0
for unit in units:
    if current and (len(current) >= 10 or char_count + unit['core_characters'] > 18000):
        batches.append(current)
        current, char_count = [], 0
    current.append(unit)
    char_count += unit['core_characters']
if current:
    batches.append(current)
batch_index = []
for n, group in enumerate(batches, 1):
    batch = {'batch_id': f'text_b{n:03d}', 'input_mode': 'text_only', 'status': 'AI_PENDING',
             'unit_count': len(group), 'core_characters': sum(u['core_characters'] for u in group), 'units': group}
    path = PACK / 'batches' / f'text_b{n:03d}.json'
    dump(path, batch)
    batch_index.append({'batch_id': batch['batch_id'], 'path': str(path), 'sha256': sha(path)['sha256'],
                        'unit_count': len(group), 'core_characters': batch['core_characters']})

evidence = {'type': 'object', 'required': ['unit_id', 'segment_ids', 'quote'], 'properties': {
    'unit_id': {'type': 'string'}, 'segment_ids': {'type': 'array', 'minItems': 1, 'items': {'type': 'string'}},
    'quote': {'type': 'string', 'maxLength': 100},
    'start_ms': {'type': ['number', 'null']}, 'end_ms': {'type': ['number', 'null']}}}
book = {'type': 'object', 'required': ['name_candidate', 'relation', 'evidence', 'source_scope'],
        'properties': {'name_candidate': {'type': 'string'}, 'relation': {'enum': ['仅引用', '明确阅读推荐', '明确购物引导', '普通词误判', '未知']},
                       'source_scope': {'enum': ['ASR', '仅标题', 'ASR及标题']},
                       'evidence': {'type': 'array', 'items': evidence}}}
schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': 'Whole-corpus text light analysis; independent from video deep analysis',
          'type': 'object', 'required': ['schema_version', 'record_kind', 'video_id', 'unit_ids', 'input_mode', 'input_sha256s',
                                      'analyzed_at', 'status', 'all_assigned_text_read', 'fields', 'evidence', 'limitations'],
          'properties': {
              'schema_version': {'const': 'text-light-output-1.0'}, 'record_kind': {'enum': ['unit', 'video']},
              'video_id': {'type': 'string', 'pattern': '^v_[0-9a-f]{16}$'},
              'unit_ids': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'type': 'string'}},
              'input_mode': {'const': 'text_only'}, 'input_sha256s': {'type': 'object', 'minProperties': 1},
              'analyzed_at': {'type': 'string', 'format': 'date-time'},
              'status': {'enum': ['AI_OK', 'AI_REVIEW', 'AI_PENDING']},
              'all_assigned_text_read': {'type': 'boolean'},
              'fields': {'type': 'object', 'required': ['theme', 'topic_tags', 'audience_inferred', 'books', 'opening',
                                                       'narrative_pattern', 'bridge', 'cta', 'value_claims', 'original_angles', 'risks', 'travel_relevance'],
                         'properties': {
                             'theme': {'type': 'string'}, 'topic_tags': {'type': 'array', 'maxItems': 5, 'items': {'type': 'string'}},
                             'audience_inferred': {'type': 'string'}, 'books': {'type': 'array', 'items': book},
                             'opening': {'type': 'object', 'required': ['quote', 'type', 'scope'], 'properties': {
                                 'quote': {'type': 'string', 'maxLength': 100}, 'type': {'type': 'string'},
                                 'scope': {'const': '文本开头摘录，不等于真实0～3秒音频钩子'}}},
                             'narrative_pattern': {'type': 'string'},
                             'bridge': {'type': 'object'}, 'cta': {'type': 'array', 'items': {'type': 'object'}},
                             'value_claims': {'type': 'array', 'items': {'type': 'object'}},
                             'original_angles': {'type': 'array', 'maxItems': 2, 'items': {'type': 'string'}},
                             'risks': {'type': 'array', 'items': {'type': 'string'}},
                             'travel_relevance': {'enum': ['高', '中', '低', '无法判断']}}},
              'evidence': {'type': 'array', 'items': evidence}, 'limitations': {'type': 'array', 'items': {'type': 'string'}},
          },
          'description': 'Schema only checks structure. Codex must verify coverage, hashes, quotes/segment ownership, book relations, and unresolved factual claims before library import.'}
dump(PACK / 'analysis_schema.json', schema)
plan = {'schema_version': 'text-light-plan-1.0', 'created_at': NOW, 'scope': '317份独立文字稿的全量轻量语义标注；不新增全量视频拆解',
        'status': 'AI_PENDING', 'source_paths': 332, 'unique_videos': 317, 'raw_text_characters': original_char_count,
        'core_text_characters': sum(u['core_characters'] for u in units), 'unit_count': len(units), 'batch_count': len(batches),
        'long_video_ids': [r['video_id'] for r in library if len(r['unit_ids']) > 1],
        'priority': '旅行地理书名规则候选→锦绣千秋录/林睿→其余账号；仅排序，不排除任何账号',
        'videos': [{'video_id': r['video_id'], 'account': r['account'], 'unit_ids': r['unit_ids'],
                    'expected_video_output': r['semantic_output_path'], 'status': 'AI_PENDING'} for r in library],
        'batches': batch_index, 'no_new_external_upload_permission': True,
        'input_includes_video_audio_frames': False,
        'output_root': str(ROOT / 'analysis_a/text_light_v1')}
dump(PACK / 'batch_plan.json', plan)

index_md = ['# 竞品文案参考库｜317份独立文字稿', '',
            f'建立时间：{NOW}。332个来源映射到317份独立内容，合计{original_char_count:,}字符（含原稿换行）。', '',
            '**当前全量语义标注：317条AI_PENDING。** 已有相似度、关键词和书名规则候选；25条历史视频深度结果单列，不能把它当全量文字分析完成。', '',
            '以下是可点击的检索目录，全文仍在原transcripts目录中。书名仅为规则候选；原稿有ASR误识，人物、数字、引语与商品信息没有全量事实核验。', '']
for account in sorted({r['account'] for r in library}):
    items = [r for r in library if r['account'] == account]
    index_md += [f'## {account}｜{len(items)}份独立内容', '',
                 '|video_id／全文|原始标题（摘要）|分钟|书名规则候选|历史深度状态|文字语义状态|', '|---|---|---:|---|---|---|']
    for row in sorted(items, key=lambda x: x['video_id']):
        link = Path(row['transcript_path']).as_posix()
        title = row['source_title'][:78]
        index_md.append(f"|[{row['video_id']}]({link})|{md(title)}|{row['duration_s']/60:.1f}|{md('、'.join(row['book_rule_candidates']) or '未命中规则，不等于没有')}|{row['legacy_deep_status']}|AI_PENDING|")
    index_md.append('')
write(LIB / '01_竞品文案参考库.md', '\n'.join(index_md) + '\n')

topic_md = ['# 旅行地理原创选题库｜30条草案', '',
            '方向：用户倾向《大美中国》和“365日走遍中国”类旅行地理读物。正式商品名、版本、目录与可展示内容尚未核对。', '',
            '**这30条是Codex新拟选题，不是竞品全文改写，不是已完成的317篇语义分析结论，也不是发布成稿或已验证爆款。** 题目中的问题是研究入口，具体解释待事实核查。', '',
            '现有T05作为结构参考；其余按商品实际内容再匹配。每条的引书段均有条件：实书确有该内容才能使用。', '',
            '## 首批建议6条', '', '|编号|题目|先试原因|', '|---|---|---|']
for t in topic_records:
    if t['priority'] == '首批建议':
        topic_md.append(f"|{t['topic_id']}|{t['title']}|可用地图、便签或阅读演示起稿；具体说明核实后再写|")
topic_md += ['', '建议先从其中选2～3条，同一本书、相近时长试做；一次只比较一个主要变量。首批选择是制作难度与信息条件的判断，不是转化预测。', '', '## 全部选题', '']
for t in topic_records:
    topic_md += [f"### {t['topic_id']}｜{t['title']}｜{t['priority']}", '',
                 f"- 系列：{t['series']}", f"- 原创开头：{t['original_opening']}",
                 f"- 展开：{t['narrative_outline']}", f"- 引书方法：{t['conditional_book_bridge']}",
                 f"- 画面与难度：{t['production_suggestion']}", f"- 待核实：{t['verification_needed']}", '']
topic_md += ['## 从选题升级到成稿', '',
             '确定真实在售版本并提供目录、可展示样页后，每条补齐：完整口播→逐段时长→画面/字幕→引书/CTA→素材需求→事实来源→复核状态。', '',
             '选题数不计入成稿数。原创建议可独立调整，不能以替换竞品同义词、保留其独特开头结尾或降低相似度作为目标。', '']
write(LIB / '02_旅行地理原创选题库_30条.md', '\n'.join(topic_md))

instructions = f'''# A执行任务：317份全文轻量分析，服务旅行地理选题库

## 范围和入口

共享目录：`{ROOT}`。先校验`{PACK / 'READY.json'}`，再读取batch_plan.json和analysis_schema.json。
本轮逐篇分析317份SHA独立文字稿（保留332来源映射由Codex维护），不对317条视频逐镜头拆解。现有25条深度样本不抵扣本轮全文阅读；补充10条视频的任务可后置，如正在处理先完成当前单条原子落盘。

输入只含文字、原始标题、模型估计时间和书名规则提示，没有视频、音频或截图。仅在此前确认的文字输入范围和额度内工作，不新增API Key、收费API或外传授权。不得为了此次文字任务读取或上传原视频、音频、图片。遇额度/输入限制记录真实未完成项并暂停，不冒充完成。

## 按批次读全文

batch_plan列出全部批次。优先旅行地理候选和相关账号，最终必须覆盖全部317份。每个batch最多10个单元且核心全文不超过约18000字符；超长稿拆成多个单元，每个核心段最多约6000字符。不能只看标题、开头结尾或目录就填整篇标签。

读取batches/<batch_id>.json后，逐项核对inputs/<unit_id>.json的SHA-256。每个单元包含完整core_text和可回溯segment_id。邻接context只辅助理解，不重复计入核心覆盖。逐单元完整阅读、落盘；同视频全部单元完成后再合并成单视频结果，不丢掉长稿尾部。若某篇包含多个话题，保留主要话题及覆盖限制，不把第一段当全文。

## 每条轻量字段

按analysis_schema.json输出，建议单视频摘要控制在约400～700个汉字（不含必要证据与长稿覆盖记录），不写逐镜头、配乐或声线分析：

1. theme、最多5个topic_tags；audience_inferred明确为推断。
2. books逐项区分仅引用、明确阅读推荐、明确购物引导、普通词误判、未知；另标ASR／仅标题／两者皆有。书名候选不是事实，“对答如流”可能只是普通词；不能把标题标签算进口播。
3. opening仅摘真实文本开头、分类其写法，scope固定“文本开头摘录，不等于真实0～3秒音频钩子”。后续长稿单元没有全文开头时写空并解释。
4. narrative_pattern用简明结构描述全文；bridge写present（true/false/null）、type、quote、evidence及scope=ASR；false仅表示完整转录中未找到，不声称视频没有视觉引导。未读全不得判全片无。
5. cta分开：购物／阅读建议／借阅剧情／关注／下一集／互动／其他。每项要短引文及分段证据，不能混成购物CTA。
6. value_claims逐项写claim、provenance（素材明确声称或AI推断）、verification_status（未核实／无法判断）；不替素材背书。
7. original_angles最多2条，是新问题、新场景或新观察角度，不能沿用独特竞品开头或拼接整段文案。
8. risks记录ASR专名问题、名人叙事、历史数据或商品歧义；travel_relevance为高/中/低/无法判断，属于主题适配推断，不是效果评分。

evidence每项必须有unit_id、核心segment_ids和不超过100字的原文短摘录，时间仅沿用对应模型时间。quote必须确实存在于这些分段拼接文本中，不自行润色原话。未知留空/标未知，有关键冲突用AI_REVIEW；未完成为AI_PENDING。模型说法、书名、历史与地理事实均未被本任务自动证实。

## 保存、校验与恢复

只写`{ROOT / 'analysis_a/text_light_v1'}`：
- units/<unit_id>.json：record_kind=unit；unit_ids只含该单元。
- videos/<video_id>.json：record_kind=video；必须列出该视频全部unit_ids及各输入SHA，all_assigned_text_read=true才可申报AI_OK。
- batches/<batch_id>.json：本批计划、实际完成、状态、文件SHA、错误及实际运行时间。

先写同目录临时文件，合法JSON和Schema校验通过后原子重命名。Schema只是结构检查，不能替代证据核对。断点恢复跳过输入哈希一致且已校验的最终结果；不读写半成品，不伪造分析时间。旧analysis_a原件、supplement_01、manifest、transcripts、frames、clusters、reports、content_library及Excel均不可修改。

## 全部可处理条目完成后

仍只在text_light_v1输出：
1. 全量文字规律.json：实际逐篇完成数、AI_OK/REVIEW/PENDING、主题/文本结构/引用/荐书/购物分别计数，聚合保留video_id列表和分母，不混入全部332来源重复计数。
2. 旅行地理选题增补.json：优先“大美中国／365日走遍中国类”读物。可只读`{LIB / '旅行地理选题库.json'}`避免重复；为既有30题提供有据的支持/调整/删除建议，每项带source_video_ids和证据角色（结构参考、素材声称、已核事实不得混用）。确有新角度再补最多10题，不凑数、不覆写Codex选题库。
3. 文本模块结构库.json：开头、故事推进、引书、CTA分别抽象成结构及原创示例，原话仅短摘作证据，不把竞品段落当可直接发布素材。
4. 完成清单.json：317个video_id逐项状态、单元覆盖、最终路径、SHA、限制、失败和真实运行时间，最后原子落盘。未完成不能计入完成。

本轮只做文字分析和选题增补，不写成稿、不制作或发布视频、不扩大为全量视频拆解。完成后暂停，报告落盘数量和路径，由Codex核验后更新文案参考库、模块库与单个7-Sheet总表。
'''
write(PACK / '发给A_全量文字轻分析.md', instructions)

guide = f'''# 阅见生活｜从竞品研究到原创生产

## 现在的真实状态

- 332个源视频、317份SHA独立内容；全量ASR文字、时间戳、基础截图和规则聚类已完成。
- 317份全文共{original_char_count:,}字符，尚未全量逐篇语义标注；本轮文字语义状态全部AI_PENDING。此状态独立于25条历史视频深度状态。
- 已有25条深度样本：20条在已核验的文字/静态画面范围可用，5条待复核。5套结构模板中4套研究可用、1套单样本草案。
- 本次新增：317条文案参考索引、30个旅行地理原创选题、{len(units)}个文字阅读单元／{len(batches)}批交接。没有代替A分析，没有外传素材，没有产生成稿或更新最终Excel。

## 三层工作怎样接起来

|层次|处理范围|产物|负责人|
|---|---|---|---|
|基础数据|全量317内容/332来源|转录、分段、去重、相似度、词频|Codex，已完成|
|文字轻分析|317份全文|主题、人群推断、引用/荐书/购物、文本结构、原创建议|A分析，Codex验收；已备好批次|
|视频深拆|代表样本及需要补画面证据的条目|视觉、书籍露出及文本不能回答的问题|A按真实输入能力分析，Codex验收|

全量文字分析不需要重看所有视频，长稿必须读全；全库文字语义完成也不代表全库视频深度完成。既有补充10条可按需要后置或与文字任务在独立目录并行。

## 文案库、选题库、脚本库的区别

1. **竞品文案参考库**：317份原转录的索引、video_id与全部来源，供查证和研究。含ASR误识，原稿不是可直接发布的文案。
2. **文本模块结构库**：文字分析后，分别整理开头公式、故事推进、引书方法、CTA结构；保留短摘证据与原创例句。当前待A输出、Codex核验后入库。
3. **原创选题库**：现在已新拟30题，围绕旅行地理阅读，首批6题有标记；都是草案，未冒充全量文字结论或爆款预测。
4. **原创成稿/分镜脚本库**：选题选定、商品版本和内容核实后，逐条形成完整口播与画面表。当前未生产，不能用30个标题冒充30条成稿。

不另建第二个分析Excel。新增文库采用Markdown/JSON，后续经核验的摘要、结构和来源仍汇总进原7-Sheet总表。

## 原创生产的最小流程

**真实商品与读者问题 → 原创选题 → 查证内容 → 完整口播 → 分镜/字幕/素材 → 样片 → 实际反馈 → 修改入库。**

- 先在首批6题中选2～3题，围绕一本真实图书起稿，减少同时变化的因素。
- 商品输入先补正式书名/版本、商品页或实书目录、可展示样页；价格只在写价格时核实，草稿不要求先齐备所有经营信息。
- 借鉴竞品提出问题、组织叙事、自然引向阅读的方法；用自己的问题、资料、场景、文字和画面重新建立完整表达。不要以同义替换、沿用独特开头结尾或相似度阈值作为原创目标。
- 首批可试60～90秒的阅读演示/地图问题稿；这是制作建议，实际按文案试读调整。先看产品与素材条件，不虚构销量、转化或教育效果。
- 发布前再核实际涉及的事实、商品一致性、素材/音色权利和标识；发布需另行明确授权。
- 有实际数据后，记录留存、完播、点击、成交和反馈，更新“待写→初稿→复核→样片→发布→复盘”状态。没有数据时只评价内容结构与制作可行性。

每条成稿记录：script_id、topic_id、参考video_id及借鉴点、正式商品版本、目标人群、完整口播、分镜时长、画面/字幕/素材来源、Bridge与CTA、事实台账、复核状态、样片路径与发布后数据。没有完成的环节留待处理，不填虚假结果。

## 立即可用的入口

- [317条竞品文案参考库]({(LIB / '01_竞品文案参考库.md').as_posix()})
- [30条旅行地理原创选题库]({(LIB / '02_旅行地理原创选题库_30条.md').as_posix()})
- [发给A的全量文字轻分析指令]({(PACK / '发给A_全量文字轻分析.md').as_posix()})
- [已有原创结构模板]({(ROOT / 'reports/原创带货模板库_验收整理版.md').as_posix()})

把下面这句话发给A即可，不需要逐条复制317篇稿：

> 请读取并严格执行 `{PACK / '发给A_全量文字轻分析.md'}`。只做317份全文轻量分析，优先旅行地理方向，沿用既有文字输入授权与额度，不读取或上传视频、音频、截图。按批次校验、逐条原子落盘并保留断点；完成后停止，交Codex验收。

A完成后，发回其完成清单和产物路径；Codex检查覆盖、原文证据、书名关系和异常，再将标签与模块入库。选题可先挑选，成稿依赖实际商品内容核实。
'''
write(LIB / '开始使用.md', guide)

assert [sha(p) for p in protected] == before
source_after = {r['source_path']: (Path(r['source_path']).stat().st_size,
                                  Path(r['source_path']).stat().st_mtime_ns) for r in rows}
assert source_before == source_after
qa = {'checked_at': NOW, 'library_records': len(library), 'source_mappings': sum(len(r['all_source_mappings']) for r in library),
      'text_characters_including_line_endings': original_char_count,
      'core_characters': sum(u['core_characters'] for u in units), 'units': len(units), 'batches': len(batches),
      'unique_video_ids': len({r['video_id'] for r in library}), 'transcript_reconstruction_pass': 317,
      'all_input_units_status': 'AI_PENDING', 'semantic_analysis_executed': False,
      'topic_drafts': 30, 'first_batch_topic_suggestions': 6, 'finished_original_scripts': 0,
      'protected_files': len(protected), 'protected_sha_size_mtime_unchanged': True,
      'source_332_size_mtime_unchanged': True, 'source_content_rehashed_this_step': False,
      'database_opened': False, 'external_uploads': 0, 'paid_api_calls': 0}
dump(LIB / '准备验收.json', qa)
ready_files = [PACK / 'analysis_schema.json', PACK / 'batch_plan.json', PACK / '发给A_全量文字轻分析.md',
               LIB / '旅行地理选题库.json', LIB / '文案索引.jsonl', LIB / '准备验收.json']
dump(PACK / 'READY.json', {'schema_version': 'text-light-ready-1.0', 'ready_at': NOW, 'files_complete': True,
                         'status': 'PREPARED_AI_PENDING', 'unique_videos': 317, 'units': len(units), 'batches': len(batches),
                         'files': [sha(p) for p in ready_files], 'batch_sha_index': batch_index,
                         'only_text_inputs': True, 'expands_external_authorization': False})
print(json.dumps(qa, ensure_ascii=True))
