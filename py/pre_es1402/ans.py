import asyncio
import os
import time
import queue
import re
import random
from google import genai
from google.genai import types

# ================= تنظیمات =================
MODEL_NAME = "gemini-3-flash-preview"
INPUT_DIR = "final_questions"
OUTPUT_DIR = "answers"
API_FILE = "api1.txt"
TIMEOUT_SECONDS = 80  # حداکثر زمان انتظار برای پاسخ هر درخواست

# لیست User Agent ها (کروم و سافاری)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# ================= ابزارهای ظاهری =================
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
BLUE = '\033[94m'
API_COLORS = [CYAN, MAGENTA, BLUE, GREEN, YELLOW, CYAN]

SUCCESS_ICON = "✅"
ERROR_ICON = "❌"
WARNING_ICON = "⚠️"
WAIT_ICON = "⏳"
ROBOT_ICON = "🤖"

# ساختار نگهداری وضعیت هر API
API_CONTEXTS = {}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= توابع کمکی =================
def load_api_keys(filename):
    """خواندن کلیدها از فایل با تمیزکاری"""
    keys = []
    if not os.path.exists(filename):
        print(f"{RED}فایل {filename} یافت نشد!{RESET}")
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # نادیده گرفتن کامنت‌ها و خطوط خالی
            if not line or line.startswith('#'):
                continue
            # حذف کوتیشن و کامای احتمالی
            clean_key = line.replace('"', '').replace("'", "").rstrip(',')
            if clean_key:
                keys.append(clean_key)
    return keys

def get_colored_api_tag(api_key, index):
    try:
        color = API_COLORS[index % len(API_COLORS)]
        return f"{color}[...{api_key[-5:]}]{RESET}"
    except: return "[Key-?]"

def clean_markdown(text):
    text = text.replace("**", "").replace("##", "").replace("`", "")
    return re.sub(r"^#+\s*", "", text, flags=re.MULTILINE).strip()

# ================= پرامپت (دست‌نخورده) =================
BASE_PROMPT = """
نقش: تو یک منتور هوشمند و استراتژیست ارشد آزمون «پره‌اینترنی پزشکی» هستی.

هدف: من یک سوال تستی بالینی به تو می‌دهم. هدف من صرفاً دانستن جواب این تست خاص نیست؛ بلکه می‌خواهم بر «مبحث و بیماری اصلی» که در این سوال مطرح شده، مسلط شوم.

دستورالعمل فرمت خروجی (بسیار مهم):
۱. خروجی باید «متن ساده» (Plain Text) باشد.
۲. اکیداً از «جدول» استفاده نکن. داده‌های جدولی را به صورت لیست زیر هم بنویس.
۳. از کاراکترهای مارک‌داون مثل «دو ستاره» (**) برای بولد کردن یا «هشتگ» (#) برای تیتر استفاده نکن. متن باید برای ذخیره در فایل txt کاملاً تمیز باشد.

ساختار پاسخ‌دهی (باید شامل ۴ بخش زیر باشد):

 کالبدشکافی بالینی و پاسخ:
گزینه صحیح را مشخص کن.
سناریوی سوال را تحلیل کن.
استدلال علمی انتخاب گزینه را بنویس.

⛔ تحلیل دام‌های آموزشی (رد گزینه):
چرا سایر گزینه‌ها غلط هستند؟

🔮 پوشش ۳۶۰ درجه بیماری (حیاتی‌ترین بخش):
نام دقیق بیماری یا اختلال مورد بحث را بنویس.
«نیمه‌ی پنهان» این بیماری را آموزش بده:
اگر سوال فعلی درباره «درمان» است ⬅️ تو نکات طلایی «تشخیص» و «علائم» را لیست کن.
اگر سوال فعلی درباره «تشخیص» است ⬅️ تو نکات طلایی «درمان خط اول» و عوارض را لیست کن.
فقط روی نکات پرتکرار و امتحانی (High-Yield) تمرکز کن.

⚡️ نکته‌های رعدوبرقی (Buzzwords):
۲ یا ۳ «کلمه کلیدی» یا «نشانه اختصاصی» بگو که دیدن آن‌ها در صورت سوال، مساوی با تشخیص این بیماری است.

متن سوال این است:
{question_text}
"""

