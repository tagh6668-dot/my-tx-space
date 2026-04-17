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
    direction: ltr; /* تیترهای انگلیسی چپ‌چین باشند بهتر است */
    text-align: left;
}
"""

# 2. پیدا کردن فایل‌ها
files = glob.glob("*.txt")

# --- اصلاح مهم: مرتب‌سازی الفبایی ساده ---
# چون نام فایل‌های شما Section_01, Section_02 است، سورت معمولی درست کار می‌کند
files.sort()

# 3. ساخت محتوای HTML
html_content = "<html><head><meta charset='utf-8'></head><body>"

print(f"Found {len(files)} files. Merging...")

for file_name in files:
    # تمیز کردن نام فایل برای نمایش در تیتر
    # مثلا: Section_15_Rheumatic_Diseases -> Section 15 Rheumatic Diseases
    display_name = file_name.replace('.txt', '').replace('_', ' ')
    
    with open(file_name, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # حذف ستاره‌ها
    text = text.replace('**', '')
        
    # تبدیل خط‌های جدید به <br>
    formatted_text = text.replace('\n', '<br>')
    
    # افزودن به HTML
    html_content += f"<h2>{display_name}</h2>"
    html_content += f"<div>{formatted_text}</div>"
    html_content += "<hr>"

html_content += "</body></html>"

# 4. تبدیل به PDF
output_filename = "Nokat_Nelson_Full.pdf"
print(f"Generating PDF: {output_filename} (this might take a moment)...")

font_config = FontConfiguration()
try:
    HTML(string=html_content).write_pdf(
        output_filename, 
        stylesheets=[CSS(string=css_content, font_config=font_config)]
    )
    print(f"Done! File saved as: {output_filename}")
except Exception as e:
    print(f"Error creating PDF: {e}")
