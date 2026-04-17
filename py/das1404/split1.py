import asyncio
import os
import time
import queue
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

# ================= تنظیمات پروژه =================
PDF_PATH = "exam.pdf"        
BATCH_SIZE = 20              
TOTAL_QUESTIONS = 200        
MODEL_NAME = "gemini-3-flash-preview"

# لیست کلیدهای API
API_KEYS = [
    "AIzaSyACWTqS5CDb87wF_6Nqjaw3mTNX8T4Fylc",
    "AIzaSyAUF13O8M53dXnkf95NkQnj297FBEXvoek",
    "AIzaSyA8yufViHavTBz8CHeX_UI4Ud-zNxf-fnw",
    "AIzaSyA3qk8y29ivUQa232YrBN6IgXlYDIe-IlI",
    "AIzaSyCXQGPCwqIMAwE5Xv05IrId8J7f2o4RF6k",
    "AIzaSyBVYksmeZJEQIN9tk7s9H1NZoWzhDNSi0M"
]

# رنگ‌های اختصاصی برای هر کلید
API_COLORS = [CYAN, MAGENTA, BLUE, LIGHT_GREEN, LIGHT_YELLOW, LIGHT_BLUE, LIGHT_MAGENTA]

# ساختار برای نگهداری آمار
API_STATS = {key: {'assigned': 0, 'failed': 0} for key in API_KEYS}

# پوشه خروجی
os.makedirs("raw_batches", exist_ok=True)

# ================= توابع کمکی =================

def play_error_sound():
    """پخش صدای بیپ در صورت خطا (لینوکس/مک)"""
    os.system('play -q -n synth 0.1 sin 880 >/dev/null 2>&1 &')

def get_colored_api_tag(api_key):
    """ساخت تگ رنگی برای نمایش خلاصه کلید"""
    try:
        key_index = API_KEYS.index(api_key)
        color = API_COLORS[key_index % len(API_COLORS)]
        return f"{color}[...{api_key[-5:]}]{RESET}"
    except ValueError:
        return f"[...{api_key[-5:]}]"

# ================= منطق اصلی (Worker) =================

def worker_process(worker_id, api_key, task_queue):
    """
    اجرای منطق استخراج در ترد جداگانه (بدون قابلیت سرچ)
    """
    api_tag = get_colored_api_tag(api_key)
    print(f"{api_tag} {ROBOT_ICON} کارگر {worker_id} آماده است.")

    # 1. ساخت کلاینت
    client = genai.Client(api_key=api_key)
    
    uploaded_file = None
    
    # 2. آپلود فایل PDF
    try:
        print(f"{api_tag} {WAIT_ICON} در حال آپلود فایل PDF...")
        with open(PDF_PATH, "rb") as f:
            # تغییر اصلی اینجاست: افزودن mime_type
            uploaded_file = client.files.upload(
                file=f,
                config=types.UploadFileConfig(
                    display_name="Exam File",
                    mime_type="application/pdf"  # مشخص کردن نوع فایل الزامی شد
                )
            )
        
        # انتظار برای پردازش فایل
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise ValueError("وضعیت فایل FAILED شد.")
            
        print(f"{api_tag} {SUCCESS_ICON} فایل آماده شد.")

    except Exception as e:
        print(f"{api_tag} {RED}{ERROR_ICON} خطا در آپلود فایل: {e}{RESET}")
        play_error_sound()
        # ثبت خطا در آمار (حتی اگر هنوز کاری تخصیص نیافته باشد)
        API_STATS[api_key]['failed'] += 1
        return

    # 3. پردازش صف سوالات
    while True:
        try:
            # دریافت تسک بدون انتظار طولانی
            start_num, end_num = task_queue.get(block=False)
        except queue.Empty:
            break # پایان کار

        API_STATS[api_key]['assigned'] += 1
        
        batch_name = f"دسته {start_num}-{end_num}"
        print(f"{api_tag} {WAIT_ICON} شروع استخراج {batch_name}...")

        prompt_text = f"""
        از فایل PDF، متن سوالات شماره {start_num} تا {end_num} را استخراج کن.
        فرمت خروجی:
        [[سوال X]]
        متن سوال...
        گزینه‌ها...
        """

        # 4. آماده‌سازی محتوا
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

        # 5. کانفیگ (بدون Tools/Search و بدون Temperature)
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
            )
        )

        try:
            full_text = ""
            
            # ارسال درخواست به مدل
            response_stream = client.models.generate_content_stream(
                model=MODEL_NAME,
                contents=contents,
                config=generate_content_config,
            )

            for chunk in response_stream:
                if chunk.text:
                    full_text += chunk.text

            # ذخیره خروجی
            if full_text:
                batch_filename = f"raw_batches/batch_{start_num}_{end_num}.txt"
                with open(batch_filename, "w", encoding="utf-8") as f:
                    f.write(full_text)
                print(f"{api_tag} {SUCCESS_ICON} {GREEN}{batch_name} با موفقیت ذخیره شد.{RESET}")
            else:
                raise ValueError("پاسخ مدل خالی بود.")

        except Exception as e:
            print(f"{api_tag} {RED}{ERROR_ICON} خطا در {batch_name}: {e}{RESET}")
            play_error_sound()
            API_STATS[api_key]['failed'] += 1
        
        finally:
            task_queue.task_done()

    # پاکسازی فایل از سرور
    try:
        client.files.delete(name=uploaded_file.name)
        print(f"{api_tag} 🗑️ فایل حذف شد.")
    except:
        pass

