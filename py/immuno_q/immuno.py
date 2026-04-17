import asyncio
import os
import time
import queue
import random
from google import genai
from google.genai import types

# ================= تنظیمات =================
MODEL_NAME = "gemini-3-flash-preview"
INPUT_DIR = "split"
OUTPUT_DIR = "immuno_q"
API_FILE = "api.txt"
TIMEOUT_SECONDS = 160  # حداکثر زمان (آپلود + پردازش)
PDF_RANGE = (25, 35)  # از 1.pdf تا 203.pdf

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
            if not line or line.startswith('#'):
                continue
            clean_key = line.replace('"', '').replace("'", "").rstrip(',')
            if clean_key:
                keys.append(clean_key)
    return keys

def get_colored_api_tag(api_key, index):
    try:
        color = API_COLORS[index % len(API_COLORS)]
        return f"{color}[...{api_key[-5:]}]{RESET}"
    except: return "[Key-?]"

# ================= پرامپت (دست‌نخورده) =================
BASE_PROMPT = """
# Role and Objective
You are a distinguished Professor of Clinical Immunology and a Senior Question Designer for the "Iranian Medical Residency Entrance Exam" (Azmoon-e Dastyari).

Your task is to analyze the provided **Immunology Textbook Chapter** (Matthew Helbert) and generate **3 to 5 Ultra-High-Yield MCQs**. Each question must test a DIFFERENT concept from the chapter (no overlap).

**CRITICAL GOAL:** You must design questions that **CANNOT** be answered solely by relying on general clinical knowledge (Pediatrics, Internal Medicine). The student MUST have read the specific **Molecular & Cellular details** in the provided Immunology text to answer correctly.

Boundary Control: Your questions must be strictly “Immunology-Centric.” Avoid generic Biochemistry (e.g., metabolic enzymes, ATP cycle) or Cell/Molecular Biology (e.g., general DNA replication, organelle functions) unless they are directly and uniquely tied to immune cell signaling or function. Focus on the immune system’s specific vocabulary: CD markers, HLA types, Cytokines, V(D)J recombination, and Immune Tolerance mechanisms.

# 1. The "Anti-Generalist Bypass" Protocol (Strict Rules)
To ensure the student cannot simply guess the answer based on clinical signs:
*   **Rule A (The Molecular Pivot):** Even if the clinical vignette clearly describes a disease (e.g., SCID, Asthma), DO NOT ask "What is the diagnosis?". Instead, ask about the **defective CD marker**, the **absent cytokine**, or the **transcription factor** involved.
*   **Rule B (Mechanism over Name):** Avoid listing simple disease names in options. Use **mechanism descriptions** or **molecular targets**.
    *   *Bad Option:* "Chronic Granulomatous Disease (CGD)"
    *   *Good Option:* "Defect in the gp91phox subunit of NADPH oxidase"
*   **Rule C (The Immunologic Nuance):** Focus on details specific to Immunology texts: Th1/Th2 balance, specific chemokine receptors (CCR/CXCR), or subtle distinctions in antibody functions (e.g., IgG subtypes).

# 2. Structure & Language
1.  **Language:** The entire output (Stem, Options, Analysis) must be in **Academic Medical Persian (Farsi)** mixed with English technical terms.
2.  **Format:**
    *   **Clinical Vignette:** High-quality Persian description (symptoms, history).
    *   **The Pivot:** A transition to Lab/Flow Cytometry/Genetic findings.
    *   **The Question:** Asking for the specific immunologic detail.

# 3. Question Types to Generate (Immunology Style)

*   **Type 1: The "Flow Cytometry/Marker Trap"**
    *   *Stem:* Clinical scenario suggesting an Immunodeficiency or Lymphoma.
    *   *Question:* "در بررسی فلوسایتومتری این بیمار، عدم بیان کدام مارکر سطحی یا درون‌سلولی مورد انتظار است؟" (Which marker is absent?)
    *   *Options:* Specific CD markers (e.g., CD40L, BTK, CD3, CD19).

*   **Type 2: The "Cytokine & Signaling Pathway"**
    *   *Stem:* A description of a pathogen response or allergic reaction.
    *   *Question:* "اختلال در مسیر سیگنالینگ کدام سایتوکاین یا فاکتور رونویسی (Transcription Factor) توجیه‌کننده این تظاهرات است؟"
    *   *Options:* Specific pairs (e.g., IL-12/IFN-gamma, STAT3, GATA3).

*   **Type 3: The "Mechanism of Therapy/Hypersensitivity"**
    *   *Stem:* A patient receiving a specific biologic drug or experiencing a specific reaction (Type I-IV).
    *   *Question:* "مکانیسم دقیق مولکولی که منجر به این تظاهرات شده است، چیست؟"
    *   *Options:* Detailed mechanisms (e.g., "Cross-linking of IgE on Mast cells" vs "Immune Complex Deposition").

# Output Structure for Each Question

=== سوال [شماره] ===

**متن سوال:**
[Clinical Scenario (Persian) + **Critical Immunologic Context**].
[Question asking for a detail found ONLY in the text, not general medicine].

**گزینه‌ها:**
الف) [Specific Molecule / Gene / Mechanism]
ب) [Distractor - Plausible but wrong mechanism]
ج) [Distractor - Related to a similar clinical disease]
د) [Distractor]

**پاسخ صحیح:** [گزینه]

**تحلیل و استناد به متن (Analysis):**
[Explain in Farsi. Explicitly state: "Clinically this looks like [Disease], but the text specifies that the underlying defect is [Mechanism/Gene]." Quote the logic from the text.]

**دام آموزشی (Trap):**
[Why would a student answering based on General Medicine knowledge choose the wrong option? e.g., Confusing X-linked Agammaglobulinemia with CVID].

#Output Rules (Strict Adherence)
Source of Truth: ONLY use the provided text.
Format: Plain text suitable for a .txt file. Use clear headings.

---
Input Text to Analyze:
[Wait for User PDF Content]

---
"""

