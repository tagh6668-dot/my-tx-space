import os
import time
import queue
import re
import threading
import concurrent.futures
from google import genai
from google.genai import types

# ================= تنظیمات =================
MODEL_NAME = "gemini-3-flash-preview"

# محدودیت‌ها
MAX_REQUESTS_PER_KEY = 20       # سهمیه هر کلید
GLOBAL_DELAY = 1.0              # فاصله ۳ ثانیه‌ای بین شلیک درخواست‌ها

INPUT_DIR = "final_questions"
OUTPUT_DIR = "answers"

API_KEYS = [
    "AIzaSyACWTqS5CDb87wF_6Nqjaw3mTNX8T4Fylc",
    "AIzaSyAUF13O8M53dXnkf95NkQnj297FBEXvoek",
    "AIzaSyA8yufViHavTBz8CHeX_UI4Ud-zNxf-fnw",
    "AIzaSyA3qk8y29ivUQa232YrBN6IgXlYDIe-IlI",
    "AIzaSyCXQGPCwqIMAwE5Xv05IrId8J7f2o4RF6k",
    "AIzaSyBVYksmeZJEQIN9tk7s9H1NZoWzhDNSi0M",
    "AIzaSyAJeWXlgJQbin5EOwa5xsg58AFH_61lvLg",
    "AIzaSyDhDgWOk6hphkJchPk9QXixBS8C_6ifghk",
    "AIzaSyDec5i74AdjYXrqI8McVfMKznxPoZMH2t4"
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

# متغیرهای کنترل ترافیک (حیاتی)
TRAFFIC_LOCK = threading.Lock()  # قفل برای دسترسی به متغیر زمان
LAST_REQUEST_TIME = 0            # زمان آخرین باری که یک درخواست به سمت گوگل شلیک شد

STATS = {'success': 0, 'failed': 0, 'quota': 0}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= تابع مدیریت ترافیک (قلب تپنده کد) =================
def wait_for_green_light():
    """
    این تابع تضمین می‌کند که هیچ دو درخواستی با فاصله کمتر از ۳ ثانیه
    به سمت گوگل شلیک نشوند.
    """
    global LAST_REQUEST_TIME
    
    # ورود به منطقه ممنوعه (فقط یک نفر همزمان وارد می‌شود)
    with TRAFFIC_LOCK:
        now = time.time()
        elapsed = now - LAST_REQUEST_TIME
        
        # اگر از آخرین شلیک کمتر از ۳ ثانیه گذشته، صبر کن
        if elapsed < GLOBAL_DELAY:
            wait_time = GLOBAL_DELAY - elapsed
            time.sleep(wait_time)
        
        # ثبت زمان شلیک جدید (همین الان)
        LAST_REQUEST_TIME = time.time()
    
    # خروج از منطقه ممنوعه: نفر بعدی می‌تواند بیاید و چک کند
    # نکته: ما الان اجازه شلیک داریم و از قفل خارج شدیم.

# ================= توابع کمکی =================
def get_colored_api_tag(api_key):
    try:
        idx = API_KEYS.index(api_key)
        color = API_COLORS[idx % len(API_COLORS)]
        return f"{color}[Key-{idx+1}]{RESET}"
    except: return "[Key-?]"

def clean_markdown(text):
    text = text.replace("**", "").replace("##", "").replace("`", "")
    return re.sub(r"^#+\s*", "", text, flags=re.MULTILINE).strip()

# ================= پرامپت =================
BASE_PROMPT = """
نقش: تو یک منتور هوشمند و استراتژیست ارشد آزمون «پره‌اینترنی پزشکی» هستی.

هدف: من یک سوال تستی بالینی به تو می‌دهم. هدف من صرفاً دانستن جواب این تست خاص نیست؛ بلکه می‌خواهم بر «مبحث و بیماری اصلی» که در این سوال مطرح شده، مسلط شوم.

دستورالعمل فرمت خروجی (بسیار مهم):
۱. خروجی باید «متن ساده» (Plain Text) باشد.
۲. اکیداً از «جدول» استفاده نکن. داده‌های جدولی را به صورت لیست زیر هم بنویس.
۳. از کاراکترهای مارک‌داون مثل «دو ستاره» (**) برای بولد کردن یا «هشتگ» (#) برای تیتر استفاده نکن. متن باید برای ذخیره در فایل txt کاملاً تمیز باشد.

ساختار پاسخ‌دهی (باید شامل ۴ بخش زیر باشد):

🩺 کالبدشکافی بالینی و پاسخ:
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

# ================= منطق کارگر =================
def worker_task(worker_id, api_key, work_queue):
    api_tag = get_colored_api_tag(api_key)
    print(f"{api_tag} 🤖 استارت (سهمیه: {MAX_REQUESTS_PER_KEY}).")

    client = genai.Client(api_key=api_key)
    count = 0

    while True:
        # ۱. چک سهمیه
        if count >= MAX_REQUESTS_PER_KEY:
            print(f"{api_tag} {RED}سهمیه تمام شد.{RESET}")
            return

        # ۲. گرفتن فایل
        try:
            filename = work_queue.get(timeout=1)
        except queue.Empty:
            return

        in_path = os.path.join(INPUT_DIR, filename)
        out_path = os.path.join(OUTPUT_DIR, filename)
        tmp_path = out_path + ".tmp"

        try:
            # ۳. هماهنگی با ایست بازرسی (مهمترین بخش)
            # اینجا چک می‌کنیم که ۳ ثانیه از نفر قبلی گذشته باشد
            wait_for_green_light() 
            
            # ۴. ارسال به گوگل (شلیک!)
            print(f"{api_tag} ⏳ ارسال {filename}...")
            
            with open(in_path, "r", encoding="utf-8") as f:
                q_txt = f.read()

            if not q_txt.strip(): raise ValueError("Empty File")

            # فراخوانی API (اینجا زمانبر است و موازی انجام می‌شود)
            resp = client.models.generate_content(
                model=MODEL_NAME,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=BASE_PROMPT.format(question_text=q_txt))])],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                )
            )
            
            # ۵. ذخیره
            ans = clean_markdown(resp.text if resp.text else "")
            if ans:
                with open(tmp_path, "w", encoding="utf-8") as f: f.write(ans)
                os.replace(tmp_path, out_path)
                print(f"{api_tag} ✅ {filename} ذخیره شد.")
                STATS['success'] += 1
                count += 1
            else:
                raise ValueError("پاسخ خالی")

        except Exception as e:
            print(f"{api_tag} ❌ خطا در {filename}: {e}")
            if os.path.exists(tmp_path): os.remove(tmp_path)
            STATS['failed'] += 1
            count += 1 # خطا هم سهمیه کم می‌کند
            time.sleep(2) # استراحت کوتاه بعد از خطا

        finally:
            work_queue.task_done()

# ================= بدنه اصلی =================
def main():
    print(f"\n{YELLOW}--- 🚦 شروع با قانون ۳ ثانیه فاصله ---{RESET}")
    
    # پیدا کردن فایل‌های انجام نشده
    files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(".txt")])
    todo = [f for f in files if not (os.path.exists(os.path.join(OUTPUT_DIR, f)) and os.path.getsize(os.path.join(OUTPUT_DIR, f)) > 0)]

    if not todo:
        print(f"{GREEN}کار تمام است!{RESET}")
        return
    
    print(f"تعداد فایل مانده: {len(todo)}")
    
    # پر کردن صف
    q = queue.Queue()
    for f in todo: q.put(f)

    # اجرای تردها
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(API_KEYS)) as exe:
        futures = [exe.submit(worker_task, i+1, key, q) for i, key in enumerate(API_KEYS)]
        concurrent.futures.wait(futures)

    STATS['quota'] = q.qsize()
    print("\n" + "="*30)
    print(f"موفق: {STATS['success']} | خطا: {STATS['failed']} | مانده: {STATS['quota']}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nتوقف.")
