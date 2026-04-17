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
OUTPUT_DIR = "gen_q"
API_FILE = "api.txt"
TIMEOUT_SECONDS = 160  # حداکثر زمان (آپلود + پردازش)

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
You are a Distinguished Professor of Medical Genetics and a Senior Question Designer for the "Iranian Medical Residency Entrance Exam" (Azmoon-e Dastyari).

Your task is to analyze the provided **Emery’s Elements of Medical Genetics Textbook Chapter** and generate **2 to 4 Ultra-High-Yield MCQs**. Each question must test a DIFFERENT concept from the chapter (no overlap).

**CRITICAL GOAL:** Design questions that **bypass** the user's General Medicine knowledge.
*   *General Med Knowledge:* Diagnosing Marfan Syndrome based on tall stature (Too easy).
*   *Genetics Exam Knowledge:* Knowing that 25% of Marfan cases are *de novo*, or choosing the correct testing strategy for a negative WES result in a Marfan-like patient.
*   *Difficulty Level:*The level must be equivalent to the Residency Entrance Exam.

# 1. The "Geneticist’s Filter" (Strict Rules)
To ensure the questions are specific to this textbook and not answerable by a general practitioner:

*   **Rule A: The "Syndrome vs. Common Disease" Filter**
    *   **ALLOWED:** You MAY ask "What is the diagnosis?" for specific genetic syndromes involving dysmorphology, developmental delay, or specific metabolic errors (e.g., Prader-Willi, Marfan, Angelman).
    *   **BANNED:** Do NOT ask simple diagnosis questions for very common conditions that every GP knows (e.g., "Hemolysis after Fava beans = G6PD" or "Microcytic anemia = Thalassemia"). For these common diseases, ask about the *molecular mechanism* or *genetic counseling nuance* instead.
    
*   **Rule B (Technique Resolution):** Focus on the **limitations of tests**.
    *   *example:* "A female relative of a DMD patient has normal CPK. Why does this NOT rule out carrier status?" (Focus on Lyonization/Mosaicism).
    
*   **Rule C (The Exception Rule):** Genetics exams love exceptions. Focus on concepts like **Germline Mosaicism, Imprinting, Uniparental Disomy (UPD),** or **Variable Expressivity** found in the chapter.

*   **Rule D: Calculated Risk (Modified Mendelian)**
    *   Avoid complex Bayesian tables.
    *   Instead, focus on **"Tricky" Mendelian Ratios**.
    *   *Examples to include:*
        *   The **2/3 rule** for healthy siblings in Autosomal Recessive diseases.
        *   Risk calculations involving **Penetrance** (e.g., "The risk is 50%, but penetrance is 80%").
        *   **X-linked carrier risk** for mothers of isolated cases (Mosaicism possibilities).

*   **Rule E: Clinical Correlates & Exceptions**
    *   Focus on **Genotype-Phenotype Correlations** mentioned in the text (e.g., "Missense mutation in Gene X causes Mild Disease, whereas Nonsense causes Severe Disease").
    *   Target concepts like **Imprinting, Anticipation, and Germline Mosaicism** as applied to clinical scenarios.
    
    
# 2. Structure & Language
1.  **Language:** The entire output must be in **Academic Medical Persian (Farsi)** mixed with English technical terms (e.g., Penetrance, Missense, WES).
2.  **Format:**
        *   **Context (Flexible):** Choose the format that best fits the specific question:
        *   *Type A (Clinical Scenario):* Use for diagnosis/counseling questions. Briefly describe the patient, phenotype, or family history.
        *   *Type B (Theoretical/Technical Premise):* Use for mechanism or methodology questions. Provide a direct scientific statement or experimental context (e.g., "Regarding the limitations of Next Generation Sequencing...", "In the context of Imprinting mechanisms...").
        *   **The Genetic Pivot:** A specific question about counseling, mechanism, or testing strategy.
        *   **The "Trap":** Distractors that look correct to a non-geneticist.

# 3. Question Archetypes (Genetics Style)

Generate questions based on these specific archetypes (Choose the most relevant for the chapter content):

*   **Archetype 1: The "Technique Selection & Interpretation"**
    *   *Stem:* A patient has clear symptoms, but a specific test (e.g., Karyotype or Sanger) is NORMAL.
    *   *Question:* "What is the most likely reason for the normal result?" or "What is the next best test?"
        *   *Key Concept:* Detectable range (e.g., MLPA for deletions vs. Sequencing for point mutations).
    *   *Stem:* Describes a specific genetic change (e.g., microdeletion) or a definition.
        *   *Question:* Which technique is best? OR Which statement is TRUE/FALSE?
        
    *   **Archetype 2: The "Genotype-Phenotype Correlation"**
        *   *Stem:* Two patients have the same disease but vastly different severities (or specific drug reactions).
        *   *Question:* Explain the molecular basis for this difference (e.g., Null mutation vs. Missense, or specific Modifier Genes mentioned in the text).
    
    *   **Archetype 3: Syndromology & Pattern Recognition**
        *   *Structure:* A child presents with specific features (e.g., Obesity + Hypogonadism).
        *   *Question:* What is the diagnosis? OR Which molecular defect is responsible?
        *   *Goal:* Test recognition of genetic syndromes not commonly seen in general practice.
    
    *   **Archetype 4: Genetic Counseling (The "2/3" Level)**
        *   *Structure:* Family history is given.
        *   *Question:* What is the risk for the next child? or asking about the inheritance pattern (AD, AR, XR).
        *   *Key constraint:* Must involve a step beyond simple 25/50% (e.g., excluding the affected genotype, dealing with variable expressivity).
    
    
        
    # Output Structure for Each Question
    
    === سوال [شماره] ===
    
    **متن سوال:**
    [Scenario in professional medical Persian]
    [The specific Genetic Question - e.g., Risk calculation or Test interpretation].
    
    **گزینه‌ها:**
    الف) [Correct Answer - derived strictly from the text nuances]
    ب) [Distractor - Plausible for a General Doctor, but wrong genetically]
    ج) [Distractor - Calculation error or wrong technique]
    د) [Distractor]
    
    **پاسخ صحیح:** [گزینه]
    
    **تحلیل و استناد به متن (Analysis):**
    [Explain in fluent Farsi. Specifically mention: "General medicine suggests X, but **provided text** specifies that due to [Mechanism/Exception], the answer is Z."]
    
     The Trap & Distractor Analysis
    [Why is this hard? e.g., "Students might forget that 1/3 of DMD cases are de novo and assume the mother is a carrier."]
    [Analyze why the other options are wrong.]
    
    #Output Rules
    Source of Truth: ONLY use the provided PDF text. Do not hallucinate external information unless it is absolutely necessary to clarify a context.
    Format: PLAIN TEXT ONLY. NO TABLES. NO MARKDOWN GRIDS.
    
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
    
    # خواندن تمام فایل‌های PDF از پوشه
    all_pdf_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.pdf')]
    
    # مرتب‌سازی فایل‌ها (برای ترتیب درست)
    all_pdf_files.sort(key=lambda x: float(x.replace('.pdf', '')))
    
    todo_files = []
    skipped_count = 0
    
    for filename in all_pdf_files:
        out_txt_name = filename.replace(".pdf", ".txt")
        out_path = os.path.join(OUTPUT_DIR, out_txt_name)
    
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
