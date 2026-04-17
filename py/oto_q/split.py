import subprocess
import os
from concurrent.futures import ThreadPoolExecutor

# نام فایل ورودی
input_pdf = "immuno.pdf"

# تنظیم تعداد پردازش همزمان مناسب برای گیت‌هاب کداسپیس (2 Core)
# عدد 4 باعث می‌شود از حداکثر توان CPU و Disk استفاده شود بدون اینکه سیستم هنگ کند
MAX_WORKERS = 10

# لیست صفحات
start_pages = [
1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 196, 205, 214, 220, 231, 245, 252, 259, 266, 276, 284, 294, 304
]

if not os.path.exists(input_pdf):
    print(f"Error: File '{input_pdf}' not found.")
    exit()

def process_chapter(data):
    """تابعی که توسط Thread ها اجرا می‌شود"""
    chapter_num, start_p, end_p = data
    
    # تعیین نام خروجی
    output_filename = f"Chapter_{chapter_num:03d}.pdf"
    
    # تعیین بازه صفحات
    if end_p == "end":
        page_range = f"{start_p}-end"
    else:
        page_range = f"{start_p}-{end_p}"
        
    # دستور سیستمی
    cmd = ["pdftk", input_pdf, "cat", page_range, "output", output_filename]
    
    try:
        # اجرای دستور
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # نمایش لاگ به صورت آنی
        print(f"Created {output_filename} (Pages: {page_range})", flush=True)
    except subprocess.CalledProcessError:
        print(f"Error creating {output_filename}", flush=True)

# آماده‌سازی لیست کارها
tasks = []
total_chapters = len(start_pages)

for i in range(total_chapters):
    chapter_num = i + 1
    start = start_pages[i]
    
    if i < total_chapters - 1:
        end = start_pages[i+1] - 1
    else:
        end = "end"
        
    tasks.append((chapter_num, start, end))

print(f"Starting parallel processing on {MAX_WORKERS} threads for {total_chapters} chapters...\n")

# اجرای موازی
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    executor.map(process_chapter, tasks)

print("\nAll Done!")
