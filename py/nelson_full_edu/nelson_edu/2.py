import os
import glob
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# 1. ساخت پوشه خروجی اگر وجود نداشته باشد
output_folder = "pdfs"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 2. تنظیمات فونت و استایل (همان تنظیمات خوب قبلی)
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
"""

# 3. پیدا کردن فایل‌ها
files = glob.glob("*.txt")
print(f"Found {len(files)} files. Starting conversion...")

font_config = FontConfiguration()
css = CSS(string=css_content, font_config=font_config)

for file_name in files:
    # خواندن فایل
    with open(file_name, 'r', encoding='utf-8') as f:
        text = f.read()

    # --- قسمت حذف ستاره‌ها ---
    # تمام ** ها را با هیچی (رشته خالی) جایگزین می‌کند
    clean_text = text.replace('**', '')

    # تبدیل اینترها به خط جدید در HTML
    formatted_text = clean_text.replace('\n', '<br>')
    
    # ساخت محتوای HTML برای همین فایل
    html_content = f"<html><head><meta charset='utf-8'></head><body>{formatted_text}</body></html>"

    # تعیین نام فایل خروجی (مثلاً 1.txt می‌شود pdfs/1.pdf)
    base_name = os.path.basename(file_name).replace('.txt', '')
    output_path = os.path.join(output_folder, f"{base_name}.pdf")

    # ساخت PDF
    try:
        HTML(string=html_content).write_pdf(output_path, stylesheets=[css])
        print(f"Converted: {file_name} -> {output_path}")
    except Exception as e:
        print(f"Error converting {file_name}: {e}")

print("Done! All files are in the 'pdfs' folder.")
