import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

source_file = r"C:\Users\Miche\Downloads\gemini-code-1792595162685.py"

# Safely execute the file in a custom namespace
namespace = {}
with open(source_file, "r", encoding="utf-8") as f:
    code = f.read()

# Replace the print statement that might fail in GBK terminal if executed
code_safe = code.replace("✅ 已生成工程包:", "[SUCCESS] Created:")

exec(code_safe, namespace)

projects = namespace.get("projects", {})
print(f"Total projects found: {len(projects)}")
target_base = r"D:\fuye\03_视频成片与工程"

for folder, content in projects.items():
    project_dir = os.path.join(target_base, folder)
    script_dir = os.path.join(project_dir, "01_文案与分镜")
    os.makedirs(script_dir, exist_ok=True)
    file_path = os.path.join(script_dir, "口播文案.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"  -> Generated: {file_path}")