# ================= منطق اصلی پردازش =================

def process_single_file_sync(api_key, filename):
    """
    این تابع منطق درخواست به گوگل را به صورت سینکرون اجرا می‌کند
    """
    ctx = API_CONTEXTS[api_key]
    client = ctx['client']
    
    in_path = os.path.join(INPUT_DIR, filename)
    out_path = os.path.join(OUTPUT_DIR, filename)
    tmp_path = out_path + ".tmp"

    # خواندن فایل ورودی
    with open(in_path, "r", encoding="utf-8") as f:
        q_txt = f.read()

    if not q_txt.strip():
        raise ValueError("Empty File")

    # ارسال درخواست
    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=BASE_PROMPT.format(question_text=q_txt))])],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
        )
    )

    ans = clean_markdown(resp.text if resp.text else "")
    
    if ans:
        # ذخیره اتمیک (اول tmp بعد rename)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(ans)
        os.replace(tmp_path, out_path)
        return True
    else:
        raise ValueError("پاسخ خالی از مدل دریافت شد")

async def process_task_wrapper(api_key, filename):
    """
    رپر Async برای مدیریت تایم‌اوت، خطاها و منطق ۳ بار تلاش
    """
    ctx = API_CONTEXTS[api_key]
    tag = ctx['tag']
    
    print(f"{tag} {WAIT_ICON} شلیک درخواست برای {filename}...")
    loop = asyncio.get_running_loop()

    try:
        # اجرای تابع سینکرون در ترد جداگانه با تایم‌اوت
        await asyncio.wait_for(
            loop.run_in_executor(None, process_single_file_sync, api_key, filename),
            timeout=TIMEOUT_SECONDS
        )
        
        print(f"{tag} {SUCCESS_ICON} {GREEN}{filename} تکمیل شد.{RESET}")
        ctx['consecutive_errors'] = 0 # ریست کردن شمارنده خطا
        
    except asyncio.TimeoutError:
        print(f"{tag} {RED}{WAIT_ICON} تایم‌اوت ({TIMEOUT_SECONDS}s) برای {filename}!{RESET}")
        ctx['failed_count'] += 1
        ctx['consecutive_errors'] += 1
        
    except Exception as e:
        print(f"{tag} {RED}{ERROR_ICON} خطا در {filename}: {e}{RESET}")
        ctx['failed_count'] += 1
        ctx['consecutive_errors'] += 1

    # بررسی قانون ۳ خطا پشت سر هم
    if ctx['consecutive_errors'] >= 3:
        if ctx['active']:
            print(f"{tag} {RED}⛔ این API سه بار پشت سر هم خطا داد و متوقف شد.{RESET}")
            ctx['active'] = False

