import subprocess
import os

# نام فایل پی‌دی‌اف شما
input_pdf = "nelson_full.pdf"

# لیست شماره صفحات شروع هر فصل (طبق داده‌های شما)
start_pages = [
    18, 21, 23, 26, 30, 33, 34, 37, 41, 50, 65, 67, 70, 73, 82, 89, 92, 96, 102, 104, 
    110, 113, 120, 124, 128, 131, 137, 143, 147, 153, 158, 170, 172, 177, 179, 183, 187, 
    193, 198, 201, 206, 207, 211, 213, 216, 222, 227, 236, 240, 244, 252, 260, 263, 268, 
    271, 273, 278, 283, 303, 309, 312, 320, 328, 330, 334, 337, 345, 352, 354, 361, 363, 
    367, 373, 381, 386, 389, 394, 397, 408, 411, 415, 421, 422, 425, 429, 435, 438, 441, 
    445, 449, 453, 455, 461, 464, 469, 471, 476, 483, 487, 491, 495, 498, 500, 503, 505, 
    509, 511, 513, 515, 518, 524, 527, 532, 535, 538, 541, 548, 551, 555, 559, 564, 567, 
    578, 585, 591, 600, 612, 614, 622, 629, 638, 641, 645, 652, 656, 660, 668, 672, 678, 
    684, 686, 688, 691, 696, 702, 705, 707, 709, 714, 718, 733, 743, 749, 754, 759, 762, 
    765, 767, 770, 772, 777, 781, 783, 786, 788, 792, 794, 796, 799, 804, 808, 816, 822, 
    829, 837, 844, 846, 850, 857, 862, 864, 870, 878, 881, 889, 892, 895, 900, 903, 905, 
    909, 911, 914, 917, 919, 922, 927, 930, 933, 938, 943, 947, 954, 958
]

if not os.path.exists(input_pdf):
    print(f"Error: File '{input_pdf}' not found in current directory.")
    exit()

print(f"Starting split process for {len(start_pages)} chapters...")

for i in range(len(start_pages)):
    chapter_num = i + 1
    start_page = start_pages[i]
    
    # Calculate end page based on the start of the next chapter
    if i < len(start_pages) - 1:
        end_page = start_pages[i+1] - 1
        page_range = f"{start_page}-{end_page}"
    else:
        # For the last chapter, go to the end of the file
        page_range = f"{start_page}-end"
    
    # Format output filename (e.g., Chapter_001.pdf)
    output_filename = f"Chapter_{chapter_num:03d}.pdf"
    
    # Run pdftk command
    cmd = ["pdftk", input_pdf, "cat", page_range, "output", output_filename]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Created {output_filename} (Pages {page_range})")
    except subprocess.CalledProcessError:
        print(f"Error creating {output_filename}")

print("Done!")
