# -*- coding: utf-8 -*-
"""
脚本：更新五大精讲视频的重点字音与多音字审校备注，并彻底纠错平遥文案中的“乌鬼”->“神龟”
"""
import os
import re

pronunciation_notes = {
    '01_平遥古城_单集精讲': '''## 重点字音与多音字审校备注
> [!IMPORTANT]
> **字音审校与勘误结论（生成口播与字幕前必核）**：
> 1. **【勘误纠错】神龟（shén guī）**：原文草稿曾误写为“乌鬼”，已严正纠正为**“神龟”**。平遥古城建制形如金龟（南门为首、北门为尾、东西四门为四足），素称“神龟城”或“龟城”，象征吉祥长寿、金汤永固。严禁出现“乌鬼”等错字。
> 2. **日升昌（rì shēng chāng）**：“昌”读第一声 chāng，平遥著名晋商第一票号，不可吞音。
> 3. **协同庆（xié tóng qìng）**：“庆”读第四声 qìng，平遥古钱庄地下金库所在地。
> 4. **票号（piào hào）**：“号”作商业机构、名称时读第四声 hào，切忌误读二声 háo。
> 5. **兑现（duì xiàn）**：“兑”读第四声 duì，不可误读为 tuì。
> 6. **晋商（jìn shāng）**：“晋”读第四声 jìn，山西简称。
> 7. **磨得发亮（mó de fā liàng）**：“得”在此处为动补连词，读轻声 de，不可读 dé 或 děi。''',

    '02_延安宝塔山_单集精讲': '''## 重点字音与多音字审校备注
> [!IMPORTANT]
> **字音审校与读音判断结论（生成口播与字幕前必核）**：
> 1. **千沟万壑（qiān gōu wàn hè）**：“壑”读第四声 hè，指深沟大壑，切忌误读为 huò。
> 2. **八角九层（bā jiǎo jiǔ céng）**：“角”表示建筑八角飞檐形态，读第三声 jiǎo，切忌误读为角色之 jué。
> 3. **吱呀作响（zhī yā zuò xiǎng）**：“吱”象声词，读第一声 zhī。
> 4. **老纺车（lǎo fǎng chē）**：“车”在此处读第一声 chē。
> 5. **省心省力（shěng xīn shěng lì）**：“省”作节约、免除讲，读第三声 shěng，不可读 xǐng。''',

    '03_开封清明上河园_单集精讲': '''## 重点字音与多音字审校备注
> [!IMPORTANT]
> **字音审校与读音判断结论（生成口播与字幕前必核）**：
> 1. **鳞次栉比（lín cì zhì bǐ）**：“栉”读第四声 zhì，指梳篦，形容房屋密集整齐；极易误读为 jié，TTS与字幕必须确认 zhì。
> 2. **茶肆（chá sì）**：“肆”读第四声 sì，古代商铺茶馆，不可读成 chì。
> 3. **龙头铡（lóng tóu zhá）**：“铡”读第二声 zhá（铡刀），不可误读为 zá。
> 4. **包拯（bāo zhěng）**：“拯”读第三声 zhěng（拯救苍生）。
> 5. **迎刃而解（yíng rèn ér jiě）**：“刃”读第四声 rèn；“解”在此处读第三声 jiě。
> 6. **东京汴梁（dōng jīng biàn liáng）**：“汴”读第四声 biàn，指北宋古都汴京。''',

    '04_苏州拙政园_单集精讲': '''## 重点字音与多音字审校备注
> [!IMPORTANT]
> **字音审校与读音判断结论（生成口播与字幕前必核）**：
> 1. **拙政园（zhuó zhèng yuán）**：“拙”现代标准普通话读第一声 zhuó，切忌误读为 cuò 或 zhuō。
> 2. **山水之怡（shān shuǐ zhī yí）**：“怡”读第二声 yí，意为和悦、怡然自得。
> 3. **框景（kuàng jǐng）**：“框”读第四声 kuàng，园林取景造景手法，切忌误读为 kuāng。
> 4. **城郭（chéng guō）**：“郭”读第一声 guō，外城墙之意。
> 5. **北寺塔（běi sì tǎ）**：“寺”读第四声 sì。''',

    '05_杭州西湖_单集精讲': '''## 重点字音与多音字审校备注
> [!IMPORTANT]
> **字音审校与读音判断结论（生成口播与字幕前必核）**：
> 1. **疏浚西湖（shū jùn xī hú）**：“浚”读第四声 jùn，意为疏通水道深挖淤泥，常误读为 suō 或 xùn，TTS与字幕必须确保为 jùn。
> 2. **水光潋滟（shuǐ guāng liàn yàn）**：“潋滟”读第四声 liàn yàn，出自苏轼《饮湖上初晴后雨》，波光闪耀貌。
> 3. **摇橹船（yáo lǔ chuán）**：“橹”读第三声 lǔ，水乡划船工具。
> 4. **苏堤（sū dī）**：“堤”读第一声 dī，切忌误读为 tí。
> 5. **三潭印月（sān tán yìn yuè）**：“潭”读第二声 tán；“印”读第四声 yìn。'''
}

def main():
    base_dir = '03_视频成片与工程'
    for proj, note in pronunciation_notes.items():
        md_path = os.path.join(base_dir, proj, '01_文案与分镜', '口播文案.md')
        if not os.path.exists(md_path):
            print(f'Missing: {md_path}')
            continue
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Project 01 typo fix
        if proj == '01_平遥古城_单集精讲':
            if '乌鬼' in content:
                content = content.replace('乌鬼', '神龟')
                print(f'Fixed "乌鬼" -> "神龟" in {proj}')
        
        # Check if notes already present
        if '## 重点字音与多音字审校备注' not in content:
            target = '## 分镜脚本与运镜编排'
            if target in content:
                content = content.replace(target, note + '\n\n' + target)
            else:
                content = content + '\n\n' + note
        else:
            content = re.sub(r'## 重点字音与多音字审校备注.*?(?=\n## 分镜脚本与运镜编排)', note, content, flags=re.DOTALL)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {proj} successfully.')

    # Update summary table
    summary_file = os.path.join(base_dir, '五城精讲_分镜脚本与GPT生图Prompt总表.md')
    if os.path.exists(summary_file):
        with open(summary_file, 'r', encoding='utf-8') as f:
            s_content = f.read()
        if '乌鬼' in s_content:
            s_content = s_content.replace('乌鬼', '神龟')
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(s_content)
            print('Updated 五城精讲_分镜脚本与GPT生图Prompt总表.md (fixed "乌鬼" -> "神龟")')

if __name__ == '__main__':
    main()
