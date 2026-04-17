import os
import glob
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# 1. تنظیمات فونت و استایل
css_content = """
@font-face {
    font-family: 'B Nazanin';
    src: url('file:///home/codespace/.fonts/BNazanin.ttf');
}
body {
    font-family: 'B Nazanin', sans-serif;
    direction: rtl;
    text-align: justify;
    padding: 30px;
    font-size: 14pt;
    line-height: 1.6;
}
.english {
    direction: ltr;
    font-family: sans-serif;
    display: inline-block;
}
h2 {
    color: #2c3e50;
    border-bottom: 1px solid #ccc;
    padding-bottom: 10px;
    margin-top: 30px;
}
"""

# 2. پیدا کردن و مرتب‌سازی فایل‌ها (1.txt, 2.txt, ...)
files = glob.glob("*.txt")

# --- تغییر اصلی: مرتب‌سازی بر اساس اعداد اعشاری ---
def sort_key(filename):
    # حذف پسوند .txt
    name = os.path.basename(filename).replace('.txt', '')
    # جدا کردن بخش‌های عددی
    parts = name.split('.')
    # تبدیل هر بخش به عدد صحیح
    return [int(part) for part in parts]

files.sort(key=sort_key)

# 3. ساخت محتوای HTML
html_content = "<html><head><meta charset='utf-8'></head><body>"

print(f"Found {len(files)} files. Merging...")

for file_name in files:
    chapter_num = file_name.replace('.txt', '')
    with open(file_name, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # --- تغییر جدید: حذف ستاره‌ها ---
    text = text.replace('**', '')
        
    # تبدیل خط‌های جدید به <br> و اضافه کردن تیتر
    formatted_text = text.replace('\n', '<br>')
    
    html_content += f"<h2>فصل {chapter_num}</h2>"
    html_content += f"<div>{formatted_text}</div>"
    html_content += "<hr>"

html_content += "</body></html>"

# 4. تبدیل به PDF
print("Generating PDF (this might take a moment)...")
font_config = FontConfiguration()
HTML(string=html_content).write_pdf(
    "Nelson_Full_Python.pdf", 
    stylesheets=[CSS(string=css_content, font_config=font_config)]
)

print("Done! File saved as: Nelson_Full_Python.pdf")