async def main():
    print(f"\n{YELLOW}--- 🚀 شروع استخراج آفلاین (بدون سرچ) با {MODEL_NAME} ---{RESET}")
    print(f"تعداد کلیدهای فعال: {len(API_KEYS)}")
    print("-" * 40)

    work_queue = queue.Queue()
    
    total_batches = 0
    for start_num in range(1, TOTAL_QUESTIONS + 1, BATCH_SIZE):
        end_num = min(start_num + BATCH_SIZE - 1, TOTAL_QUESTIONS)
        work_queue.put((start_num, end_num))
        total_batches += 1
    
    print(f"📌 {total_batches} دسته سوال در صف قرار گرفت.\n")

    loop = asyncio.get_running_loop()
    tasks = []
    
    # اجرای همزمان کارگرها
    for i, api_key in enumerate(API_KEYS):
        tasks.append(
            loop.run_in_executor(None, worker_process, i+1, api_key, work_queue)
        )

    await asyncio.gather(*tasks)

    # ================= گزارش نهایی =================
    print("\n" + "-" * 30)
    print("📊 " + YELLOW + "آمار نهایی عملکرد هر کلید API" + RESET)
    print("-" * 30)
    
    total_failed = 0
    for api_key, stats in API_STATS.items():
        # نمایش آمار حتی اگر فقط آپلود فیل شده باشد (assigned=0 اما failed>0)
        if stats['assigned'] > 0 or stats['failed'] > 0:
            api_tag = get_colored_api_tag(api_key)
            failed_count = stats['failed']
            assigned_count = stats['assigned']
            total_failed += failed_count
            
            if failed_count == 0:
                status_color = GREEN
                status_icon = SUCCESS_ICON
            elif failed_count < assigned_count or assigned_count == 0: # اگر همه فیل شدند یا تعدادی
                status_color = RED
                status_icon = ERROR_ICON
            else:
                status_color = YELLOW
                status_icon = WARNING_ICON
            
            print(f"{api_tag} : {status_icon} {status_color}{failed_count} خطا (از {assigned_count} درخواست){RESET}")

    print("-" * 30)
    if total_failed == 0:
        print(f"{GREEN}{SUCCESS_ICON} عملیات با موفقیت کامل انجام شد!{RESET}")
    else:
        print(f"{RED}{WARNING_ICON} عملیات تمام شد اما {total_failed} خطا داشتیم.{RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{RED}⛔ توقف دستی توسط کاربر.{RESET}")
