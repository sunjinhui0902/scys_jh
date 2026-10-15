import os
from workspace_paths import ROOT, EP1, JIANYING, FONT_DIR as PORTABLE_FONT_DIR, ffmpeg, font
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = str(EP1)
IMG_DIR = os.path.join(BASE_DIR, "02_分镜视觉素材")
bg_path = os.path.join(IMG_DIR, "gpt_masterpieces", "gpt_epic_cliff_temple.jpg")
cover_path = os.path.join(IMG_DIR, "cover_packaging_epic_gpt.jpg")
FONT_DIR = str(PORTABLE_FONT_DIR)

target_w, target_h = 1080, 1920

# Open and resize/crop
img = Image.open(bg_path).convert("RGBA")
scale = max(target_w / img.width, target_h / img.height)
new_w, new_h = int(img.width * scale), int(img.height * scale)
img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
left = (new_w - target_w) // 2
top = (new_h - target_h) // 2
bg_cropped = img.crop((left, top, left + target_w, top + target_h))

# Dark translucent gradient on left side
overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
draw_overlay = ImageDraw.Draw(overlay)

# Gradient covering left 60% and top
for y in range(int(target_h * 0.55)):
    alpha = int(190 * (1 - y / (target_h * 0.55)))
    draw_overlay.rectangle([(0, y), (int(target_w * 0.8), y+1)], fill=(10, 8, 5, alpha))

final_img = Image.alpha_composite(bg_cropped, overlay)
draw = ImageDraw.Draw(final_img)

# Fonts
font_xingkai = font("STXINGKA.TTF")
font_msyh_bold = font("msyhbd.ttc")

font_title_main = ImageFont.truetype(font_xingkai, 128)
font_title_mid = ImageFont.truetype(font_xingkai, 86)
font_tag = ImageFont.truetype(font_msyh_bold, 36)
font_subtitle = ImageFont.truetype(font_msyh_bold, 38)

gold_color = (255, 230, 130, 255)
gold_shadow = (20, 15, 10, 240)
white_color = (245, 245, 245, 255)
red_tag_bg = (185, 30, 25, 230)

start_x = 75
start_y = 180

# 1. Main Title Line 1: 中国山西
draw.text((start_x + 4, start_y + 4), "中国山西", font=font_title_main, fill=gold_shadow)
draw.text((start_x, start_y), "中国山西", font=font_title_main, fill=gold_color)

# 2. Main Title Line 2: 三大不可思议的
start_y += 145
draw.text((start_x + 4, start_y + 4), "三大不可思议的", font=font_title_mid, fill=gold_shadow)
draw.text((start_x, start_y), "三大不可思议的", font=font_title_mid, fill=gold_color)

# 3. Main Title Line 3: 古代木结构建筑
start_y += 110
draw.text((start_x + 4, start_y + 4), "古代木结构建筑", font=font_title_mid, fill=gold_shadow)
draw.text((start_x, start_y), "古代木结构建筑", font=font_title_mid, fill=gold_color)

# 4. Red Tag Badge: 【 营造天工 · 全解 】
start_y += 130
tag_text = "【 营造天工 · 全解 】"
tag_bbox = draw.textbbox((start_x, start_y), tag_text, font=font_tag)
pad_x, pad_y = 18, 10
draw.rounded_rectangle(
    [(tag_bbox[0] - pad_x, tag_bbox[1] - pad_y), (tag_bbox[2] + pad_x, tag_bbox[3] + pad_y)],
    radius=16,
    fill=red_tag_bg,
    outline=(255, 200, 100, 220),
    width=2
)
draw.text((start_x, start_y), tag_text, font=font_tag, fill=(255, 240, 200, 255))

# Separator line
start_y += 80
draw.line([(start_x, start_y), (start_x + 420, start_y)], fill=(200, 170, 90, 180), width=3)

# 5. Provocative Subtitles
start_y += 35
q1 = "断了梁，为何能屹立千年不断？"
q2 = "抽掉承重柱，如何扛住八级大震？"

draw.text((start_x + 2, start_y + 2), q1, font=font_subtitle, fill=(0, 0, 0, 220))
draw.text((start_x, start_y), q1, font=font_subtitle, fill=white_color)

start_y += 58
draw.text((start_x + 2, start_y + 2), q2, font=font_subtitle, fill=(0, 0, 0, 220))
draw.text((start_x, start_y), q2, font=font_subtitle, fill=white_color)

final_rgb = final_img.convert("RGB")
final_rgb.save(cover_path, quality=95)
print(f"Cover packaging on GPT image saved: {cover_path}")
