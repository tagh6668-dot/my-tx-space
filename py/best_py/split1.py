import asyncio
import os
import time
import queue
import random
from google import genai
from google.genai import types

# ================= تنظیمات ظاهری و رنگ‌ها =================
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
BLUE = '\033[94m'
LIGHT_GREEN = '\033[92m'
LIGHT_YELLOW = '\033[93m'
LIGHT_BLUE = '\033[94m'
LIGHT_MAGENTA = '\033[95m'

SUCCESS_ICON = "✅"
ERROR_ICON = "❌"
WARNING_ICON = "⚠️"
WAIT_ICON = "⏳"
ROBOT_ICON = "🤖"
SKIP_ICON = "⏭️"

# ================= تنظیمات پروژه =================
PDF_PATH = "exam.pdf"
BATCH_SIZE = 20
TOTAL_QUESTIONS = 200
MODEL_NAME = "gemini-3-flash-preview"
API_FILE = "api1.txt"
TIMEOUT_SECONDS = 80  # حداکثر زمان انتظار برای جواب
OUTPUT_DIR = "raw_batches"

# لیست User Agent ها (کروم و سافاری)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# رنگ‌های اختصاصی
API_COLORS = [CYAN, MAGENTA, BLUE, LIGHT_GREEN, LIGHT_YELLOW, LIGHT_BLUE, LIGHT_MAGENTA]

# ساختار نگهداری وضعیت زنده (Live) برای هر API
API_CONTEXTS = {}

# پوشه خروجی
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
            if not line or line.startswith('#'):
                continue
            clean_key = line.replace('"', '').replace("'", "").rstrip(',')
            if clean_key:
                keys.append(clean_key)
    return keys

def play_error_sound():
    """پخش صدای بیپ در صورت خطا (لینوکس/مک)"""
    os.system('play -q -n synth 0.1 sin 880 >/dev/null 2>&1 &')

def get_colored_tag(api_key, index):
    """ساخت تگ رنگی"""
    color = API_COLORS[index % len(API_COLORS)]
    return f"{color}[...{api_key[-5:]}]{RESET}"

# ================= منطق آماده‌سازی (Setup) =================

def setup_api_client(api_key, index):
    """ایجاد کلاینت و آپلود فایل برای یک کلید خاص"""
    user_agent = USER_AGENTS[index % len(USER_AGENTS)]
    
    try:
        client = genai.Client(
            api_key=api_key,
            http_options={'headers': {'User-Agent': user_agent}}
        )

        with open(PDF_PATH, "rb") as f:
            uploaded_file = client.files.upload(
                file=f,
                config=types.UploadFileConfig(
                    display_name="Exam File",
                    mime_type="application/pdf"
                )
            )

        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            raise ValueError("وضعیت فایل FAILED شد.")

        return {
            'client': client,
            'file': uploaded_file,
            'consecutive_errors': 0,
            'total_sent': 0,
            'total_failed': 0,
            'active': True,
            'tag': get_colored_tag(api_key, index)
        }

    except Exception as e:
        print(f"{get_colored_tag(api_key, index)} {RED}خطا در آماده‌سازی اولیه: {e}{RESET}")
        return None

# ================= منطق پردازش تک درخواست =================