# ================= منطق اصلی پردازش =================

def process_pdf_sync(api_key, filename):
    """
    آپلود PDF + درخواست به مدل + ذخیره اتمیک (سینکرون)
    """
    ctx = API_CONTEXTS[api_key]
    client = ctx['client']
    
    pdf_path = os.path.join(INPUT_DIR, filename)
    output_filename = filename.replace(".pdf", ".txt")
    out_path = os.path.join(OUTPUT_DIR, output_filename)
    tmp_path = out_path + ".tmp"

    uploaded_file = None
    try:
        # 1. آپلود فایل
        with open(pdf_path, "rb") as f:
            uploaded_file = client.files.upload(
                file=f,
                config=types.UploadFileConfig(
                    display_name=filename,
                    mime_type="application/pdf"
                )
            )

        # انتظار برای پردازش فایل توسط گوگل
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(1)
            uploaded_file = client.files.get(name=uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
            raise ValueError("آپلود فایل در گوگل FAILED شد.")

        # 2. ارسال درخواست
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=uploaded_file.uri,
                        mime_type=uploaded_file.mime_type
                    ),
                    types.Part.from_text(text=BASE_PROMPT),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
            )
        )

        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=generate_content_config,
        )

        full_text = resp.text if resp.text else ""
        
        if not full_text:
            raise ValueError("پاسخ مدل خالی بود.")

        # 3. ذخیره اتمیک
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        os.replace(tmp_path, out_path)
        
        return True

    finally:
        # 4. پاکسازی فایل از سرور گوگل (بسیار مهم)
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except:
                pass

async def process_task_wrapper(api_key, filename):
    """
    رپر Async برای مدیریت تایم‌اوت، خطاها و منطق ۳ بار تلاش
    """
    ctx = API_CONTEXTS[api_key]
    tag = ctx['tag']
    
    print(f"{tag} {WAIT_ICON} شروع آپلود و پردازش {filename}...")
    loop = asyncio.get_running_loop()

    try:
        # اجرای تابع سینکرون در ترد جداگانه با تایم‌اوت
        await asyncio.wait_for(
            loop.run_in_executor(None, process_pdf_sync, api_key, filename),
            timeout=TIMEOUT_SECONDS
        )
        
        print(f"{tag} {SUCCESS_ICON} {GREEN}{filename} با موفقیت استخراج شد.{RESET}")
        ctx['consecutive_errors'] = 0 
        
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
    print(f"\n{YELLOW}--- 🚀 شروع استخراج نلسون (PDF Processing) ---{RESET}")

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

    todo_files = []
    skipped_count = 0

    # حلقه روی اعداد ۱ تا ۲۰۳
    for i in range(PDF_RANGE[0], PDF_RANGE[1] + 1):
        filename = f"{i}.pdf"
        in_path = os.path.join(INPUT_DIR, filename)
        out_txt_name = f"{i}.txt"
        out_path = os.path.join(OUTPUT_DIR, out_txt_name)

        if not os.path.exists(in_path):
            # اگر فایل PDF شماره X وجود ندارد، رد می‌کنیم
            continue

        # اگر فایل خروجی وجود دارد و خالی نیست، رد کن (Resume)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            skipped_count += 1
        else:
            todo_files.append(filename)

    if skipped_count > 0:
        print(f"{GREEN}⏭️  تعداد {skipped_count} فایل از قبل پردازش شده بود.{RESET}")
    
    if not todo_files:
        print(f"{GREEN}{SUCCESS_ICON} همه فایل‌ها قبلاً پردازش شده‌اند. پایان.{RESET}")
        return

    print(f"📌 {len(todo_files)} فایل PDF جدید در صف پردازش قرار گرفت.\n")

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
        
        # تاخیر شانسی بین شلیک‌ها
        if file_index < total_files:
            sleep_time = random.uniform(2, 5)
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
