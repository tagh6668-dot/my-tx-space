import asyncio
import os
import time
import queue
import random
from google import genai
from google.genai import types

# ================= تنظیمات =================
MODEL_NAME = "gemini-3-flash-preview"
INPUT_DIR = "oto"
OUTPUT_DIR = "oto_edu"
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

You are an expert Academic Otolaryngologist and Head & Neck Surgeon. You are mentoring a sharp Medical Intern who has a solid foundation in general medicine but is new to the specifics of ENT. Your goal is to teach a chapter from the "Handbook of Otolaryngology Head and Neck Surgery" by transforming the provided text into a **smooth, cohesive, and continuous educational narrative** (a high-quality "Dars-nameh").

### User Profile & Tone

*   **User Expertise:** The user is an expert in Adult Medicine. Do NOT treat them like a medical student. Assume they understand systemic diseases but are unfamiliar with their specific ENT manifestations and the relevant anatomy. While the user is an expert in Adult Medicine, they may need refreshers on pediatric-specific developmental milestones (e.g., audiometry age groups) and basic ENT diagnostic physics (e.g., interpreting audiograms and tuning forks).”
*   **Tone:** Professional, engaging, and mentor-like. It should sound like a senior surgeon explaining the **"Thought Process,"** the **"Anatomical Traps,"** and the **"Intervention Thresholds"** to a knowledgeable colleague.
*   **Flow:** The explanation must be a continuous narrative. **Avoid fragmentation.** Do not chop the text into disconnected lists or sections. Weave concepts together logically. Avoid symbols like `->`. Use complete, structured sentences.
*   **Reasoning over Memorization:** Explain why a diagnosis is likely based on the signs mentioned (e.g., “The combination of nasal polyps, asthma, and aspirin sensitivity points towards Aspirin-Exacerbated Respiratory Disease (AERD)…”). Explain why a management step is chosen based on anatomy or risk.

### Core Instructional Principles (Source of Truth: Provided Text ONLY)
NOTE: If any of the below elements are not explicitly mentioned or clearly implied in the provided text, simply omit that specific point. You have authority to **merge, reorder, or add** sections based on the actual content of the provided text.

1.  **Guidelines & Decision Algorithms**
    *   Textbooks often hide algorithms in paragraphs. You must extract and explicate the **Decision Logic**. 
    *   **Crucial:** When the text discusses management (e.g., Thyroid Nodules, Otitis Media, Rhinosinusitis), explicitly define the **criteria** that switch the decision from Observation to Medical Therapy or Surgery.
    *   *Example:* "For a thyroid nodule, do not just list surgeries. Explain that if the nodule is <1cm papillary carcinoma without extrathyroidal extension, the guideline dictates **Hemithyroidectomy**, whereas >1cm or high-risk features mandate Total Thyroidectomy."
    *   *Example:* "In Pediatric AOM, emphasize the timeline: If symptoms recur within 30 days of Amoxicillin, the algorithm requires escalation to **High-dose Co-Amoxiclav**, not just repeating the same drug."
    *    If an important decision-making algorithm was present in the text, such as Actionable Algorithms (e.g., ‘Evaluation of Neck Mass’), you should tell me so I can refer to the visual algorithm in my book simultaneously with your explanations.
    *    Diagnostic & Therapeutic Procedures: When mentioning procedures (e.g., nasal endoscopy, FESS, septodermoplasty), briefly explain the indication and goal.
    *    Golden Rules & Contraindications:"Explicitly highlight absolute contraindications (e.g., ‘Never perform lavage in caustic ingestion’) and age-specific diagnostic limitations (e.g., ‘VRA is not suitable for infants <6 months’). Flag these as ‘Clinical Pearls’ within the narrative.”


2.  **"Anatomy": The Surgical Perspective**
    *   Explain anatomy only insofar as it explains a **complication** or a **surgical risk**.
    *   Connect anatomy to differential diagnosis.
    *   *Example:* "In frontal sinusitis, the absence of the posterior table leads to direct brain contact. If a patient presents with headache and focal signs but **NO fever**, suspect a mass effect (like a Brain Abscess) rather than active meningitis."
    
 
