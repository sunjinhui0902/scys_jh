from __future__ import annotations
import csv, hashlib, json, zipfile
from pathlib import Path
from PIL import Image
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
CAPTIONS={
'01':['太和殿与广场全景，先看空间','大殿正面，配合宫城布局背景','另一季节的院落视角，观察前后关系','午门及院落视角，回到门与空间'],
'02':['兵马俑坑全景，建立队列印象','陶俑与陶马展陈，观察人物和动物','一号坑队列，观察个体与整体','陶俑近景，观察脸部与衣着'],
'03':['龙门石壁与洞窟远景','河流与石窟群，补充整体环境','真实洞窟及崖面，观察主次','石刻近景，配合细节观察'],
'04':['云冈第20窟造像','云冈露天造像及石壁环境','洞窟雕刻近景，观察人物组织','第20窟大佛侧面，观察衣纹'],
'05':['日升昌旧址外观，引入票号','另一角度的旧址外观','汇通天下匾额，承接汇兑问题','旧址院门与空间，收回观察'],
'06':['拙政园池水与植物','亭、水与远景的层次','建筑与池水的关系','园林另一视角，配合移动观察'],
'07':['西湖桥、水与树木','远处山体和湖岸','湖面与桥的构景','近树远桥，回到观众的观察'],
'08':['开元寺仁寿塔远景','仁寿塔近一些的视角','开元寺镇国塔','开元寺建筑环境，回到城市生活'],
'09':['丽江古城临水建筑','水道与临水空间','水道和桥的关系','水边台阶与街巷空间'],
'10':['莫高窟标志性外部建筑','第16至17窟外部，不能当作内部壁画','莫高窟入口建筑','崖面与洞窟外部通道'],
'11':['避暑山庄湖岸与建筑','水边亭阁','山庄内塔与园林空间','湖区植物与远景'],
'12':['曲阜孔庙建筑环境','孔庙屋脊细节','孔府建筑，区别于孔庙','孔林神道石刻，区别于孔庙和孔府'],
'13':['明孝陵神道石刻环境','神道石兽近景','另一石兽细节','成排石刻与道路，配合由近到远'],
'14':['殷墟相关甲骨照片，先从文字入题','妇好墓展示，承接遗址与墓葬背景','殷墟现场博物馆青铜簋展陈','安阳中国文字博物馆甲骨展陈；不标为殷墟现场'],
'15':['登封观星台正面','观星台另一角度','观星台与周边空间','观星台标识碑，回到地点']}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 cs=json.loads((BASE/'城市内容.json').read_text(encoding='utf-8'))
 index=list(csv.DictReader((ROOT/'05_爆款知识库与复盘/参考图书拆解_2026-10-15/城市章节索引.csv').open(encoding='utf-8-sig')))
 inventory=json.loads((ROOT/'.local/reference-books/inventory.json').read_text(encoding='utf-8'))
 books={x['id']:x for x in inventory}
 master=['# 15城完整口播文案\n','每城约60～90秒的试读稿，尚未实际配音计时。每段对应同编号图片；第5段用AI氛围图。\n','阅读推荐依据项目参考书的城市目录；不代表已核实际在售商品，不含商品购买指令。\n']
 readme=['# 15城文案与图片素材包\n','15份完整口播，60张实景照片，15张AI氛围图，共75张独立配图。另附3张总预览图。\n','打开任一城市文件夹：先看「文案.txt」，按「图片与文案对应.md」的顺序使用01～05图片。素材图保持原比例，适合剪辑时按主体位置安排；没有强行把横图裁成竖图。\n','图片01～04为有来源的实景或文物展陈照片，05为AI生成氛围示意。AI图不能作为该城实拍、古建筑形制或文物细节的证据，剪辑使用时应保留相应标识。\n','实景照片按照其各自开放许可使用。作者、原页面和许可证见每城「图片来源与许可.txt」与根目录「图片来源总表.csv」。发布时保留署名及许可链接；CC BY-SA的改编分享要求按对应版本处理。署名不是拍摄者或场馆对成片背书。\n','文案事实依据每城的UNESCO官方页面；参考书页码只作目录检索入口，本轮没有对15城全部正文逐页阅读。没有合成真实书封或内页；带货时引书段需与实际商品核对。\n','已核对文件可读取、图片数量、图文主题与图片来源。目标时长为预计值，录音后调整画面时间。\n','## 城市目录\n']
 manifest=[];source_rows=[];all_files=[]
 for c in cs:
  d=BASE/(c['id']+'_'+c['city']);records=json.loads((d/'实景来源.json').read_text(encoding='utf-8'));assert len(records)==4
  images=[d/r['file'] for r in records]+[d/'05_AI氛围.png']
  assert len(list(d.glob('0[1-5]_*.jpg'))+list(d.glob('0[1-5]_*.png')))==5,d
  for p in images:
   with Image.open(p) as im:im.verify()
  text=c['city']+'｜'+c['title']+'\n\n'+'\n\n'.join(c['paragraphs'])+'\n'
  (d/'文案.txt').write_text(text,encoding='utf-8-sig');master.extend(['\n## '+c['id']+' '+c['city']+'｜'+c['title']+'\n','\n\n'.join(c['paragraphs'])+'\n'])
  words=len(''.join(c['paragraphs']));readme.append('- '+c['id']+' '+c['city']+'：'+c['title']+'\n')
  md=['# '+c['city']+'｜图片与文案对应\n','标题：'+c['title']+'\n','完整稿约'+str(words)+'个文字字符；目标60～90秒，未配音实测。按下列5段依次使用，时长随实际录音调整。\n']
  for k,(p,para) in enumerate(zip(images,c['paragraphs'])):
   desc=CAPTIONS[c['id']][k] if k<4 else 'AI氛围示意：'+c['mood']+'。不表示真实城市地点或商品实物。'
   md+=['\n## '+str(k+1)+'｜'+p.name+'\n','画面：'+desc+'\n','对应口播：'+para+'\n']
   manifest.append({'city':c['city'],'file':p.relative_to(BASE).as_posix(),'kind':'真实照片' if k<4 else 'AI氛围示意','caption':desc,'narration':para,'sha256':digest(p),'visual_review':'已查看总预览并核对场所主题；非文物鉴定'})
  url='https://whc.unesco.org/en/list/'+str(c['heritage'])+'/'
  md+=['\n## 后台事实来源\n','[UNESCO官方遗产页]('+url+')，本次已读取。\n']+['- '+f+'\n' for f in c['facts']]
  if c['book']:
   row=next(x for x in index if x['book_id']==c['book'] and x['city_search_alias']==c['city']);b=books[c['book']]
   md+=['\n参考阅读定位：'+c['book']+'，城市条目PDF阅读器第'+row['pdf_start']+'页起，纸书起页'+row['printed_start']+'。此为既有目录定位，不表示本轮已读该正文，且不作为上述史实的唯一依据。\n','原参考PDF：'+Path(b['file']).name+'\n','原件SHA-256：'+b['sha256']+'\n']
  else:md+=['\n登封为本轮新增选题，未在既有城市目录中找到独立条目，结尾未承诺参考书收录。\n']
  if c['id']=='10':md+=['\n本包只配莫高窟外观，口播提及内部壁画时仍使用外观建立背景，不把外观标注为内部细节；如需展示某窟内景，须另取得相应真实资料。\n']
  (d/'图片与文案对应.md').write_text('\n'.join(md),encoding='utf-8')
  license_lines=[c['city']+'｜图片来源与许可\n','下载与核对日期：2026-10-15；照片为作者拍摄时的历史画面，非当天现状。\n']
  for r in records:
   assert digest(d/r['file'])==r['sha256']
   attribution=r['commons_title']+' — '+r['artist']+' — '+r['license']+' — '+r['source_page']+' — '+r['license_url']
   license_lines.extend(['\n'+r['file'],attribution,'图像说明：'+r['description'],'下载处理：'+r['modification'],'原图：'+r['original_url'],''])
   source_rows.append({'城市':c['city'],'图片':r['file'],'原文件名':r['commons_title'],'作者':r['artist'],'许可':r['license'],'许可链接':r['license_url'],'来源页面':r['source_page'],'下载链接':r['download_url'],'SHA256':r['sha256'],'署名文本':attribution})
  license_lines+=['05_AI氛围.png：OpenAI内置图像生成工具生成，提示词保存在AI图片提示词.txt。纯氛围示意，不是历史照片或真实商品展示。']
  (d/'图片来源与许可.txt').write_text('\n'.join(license_lines)+'\n',encoding='utf-8-sig')
  all_files+=images+[d/'文案.txt',d/'图片与文案对应.md',d/'图片来源与许可.txt',d/'AI图片提示词.txt']
 (BASE/'15城完整文案.md').write_text('\n'.join(master),encoding='utf-8');(BASE/'开始使用.md').write_text('\n'.join(readme),encoding='utf-8')
 (BASE/'图文清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with (BASE/'图片来源总表.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(source_rows[0]));w.writeheader();w.writerows(source_rows)
 all_files += [BASE/n for n in ('开始使用.md','15城完整文案.md','图文清单.json','图片来源总表.csv','预览_01.jpg','预览_02.jpg','预览_03.jpg')]
 assert len(manifest)==75 and len(source_rows)==60
 archive=BASE.parent/'15城文案与配图_75张_2026-10-15.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
  for p in all_files:z.write(p,'15城文案与配图/'+p.relative_to(BASE).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  assert len([x for x in z.namelist() if x.endswith(('.png','.jpg'))])==78
 report={'cities':15,'real_photos':60,'ai_images':15,'previews':3,'zip_entries':len(all_files),'zip_bytes':archive.stat().st_size,'zip_sha256':digest(archive),'zip_crc_verified':True,'scope':'完整文案与图片素材；未配音、未生成视频、未核实际SKU'}
 (BASE/'打包验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':build()
