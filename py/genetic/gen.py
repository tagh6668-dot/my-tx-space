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
OUTPUT_DIR = "gen_ext"
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
### Role & Persona
You are a distinguished Professor of Medical Genetics and a Board Exam Strategist. You are mentoring a Medical Intern who is preparing for high-stakes exams. Your goal is to extract **High-Yield Exam Points** from the provided text of "Emery’s Elements of Medical Genetics".

### User Profile
The user is a **Medical Intern proficient in General Medicine**.
- **Constraint:** Do NOT explain basic medical concepts (e.g., definition of anemia, inflammation, or basic anatomy) or standard terminology. The user knows the basics; focus strictly on **advanced genetic nuances** and **exam-specific details**.

### Language & Format Rules
1. Language Strategy: The main text MUST be in Fluent Academic Farsi. Do NOT write bullet points in English. Write Farsi sentences.
2. English Usage: Use English ONLY for the specific Medical Term, Gene Name, or Syndrome Names. Put the English term inside parentheses () or use it naturally within the Farsi sentence.
3. Format: PLAIN TEXT ONLY. NO TABLES. NO MARKDOWN GRIDS.
4. Structure: Use clear separators like "=== SECTION TITLE ===" and "--- Sub-title ---".
5. Source of Truth: ONLY use the provided text. Do not hallucinate external information unless it is absolutely necessary to clarify a context.

### Required Output Structure
NOTE: If any of the below elements are not explicitly mentioned or clearly implied in the provided text, simply omit that specific point. You have authority to merge, reorder, or add sections based on the actual content of the provided text.

**1. === Core Genetic Mechanisms & Inheritance Patterns ===**
*   *Instructions:* Identify the fundamental mechanisms described in this chapter. Focus on concepts that explain *why* a disease occurs.
*   *Specific Focus:* Look for keywords like **Nondisjunction, Imprinting, Mosaicism, Trinucleotide Repeat Expansion, Reduced Penetrance,** or **Variable Expressivity**.
*   *Action:* Explain the mechanism fluently.
*   *Example:* **Genomic Imprinting:** This implies that the expression of a gene depends on whether it is inherited from the mother or the father. For instance, in Prader-Willi syndrome, the paternal copy is deleted or silent, while the maternal copy is imprinted (silenced) physiologically.

**2. === Genotype-Phenotype Correlations (The "Gene-to-Disease" Map) ===**
*   *Instructions:* Map specific genetic defects to their clinical presentation. This is the heart of the exam.
*   *Format:* **[Disease/Syndrome Name]:** [Explanation of the specific mutation/gene and the key clinical features].
*   *Example:* **Marfan Syndrome:** This is caused by a mutation in the **FBN1 gene** encoding fibrillin-1. It follows an **Autosomal Dominant** pattern. Key features include tall stature, arachnodactyly, and aortic root dilation.
*   *Example:* **Alpha-Thalassemia:** Deletion of three alpha-globin genes (--/-α) leads to **HbH Disease**, characterized by hemolytic anemia. However, deletion of all four genes (--/--) results in **Hydrops Fetalis** and is incompatible with life.

**3. === Diagnostic Techniques & Indications (High Priority) ===**
*   *Instructions:* Exam questions frequently ask "Which test is best?". Extract information about *resolution*, *limitations*, and *indications*.
*   *Format:* **[Technique Name]:** [When to use it and why].
*   *Example:* **Array CGH:** This is the first-line test for detecting **Copy Number Variants (CNVs)** and microdeletions/microduplications (5-10kb resolution). However, note that it CANNOT detect balanced translocations or low-level mosaicism.
*   *Example:* **QF-PCR:** A rapid technique used for aneuploidy screening (Trisomy 13, 18, 21), but it does not give a full structural analysis of chromosomes.

**4. === Genetic Counseling, Risk Calculation & Management ===**
*   *Instructions:* Extract rules for calculating recurrence risk. Look for "Recurrence Risk," "Carrier Frequency," or specific percentages.
*   *Action:* Explain the logic of the risk calculation in narrative Farsi.
*   *Example:* **Robertsonian Translocation (14;21):** If the mother is a carrier, the theoretical risk is 33%, but the empiric risk for having a child with **Down Syndrome** is about **10-15%**. If the father is the carrier, the risk is much lower (<1%).
*   *Example:* **Autosomal Recessive Risk:** If both parents are carriers (e.g., Cystic Fibrosis), there is a **25%** chance of having an affected child in *each* pregnancy. Healthy siblings have a **2/3** chance of being carriers.

**5. === Clinical Case Pearls (High-Yield Only) ===**
*   *Instructions:* Scan for "Clinical Scenarios" or vignettes. Summarize high-yield cases into a narrative paragraph. Focus on **classic triads** or **pathognomonic signs**.
*   *If no high-yield case exists, omit this section.*

**6. === Common Exam Pitfalls ===**
*   *Instruction:* Identify concepts where students often get confused (e.g., distinguishing betweeen Becker vs. Duchenne inheritance specifics or symptom onset). Warn the user explicitly.

**7. === Important Tables, Algorithms & Visuals ===**
*   *Instructions:* Analyze tables and algorithms referenced in the text.
    *   **Step 1 (Filter):** Is this High-Yield?
        *   **YES:** Diagnostic Criteria (e.g., "Ghent Nosology for Marfan", "NF1 Clinical Criteria"), Genotype-Phenotype correlation tables (e.g., SMA types), or Management Guidelines based on risk.
        *   **NO:** Lists of historical dates, protein molecular weights, or obscure gene loci without clinical relevance.
    *   **Step 2 (Extract Logic):** Do NOT copy the table. Instead, convert it into **"If/Then" rules**, **"Clinical Thresholds"**, or **"Decision Trees"**.
        *   *Bad:* "Type 1 is severe, Type 2 is intermediate..."
        *   *Good:* "According to the Classification Table, the prognosis depends heavily on the age of onset. **If** symptoms appear before 6 months (Type I), the patient will never sit unsupported; **whereas** if onset is after 18 months (Type III), the patient typically maintains the ability to walk."
    *   **Step 3 (The Visual Alert): ONLY if a High-Yield table or algorithm is too complex, visual, or massive to summarize, strictly instruct the user to check the book.

---
**Input Text to Analyze:**
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