def process_batch_sync(api_key, start_num, end_num):
    """
    اجرای درخواست به صورت سینکرون و ذخیره اتمیک
    """
    ctx = API_CONTEXTS[api_key]
    client = ctx['client']
    uploaded_file = ctx['file']
    
    prompt_text = f"""
    از فایل PDF، متن سوالات شماره {start_num} تا {end_num} را استخراج کن.
    فرمت خروجی:
    [[سوال X]]
    متن سوال...
    گزینه‌ها...
    """

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type=uploaded_file.mime_type
                ),
                types.Part.from_text(text=prompt_text),
            ],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level="HIGH",
        )
    )

    full_text = ""
    response_stream = client.models.generate_content_stream(
        model=MODEL_NAME,
        contents=contents,
        config=generate_content_config,
    )

    for chunk in response_stream:
        if chunk.text:
            full_text += chunk.text

    if not full_text:
        raise ValueError("پاسخ مدل خالی بود.")

    # === قابلیت شماره 1: نوشتن اتمیک (Atomic Write) ===
    final_filename = os.path.join(OUTPUT_DIR, f"batch_{start_num}_{end_num}.txt")
    temp_filename = final_filename + ".tmp"
    
    # ابتدا در فایل تمپ می‌نویسیم
    with open(temp_filename, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    # سپس نام آن را تغییر می‌دهیم (این عملیات اتمیک است)
    os.replace(temp_filename, final_filename)
    
    return True

async def process_task_wrapper(api_key, start_num, end_num):
    """
    رپر برای مدیریت تایم‌اوت و خطا
    """
    ctx = API_CONTEXTS[api_key]
    tag = ctx['tag']
    batch_name = f"دسته {start_num}-{end_num}"

    print(f"{tag} {WAIT_ICON} شلیک درخواست برای {batch_name} (Fire)...")

    loop = asyncio.get_running_loop()
    
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, process_batch_sync, api_key, start_num, end_num),
            timeout=TIMEOUT_SECONDS
        )
        
        print(f"{tag} {SUCCESS_ICON} {GREEN}دریافت پاسخ {batch_name} موفق بود.{RESET}")
        ctx['consecutive_errors'] = 0 
        
    except asyncio.TimeoutError:
        print(f"{tag} {RED}{WAIT_ICON} تایم‌اوت ({TIMEOUT_SECONDS}s) برای {batch_name}!{RESET}")
        ctx['total_failed'] += 1
        ctx['consecutive_errors'] += 1
        play_error_sound()
        
    except Exception as e:
        print(f"{tag} {RED}{ERROR_ICON} خطا در {batch_name}: {e}{RESET}")
        ctx['total_failed'] += 1
        ctx['consecutive_errors'] += 1
        play_error_sound()

    if ctx['consecutive_errors'] >= 3:
        if ctx['active']:
            print(f"{tag} {RED}⛔ این API سه بار خطا داد و متوقف شد.{RESET}")
            ctx['active'] = False

# ================= حلقه اصلی (Main Loop) =================