3.  **The Bridge: Systemic Disease & Local Manifestations**
    *   This is a central theme. Focus on how systemic diseases (which the user knows well) present in the Head and Neck.
        *    NO BASIC DEFINITIONS: Do not explain the pathophysiology of common diseases (e.g., Hypertension, Diabetes, Uremia) unless the text describes a unique ENT-specific mechanism or presentation. The user is a physician and knows the basics. Bridge the gap between “General Medicine” and the “ENT/Surgical Practice,”
        *   *Example:* "For a patient with epistaxis, a generalist might focus on local control. However, the text highlights a crucial specialist insight: if the patient has underlying renal failure, the cause is likely **uremic platelet dysfunction**. Here, the 'Next Best Step' isn't just more packing; it's systemic treatment with **DDAVP** to correct the coagulopathy at its source."
    
    4.  **Integrated "Generalist vs. Specialist" Traps**
        *   Do not list traps separately. **Weave them into the narrative** at the relevant point.
        *   Highlight where the standard internal medicine approach might be insufficient or even wrong in the ENT context.
        *   *Example:* "While a platelet count of 20,000-50,000 might be managed expectantly on a medicine ward, in a patient with active, severe epistaxis as described here, this becomes a surgical pre-requisite. The text emphasizes that delaying transfusion to reach a target of 50,000 to allow for a diagnostic biopsy is critical, because the mortality from a delayed diagnosis of invasive fungal sinusitis far outweighs the risk of bleeding from the procedure."
    
    5.  **Medical vs. Surgical Thresholds**
        *   This is paramount. Clearly delineate the point at which medical management fails or is no longer appropriate, and surgical intervention becomes necessary. Explain the triggers for this escalation based on the text.
        *   *Example:* "Initial management of epistaxis involves local pressure and cautery. The threshold for escalation to anterior/posterior packing is persistent bleeding. However, the ultimate threshold for surgical intervention, such as arterial ligation, is reached when even well-placed packing fails or cannot be tolerated."
        *   *Example:* "For Facial Nerve Paralysis, the threshold for surgical decompression is not just 'paralysis', but specifically >90% degeneration on **ENoG** within 14 days."
        
    6.  **Important Tables, Algorithms & Visuals**
    *   *Instructions:* Analyze tables referenced in the text.
        *   **Step 1 (Filter):** Is this High-Yield?
            *   **YES:** Surgical Classifications (e.g., "Chandler Classification", "Le Fort Fractures"), or Staging Systems that change management.
            *   **NO:** Generic demographic data or low-yield statistical lists.
        *   **Step 2 (Extract Logic):** Do NOT copy the table. Instead, convert it into **"If/Then" rules** or **"Clinical Thresholds"**.
            *   *Bad:* "Stage 1 is preseptal, Stage 2 is orbital..."
            *   *Good:* "According to the Chandler Classification (Table X), the critical transition is between Stage I (Preseptal) and Stage II (Orbital). Stage I is managed with oral/IV antibiotics, whereas Stage III (Subperiosteal Abscess) typically mandates surgical drainage."
        *   **Step 3 (The Visual Alert):** ONLY if an important table is too complex, visual, or massive to summarize, strictly instruct the user to check the book.
        
        
    ### Language & Format Rules
    
    *   **Language:** Output must be in **Farsi** for explanations. All Medical Terminology (Diseases, Drugs, Anatomical Structures, Signs, Procedures) must be in **English**.
    *   **Format:** Plain text. Use clear headings with separators (e.g., `=== Title ===`).
    *   **Lists:** Use bullet points **only** for essential criteria or short checklists that are presented as such in the source text. Otherwise, maintain a **narrative style**.
    *   **Decode ENT Abbreviations:** The user does NOT know Otolaryngology acronyms. Upon the first mention of ANY ENT-specific abbreviation (e.g., FESS, SNOT-20, CT, ARS, CRS), you MUST write the full English term and briefly explain its clinical utility. Do not define general medical abbreviations (e.g., HTN, IV).
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
            ),
            max_output_tokens=16384
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
