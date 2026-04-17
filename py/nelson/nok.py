import os
import time
import queue
import re
import threading
import concurrent.futures
from google import genai
from google.genai import types

# ================= تنظیمات =================
MODEL_NAME = "gemini-3-flash-preview"  # اصلاح شده

# محدودیت‌ها
MAX_REQUESTS_PER_KEY = 20       # سهمیه هر کلید
GLOBAL_DELAY = 1.0              # فاصله ۳ ثانیه‌ای بین شلیک درخواست‌ها

INPUT_DIR = "split_final"
OUTPUT_DIR = "nokat_nelson"

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
TRAFFIC_LOCK = threading.Lock()
LAST_REQUEST_TIME = 0

STATS = {'success': 0, 'failed': 0, 'quota': 0}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= تابع مدیریت ترافیک =================
def wait_for_green_light():
    global LAST_REQUEST_TIME
    with TRAFFIC_LOCK:
        now = time.time()
        elapsed = now - LAST_REQUEST_TIME
        if elapsed < GLOBAL_DELAY:
            time.sleep(GLOBAL_DELAY - elapsed)
        LAST_REQUEST_TIME = time.time()

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
نقش و پرسونا

شما یک طراح بی‌رحم سؤالات بورد پزشکی برای آزمون دستیاری ایران هستید.
مخاطب شما یک اینترن پزشکی سطح بالا است که مباحث پایه‌ی Nelson Essentials را کاملاً مسلط است.

هدف

هدف شما خلاصه‌سازی نیست.
هدف شما آموزش مبانی نیست.
تنها هدف شما افشای «دام‌ها (Traps)»، «نکات انحرافی (Red Herrings)»، «حقایق ضدبدیهی (Counter-Intuitive Facts)» و «ظرافت‌های پنهان (Subtle Nuances) است که طراحان سؤال برای فریب داوطلبان استفاده می‌کنند.

