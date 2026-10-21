# -*- coding: utf-8 -*-
fp = r"C:\Users\Miche\AppData\Roaming\Python\Python314\site-packages\pyJianYingDraft\draft_folder.py"
with open(fp, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "shutil.rmtree(draft_path)" in line:
        new_lines.append("""            try:
                shutil.rmtree(draft_path)
            except Exception:
                for item in os.listdir(draft_path):
                    if item != "deepagent":
                        item_p = os.path.join(draft_path, item)
                        try:
                            if os.path.isdir(item_p):
                                shutil.rmtree(item_p)
                            else:
                                os.unlink(item_p)
                        except Exception:
                            pass
""")
    elif "os.makedirs(draft_path)" in line and "exist_ok" not in line:
        new_lines.append("        os.makedirs(draft_path, exist_ok=True)\n")
    else:
        new_lines.append(line)

with open(fp, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("draft_folder.py patched with resilient rmtree!")