# ================= بدنه اصلی (Dispatcher) =================
async def main():
    print(f"\n{YELLOW}--- 🚀 شروع عملیات (Fire & Forget / Round Robin) ---{RESET}")

    # ۱. بارگذاری کلیدها
    keys_list = load_api_keys(API_FILE)
    if not keys_list:
        print(f"{RED}هیچ کلیدی پیدا نشد.{RESET}")
        return

    # ۲. آماده‌سازی کلاینت‌ها (با User Agent چرخشی)
    valid_keys = []
    for i, key in enumerate(keys_list):
        user_agent = USER_AGENTS[i % len(USER_AGENTS)]
        try:
            client = genai.Client(
                api_key=key,
                http_options={'headers': {'User-Agent': user_agent}}
            )
            API_CONTEXTS[key] = {
                'client': client,
                'tag': get_colored_api_tag(key, i),
                'active': True,
                'sent_count': 0,
                'failed_count': 0,
                'consecutive_errors': 0
            }
            valid_keys.append(key)
        except Exception as e:
            print(f"خطا در لود کلید {key}: {e}")

    print(f"تعداد کلیدهای فعال: {len(valid_keys)}")

    # ۳. شناسایی فایل‌ها (با قابلیت Resume)
    if not os.path.exists(INPUT_DIR):
        print(f"{RED}پوشه ورودی {INPUT_DIR} یافت نشد.{RESET}")
        return

    all_files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(".txt")])
    todo_files = []
    skipped_count = 0

    for f in all_files:
        out_path = os.path.join(OUTPUT_DIR, f)
        # اگر فایل وجود دارد و خالی نیست، رد کن
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            skipped_count += 1
        else:
            todo_files.append(f)

    if skipped_count > 0:
        print(f"{GREEN}⏭️  تعداد {skipped_count} فایل از قبل پردازش شده بود و نادیده گرفته شد.{RESET}")
    
    if not todo_files:
        print(f"{GREEN}{SUCCESS_ICON} همه فایل‌ها قبلاً پردازش شده‌اند. پایان.{RESET}")
        return

    print(f"📌 {len(todo_files)} فایل جدید در صف پردازش قرار گرفت.\n")

    # ۴. حلقه دیسپچر (Round Robin)
    tasks_in_flight = []
    key_index = 0
    file_index = 0
    total_files = len(todo_files)

    while file_index < total_files:
        # پیدا کردن کلید فعال بعدی
        attempts = 0
        selected_key = None
        
        while attempts < len(valid_keys):
            candidate_key = valid_keys[key_index % len(valid_keys)]
            if API_CONTEXTS[candidate_key]['active']:
                selected_key = candidate_key
                key_index = (key_index + 1) % len(valid_keys)
                break
            key_index += 1
            attempts += 1
        
        if not selected_key:
            print(f"{RED}⛔ همه APIها غیرفعال شده‌اند! توقف عملیات.{RESET}")
            break

        # برداشتن فایل و شلیک
        filename = todo_files[file_index]
        API_CONTEXTS[selected_key]['sent_count'] += 1
        
        # ایجاد تسک (Fire)
        coro = process_task_wrapper(selected_key, filename)
        task = asyncio.create_task(coro)
        tasks_in_flight.append(task)
        
        file_index += 1
        
        # تاخیر شانسی بین شلیک‌ها (اگر فایلی مانده باشد)
        if file_index < total_files:
            sleep_time = random.uniform(2, 5)
            # print(f"   ... مکث {sleep_time:.1f} ثانیه ...") 
            await asyncio.sleep(sleep_time)

    # ۵. انتظار برای پایان تسک‌های در جریان
    print(f"\n{YELLOW}شلیک درخواست‌ها تمام شد. منتظر دریافت پاسخ‌های باقی‌مانده...{RESET}")
    if tasks_in_flight:
        await asyncio.gather(*tasks_in_flight)

    # ۶. گزارش نهایی
    print("\n" + "=" * 40)
    print("📊 " + YELLOW + "گزارش نهایی عملکرد" + RESET)
    print("=" * 40)

    total_sent = 0
    total_failed = 0

    for key in valid_keys:
        stats = API_CONTEXTS[key]
        sent = stats['sent_count']
        failed = stats['failed_count']
        tag = stats['tag']
        total_sent += sent
        total_failed += failed
        
        status_msg = "" if stats['active'] else f"{RED}(متوقف شده){RESET}"
        
        if sent > 0:
            icon = SUCCESS_ICON if failed == 0 else WARNING_ICON
            print(f"{tag}: {icon} {sent} درخواست | {failed} خطا {status_msg}")
    
    print("-" * 40)
    print(f"مجموع کل درخواست‌ها: {total_sent}")
    print(f"مجموع کل خطاها:     {total_failed}")
    if skipped_count > 0:
        print(f"تعداد نادیده گرفته شده (قبلی): {skipped_count}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{RED}⛔ توقف دستی.{RESET}")