async def main():
    print(f"\n{YELLOW}--- 🚀 شروع استخراج هوشمند (Resume & Atomic Save) ---{RESET}")
    
    # 1. بارگذاری کلیدها
    raw_keys = load_api_keys(API_FILE)
    if not raw_keys:
        print(f"{RED}هیچ کلیدی پیدا نشد. خروج.{RESET}")
        return

    # 2. ایجاد صف کار با بررسی فایل‌های موجود (Resume Capability)
    work_queue = []
    skipped_count = 0
    
    print(f"{CYAN}در حال بررسی فایل‌های قبلی...{RESET}")
    for start_num in range(1, TOTAL_QUESTIONS + 1, BATCH_SIZE):
        end_num = min(start_num + BATCH_SIZE - 1, TOTAL_QUESTIONS)
        
        # === قابلیت شماره 2: بررسی وجود فایل ===
        expected_filename = os.path.join(OUTPUT_DIR, f"batch_{start_num}_{end_num}.txt")
        if os.path.exists(expected_filename):
            skipped_count += 1
            # print(f"{SKIP_ICON} دسته {start_num}-{end_num} قبلاً انجام شده.") # اختیاری: چاپ برای دیباگ
        else:
            work_queue.append((start_num, end_num))
    
    total_tasks = len(work_queue)
    
    if skipped_count > 0:
        print(f"{GREEN}{SKIP_ICON} تعداد {skipped_count} دسته از قبل موجود بود و رد شد.{RESET}")
    
    if total_tasks == 0:
        print(f"{GREEN}{SUCCESS_ICON} همه کارها قبلاً انجام شده‌اند! پایان.{RESET}")
        return

    print(f"📌 {total_tasks} دسته سوال جدید برای پردازش باقی مانده است.\n")

    # 3. آماده‌سازی و آپلود فایل (فقط اگر کاری مانده باشد)
    print(f"{CYAN}در حال آماده‌سازی و آپلود PDF برای {len(raw_keys)} کلید...{RESET}")
    valid_keys_list = []
    
    loop = asyncio.get_running_loop()
    setup_tasks = []
    
    for i, key in enumerate(raw_keys):
        setup_tasks.append(loop.run_in_executor(None, setup_api_client, key, i))
    
    results = await asyncio.gather(*setup_tasks)
    
    for i, res in enumerate(results):
        key = raw_keys[i]
        if res:
            API_CONTEXTS[key] = res
            valid_keys_list.append(key)
            print(f"{res['tag']} {SUCCESS_ICON} آماده شد.")
    
    if not valid_keys_list:
        print(f"{RED}هیچ API آماده به کاری وجود ندارد.{RESET}")
        return

    # 4. حلقه دیسپچر (Round Robin Fire and Forget)
    tasks_in_flight = []
    key_index = 0
    task_index = 0

    while task_index < total_tasks:
        # انتخاب کلید فعال
        attempts = 0
        selected_key = None
        
        while attempts < len(valid_keys_list):
            candidate_key = valid_keys_list[key_index % len(valid_keys_list)]
            if API_CONTEXTS[candidate_key]['active']:
                selected_key = candidate_key
                key_index = (key_index + 1) % len(valid_keys_list)
                break
            key_index += 1
            attempts += 1
        
        if not selected_key:
            print(f"{RED}⛔ همه APIها غیرفعال شده‌اند!{RESET}")
            break

        # برداشتن تسک
        start_num, end_num = work_queue[task_index]
        
        API_CONTEXTS[selected_key]['total_sent'] += 1
        
        # شلیک
        coro = process_task_wrapper(selected_key, start_num, end_num)
        task = asyncio.create_task(coro)
        tasks_in_flight.append(task)
        
        task_index += 1
        
        if task_index < total_tasks:
            sleep_time = random.uniform(2, 5)
            print(f"{ROBOT_ICON} ... انتظار {sleep_time:.1f} ثانیه ...")
            await asyncio.sleep(sleep_time)

    # 5. انتظار نهایی
    print(f"\n{YELLOW}شلیک‌ها تمام شد. منتظر دریافت پاسخ‌های آخر...{RESET}")
    if tasks_in_flight:
        await asyncio.gather(*tasks_in_flight)

    # 6. پاکسازی
    print("\n🗑️ پاکسازی فایل‌ها از سرور...")
    for ctx in API_CONTEXTS.values():
        try:
            if ctx['active'] or ctx['client']:
                ctx['client'].files.delete(name=ctx['file'].name)
        except:
            pass

    # ================= گزارش نهایی =================
    print("\n" + "-" * 40)
    print("📊 " + YELLOW + "گزارش نهایی عملکرد API ها" + RESET)
    print("-" * 40)

    grand_total_sent = 0
    grand_total_failed = 0

    for api_key in valid_keys_list:
        ctx = API_CONTEXTS[api_key]
        sent = ctx['total_sent']
        failed = ctx['total_failed']
        tag = ctx['tag']
        
        grand_total_sent += sent
        grand_total_failed += failed

        status_icon = SUCCESS_ICON if failed == 0 else (WARNING_ICON if failed < sent else ERROR_ICON)
        status_color = GREEN if failed == 0 else (YELLOW if failed < sent else RED)
        
        active_status = "" if ctx['active'] else "(⛔ متوقف شد)"

        if sent > 0:
            print(f"{tag} : {status_icon} {status_color}ارسال: {sent} | خطا: {failed} {active_status}{RESET}")
        else:
            print(f"{tag} : ⚪ بدون استفاده")

    print("-" * 40)
    print(f"مجموع درخواست‌ها: {grand_total_sent}")
    print(f"مجموع خطاها: {grand_total_failed}")
    if skipped_count > 0:
        print(f"تعداد دسته‌های از قبل انجام شده (Skip): {skipped_count}")

    if grand_total_failed == 0 and grand_total_sent > 0:
        print(f"{GREEN}{SUCCESS_ICON} عملیات عالی بود!{RESET}")
    elif grand_total_failed > 0:
        print(f"{RED}تعدادی خطا داشتیم، لاگ‌ها را بررسی کنید.{RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{RED}⛔ توقف دستی توسط کاربر.{RESET}")
