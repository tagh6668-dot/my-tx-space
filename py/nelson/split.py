import os
from pypdf import PdfReader, PdfWriter

# --- تنظیمات ---
input_pdf_path = '/workspaces/dadsetani/nelson/book.pdf'  # نام فایل خود را چک کنید
output_folder = '/workspaces/dadsetani/nelson/split'

# *** مهم: اختلاف شماره صفحه فهرست با شماره صفحه واقعی در PDF ***
# اگر سکشن ۱ در فهرست صفحه ۱۸ است، اما در PDF Viewer صفحه ۲۵ را نشان می‌دهد
# اینجا عدد ۷ را وارد کنید (25 - 18 = 7)
# اگر شماره‌ها دقیقا یکی هستند، این را 0 بگذارید.
page_offset = 0 

# لیست استخراج شده از تصاویر شما
# فرمت: (شماره_صفحه_فهرست, نام_پوشه_خروجی)
sections_list = [
    (18,  "Section_01_Profession_of_Pediatrics"),
    (30,  "Section_02_Growth_and_Development"),
    (65,  "Section_03_Behavioral_Disorders"),
    (89,  "Section_04_Psychiatric_Disorders"),
    (110, "Section_05_Psychosocial_Issues"),
    (137, "Section_06_Nutrition"),
    (170, "Section_07_Fluids_and_Electrolytes"),
    (193, "Section_08_Acutely_Ill_Child"),
    (227, "Section_09_Genetics"),
    (252, "Section_10_Metabolic_Disorders"),
    (283, "Section_11_Fetal_and_Neonatal"),
    (345, "Section_12_Adolescent_Medicine"),
    (367, "Section_13_Immunology"),
    (394, "Section_14_Allergy"),
    (435, "Section_15_Rheumatic_Diseases"),
    (461, "Section_16_Infectious_Diseases"),
    (600, "Section_17_Digestive_System"),
    (645, "Section_18_Respiratory_System"),
    (678, "Section_19_Cardiovascular_System"),
    (714, "Section_20_Hematology"),
    (749, "Section_21_Oncology"),
    (777, "Section_22_Nephrology_and_Urology"),
    (804, "Section_23_Endocrinology"),
    (856, "Section_24_Neurology"),
    (900, "Section_25_Dermatology"),
    (927, "Section_26_Orthopedics"),
    (962, "Index_and_End")
]

def split_by_sections():
    if not os.path.exists(input_pdf_path):
        print("Error: File PDF nayaft shod!")
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    reader = PdfReader(input_pdf_path)
    total_pages = len(reader.pages)
    
    print(f"Total pages in PDF: {total_pages}")
    print("Starting split process...")

    for i in range(len(sections_list)):
        # محاسبه صفحه شروع
        toc_page_num = sections_list[i][0]
        section_name = sections_list[i][1]
        
        # تبدیل شماره صفحه کتاب به ایندکس پایتون (که از 0 شروع میشه) + اعمال آفست
        # مثال: صفحه 18 کتاب -> منهای 1 میشه 17 -> به علاوه آفست
        start_index = (toc_page_num - 1) + page_offset

        # محاسبه صفحه پایان (شروع سکشن بعدی)
        if i < len(sections_list) - 1:
            next_toc_page = sections_list[i+1][0]
            end_index = (next_toc_page - 1) + page_offset
        else:
            # برای آخرین مورد (Index)، تا آخر فایل می‌رویم
            end_index = total_pages

        # بررسی اینکه اعداد از حد مجاز خارج نشوند
        if start_index >= total_pages:
            print(f"Skipping {section_name}: Start page {start_index} is out of range.")
            continue
        
        if end_index > total_pages:
            end_index = total_pages

        # ساخت فایل جدید
        writer = PdfWriter()
        for p in range(start_index, end_index):
            writer.add_page(reader.pages[p])

        output_filename = f"{output_folder}/{section_name}.pdf"
        with open(output_filename, "wb") as f:
            writer.write(f)
        
        print(f"Created: {section_name}.pdf (Pages {start_index+1} to {end_index})")

    print("\nDone! Check 'Sections_Split' folder.")

if __name__ == "__main__":
    split_by_sections()
