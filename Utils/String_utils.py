import unicodedata

def remove_vietnamese_accents(input_str: str) -> str:
    if not input_str: 
        return ""
    
    # 1. BẮT BUỘC: Thay thế Đ/đ trước khi ép kiểu ASCII
    input_str = input_str.replace('đ', 'd').replace('Đ', 'D')
    
    # 2. Phân tách các dấu (sắc, huyền, hỏi, ngã, nặng, mũ, râu...)
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    
    # 3. Ép kiểu ASCII để vứt bỏ toàn bộ các dấu vừa được phân tách
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    
    # 4. Trả về chữ thường
    return only_ascii.lower()