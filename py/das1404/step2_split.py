import os
import re

# ================= تنظیمات =================
INPUT_DIR = "raw_batches"
OUTPUT_DIR = "final_questions"

def persian_to_english(text):
    """تبدیل اعداد فارسی و عربی به انگلیسی"""
    mapping = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    for fa, en in mapping.items():
        text = text.replace(fa, en)
    return text

def clean_text_advanced(text):
    """پاکسازی متن سوال"""
    # حذف تگ‌های احتمالی باقی‌مانده
    text = re.sub(r"\[cite.*?\]", "", text)
    
    # حذف فاصله‌های اضافی اول و آخر
    text = text.strip()
    return text

def main():
    print("--- ✂️ مرحله دوم: جداسازی هوشمند (پشتیبانی از اعداد فارسی) ---")

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    batch_files = sorted(os.listdir(INPUT_DIR))
    total_saved = 0

    for batch_file in batch_files:
        if not batch_file.endswith(".txt"):
            continue

        path = os.path.join(INPUT_DIR, batch_file)
        print(f"📖 در حال پردازش {batch_file}...")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # الگوی جدید: پشتیبانی از اعداد فارسی (۰-۹) و انگلیسی (0-9)
        # همچنین فاصله احتمالی بین کلمه "سوال" و عدد را در نظر می‌گیرد
        pattern = r"\[\[سوال\s*([0-9۰-۹]+)\]\]"
        
        # اسپلیت کردن متن بر اساس الگو
        # خروجی این دستور لیستی است که به ترتیب: متن قبل از اولین سوال، شماره سوال اول، متن سوال اول، شماره سوال دوم...
        parts = re.split(pattern, content)

        # اگر سوالی پیدا نشد
        if len(parts) < 2:
            print(f"⚠️ هیچ سوالی در {batch_file} یافت نشد (شاید فرمت فایل خالی است).")
            continue

        # حلقه روی قطعات (از اندیس 1 شروع می‌کنیم چون اندیس 0 متن قبل از اولین سوال است)
        for i in range(1, len(parts), 2):
            raw_num = parts[i]        # شماره سوال (ممکن است فارسی باشد: ۱)
            q_text = parts[i+1]       # متن سوال

            # تبدیل شماره به انگلیسی برای نام فایل
            eng_num = persian_to_english(raw_num)
            
            # تمیزکاری متن
            final_text = clean_text_advanced(q_text)

            # اگر متن خالی بود ذخیره نکن
            if not final_text:
                continue

            # ذخیره فایل (مثلاً 1.txt)
            final_path = os.path.join(OUTPUT_DIR, f"{eng_num}.txt")
            with open(final_path, "w", encoding="utf-8") as out_f:
                out_f.write(final_text)

            total_saved += 1

    print(f"\n🎉 تمام شد! {total_saved} سوال در پوشه '{OUTPUT_DIR}' ذخیره شدند.")

if __name__ == "__main__":
    main()