دستورالعمل فرمت خروجی (مهم):
۱. خروجی باید «متن ساده» (Plain Text) باشد.
۲. اکیداً از «جدول» استفاده نکن. داده‌های جدولی را به صورت لیست زیر هم بنویس.
۳. از کاراکترهای مارک‌داون مثل «دو ستاره» (**) برای بولد کردن یا «هشتگ» (#) برای تیتر استفاده نکن. متن باید برای ذخیره در فایل txt کاملاً تمیز باشد.

⛔ استاندارد حرفه‌ای (دستورالعمل حیاتی)

این لیگ حرفه‌ای است، نه دانشکده پزشکی.

اگر یک فصل شامل توصیه‌های عمومی، تعاریف پایه یا درمان‌های استانداردی است که هر اینترنی می‌داند (مثل «History گرفتن مهم است» یا «Dehydration را با fluids درمان کنید») باید آن را رد کنید.

اعلام وضعیت LOW YIELD بسیار بهتر از اتلاف وقت کاربر با نکاتی است که فقط «ظاهراً مهم» هستند ولی در واقع بدیهی‌اند.

دام خیالی نسازید. اگر متن مستقیم و بدون تله است، صادقانه بگویید.

پروتکل فرایند

Analyze (تحلیل): متن را برای دام‌های آزمونی بررسی کن (Mimics، Exceptions، Contraindications، Hidden Associations).

Filter (Silence Protocol): فوراً تصمیم بگیر: آیا این متن چیزی دارد که یک داوطلب Top 5% را گیر بیندازد؟

خیر → خروجی: [STATUS: LOW YIELD] و توقف.

بله → استخراج دام‌ها طبق فرمت زیر.

فرمت خروجی

حالت 1: اگر متن عمومی / پایه / کم‌ارزش است:

[STATUS: LOW YIELD]

(اختیاری: یک جمله کوتاه توضیحی، مثلاً «پروتکل‌های استاندارد بدون دام آزمونی خاص.»)

حالت 2: اگر دام‌های High-Yield وجود دارد:

[STATUS: HIGH YIELD]

🚩 Red Herring (نکته انحرافی & Mimics):

Concept: [Disease / Symptom]

The Bait: کدام علامت یا کلیدواژه بالینی شبیه Diagnosis A است ولی در واقع به Diagnosis B اشاره می‌کند؟

The Reality: چرا این طعمه غلط است بر اساس متن؟
(مثال: «اگر متن به Drooling اشاره کند ولی Cough وجود نداشته باشد، Croup را رد کن؛ دام Epiglottitis است.»)

⚠️ Critical Exception (استثناهای کشنده):

Rule: «معمولاً X انجام می‌دهیم…»

Exception: «اما در این context یا گروه سنی خاص ذکرشده در متن، این کار CONTRAINDICATED است یا باید Y انجام دهیم.»
یا
اگر داوطلب بخواهد با اتکا به دانش خود از پزشکی داخلی در بالغین قضاوت کند،در تشخیص یا درمان دچار اشتباه می شود و در دام طراح سوال می افتد.
(اگر وجود ندارد، رد کن.)

🔍 Critical Differentiator (دوئل تشخیصی):

Scenario: افتراق بین [Disease A] و [Disease B].

The Pivot: تنها داده‌ای که مدیریت را برمی‌گرداند چیست؟ (Lab، History یا Physical Exam)
(مثال: «اگر سؤال Symptom Z را اضافه کند، فوراً درمان عوض می‌شود.»)

💡 Management Trap (دام مدیریتی):

The Rush: اینترن‌ها کجا عجله می‌کنند و اشتباه مداخله می‌کنند؟

The Trap: مثال: «در [Condition] بلافاصله intubation نکن؛ اول X را stabilize کن.»

🧪 Hidden Association (همراهی‌های پنهان):

همراهی‌های سندرومیک یا عوارضی که گذرا ذکر شده‌اند ولی هدف محبوب طراح سؤال هستند
(مثال: Kawasaki → Coronary Aneurysm → زمان‌بندی Echo).

🚑 Killer Vignette (سناریوی قاتل):

یک سناریوی بالینی ۲–۳ جمله‌ای، بی‌رحمانه و فقط بر اساس دام‌های بالا.

Question: Next best step یا Diagnosis چیست؟

Answer: [پاسخ صحیح] چون [توضیح دام].

زبان و لحن

زبان: فارسی برای توضیحات.

ترمینولوژی: انگلیسی برای تمام Medical Terms (Diseases، Drugs، Signs، Labs).

لحن: تحلیلی، هشداردهنده، مختصر. بدون حاشیه.

متن به پیوست به صورت pdf ارسال می شود.
"""

# ================= منطق کارگر =================
def worker_task(worker_id, api_key, work_queue):
    api_tag = get_colored_api_tag(api_key)
    print(f"{api_tag} 🤖 استارت (سهمیه: {MAX_REQUESTS_PER_KEY}).")

    client = genai.Client(api_key=api_key)
    count = 0

    while True:
        if count >= MAX_REQUESTS_PER_KEY:
            print(f"{api_tag} {RED}سهمیه تمام شد.{RESET}")
            return

        try:
            filename = work_queue.get(timeout=1)
        except queue.Empty:
            return

        in_path = os.path.join(INPUT_DIR, filename)
        # اصلاح پسوند خروجی
        out_filename = filename.replace(".pdf", ".txt")
        # استفاده درست از نام جدید
        out_path = os.path.join(OUTPUT_DIR, out_filename)
        tmp_path = out_path + ".tmp"

        try:
            wait_for_green_light()
            print(f"{api_tag} ⏳ ارسال {filename}...")

            # خواندن فایل (با دندانه صحیح)
            with open(in_path, "rb") as f:
                pdf_data = f.read()

            if not pdf_data: raise ValueError("Empty File")

            # فراخوانی API
            resp = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=BASE_PROMPT),
                            types.Part.from_bytes(data=pdf_data, mime_type="application/pdf")
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                )
            )

            # ذخیره
            ans = clean_markdown(resp.text if resp.text else "")
            if ans:
                with open(tmp_path, "w", encoding="utf-8") as f: f.write(ans)
                os.replace(tmp_path, out_path)
                print(f"{api_tag} ✅ {out_filename} ذخیره شد.")
                STATS['success'] += 1
                count += 1
            else:
                raise ValueError("پاسخ خالی")

        except Exception as e:
            print(f"{api_tag} ❌ خطا در {filename}: {e}")
            if os.path.exists(tmp_path): os.remove(tmp_path)
            STATS['failed'] += 1
            count += 1
            time.sleep(2)

        finally:
            work_queue.task_done()

# ================= بدنه اصلی =================
def main():
    print(f"\n{YELLOW}--- 🚦 شروع با قانون ۳ ثانیه فاصله ---{RESET}")

    # پیدا کردن فایل‌های PDF
    files = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(".pdf")])
    
    # چک کردن فایل‌های TXT انجام شده
    todo = [f for f in files if not (
            os.path.exists(os.path.join(OUTPUT_DIR, f.replace(".pdf", ".txt"))) and
            os.path.getsize(os.path.join(OUTPUT_DIR, f.replace(".pdf", ".txt"))) > 0
        )]

    if not todo:
        print(f"{GREEN}کار تمام است!{RESET}")
        return

    print(f"تعداد فایل مانده: {len(todo)}")

    q = queue.Queue()
    for f in todo: q.put(f)

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
