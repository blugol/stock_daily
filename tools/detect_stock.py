import time
import re
import sys
import win32gui

# Pattern for potential stock names: 2 to 20 characters of Korean, English, numbers, space, &, -, .
POTENTIAL_NAME_PATTERN = re.compile(r'^[가-힣A-Za-z0-9\s\&\-\.]{2,20}$')

# Common HTS UI words to exclude immediately
EXCLUDED_WORDS = {
    "등록", "뉴스", "소리", "대상", "조건", "필드", "예상", "통", "평", "주", "연결", "매도", "매수",
    "지표분석", "비교분석", "자동삭제", "이탈삭제", "종목수", "선별종목", "관심종목", "키움종합차트",
    "조건검색실시간", "영웅문", "종목감시기", "테스트", "돋보기", "최근검색", "종목연동", "차트"
}

def sanitize_stock_name(text):
    """Cleans up win32 window text to ensure exact matches (removes null bytes, zero-width spaces)."""
    if not text:
        return ""
    # Remove null bytes
    text = text.replace("\x00", "")
    # Remove invisible unicode characters (zero-width space, BOM, etc.)
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)
    return text.strip()

def get_window_title(hwnd):
    """Retrieves the title of a window given its handle."""
    try:
        title = win32gui.GetWindowText(hwnd)
        return sanitize_stock_name(title)
    except Exception:
        return ""

def get_window_class(hwnd):
    """Retrieves the class name of a window."""
    try:
        return win32gui.GetClassName(hwnd)
    except Exception:
        return ""

def scan_all_child_windows(parent_hwnd):
    """Scans all child windows, returning a list of (hwnd, class_name, title)."""
    children = []
    
    def enum_child_callback(hwnd, lparam):
        title = get_window_title(hwnd)
        class_name = get_window_class(hwnd)
        children.append((hwnd, class_name, title))
        return True
        
    try:
        win32gui.EnumChildWindows(parent_hwnd, enum_child_callback, None)
    except Exception:
        pass
    return children

def detect_current_stock(hts_hwnd):
    """
    Scans child windows of 영웅문4 and finds the active stock.
    Returns stock_name or None.
    """
    children = scan_all_child_windows(hts_hwnd)
    
    # Scan AfxWnd110 class child windows for potential stock name
    for hwnd, c_name, title in children:
        if c_name == "AfxWnd110":
            name = title
            if name and name not in EXCLUDED_WORDS and POTENTIAL_NAME_PATTERN.match(name):
                # Basic sanity check: Korean stock names are usually 2 to 10 characters
                # and do not contain pure numbers (except some index/ETF names)
                # This ensures we get a valid stock name
                if len(name) >= 2 and len(name) <= 10:
                    return name
                    
    return None

def main():
    print("==================================================")
    print(" Kiwoom HTS Stock Detector (로컬 안전 모드)")
    print("==================================================")
    print("인터넷 통신 없이 오직 로컬 창 정보로만 종목을 감지합니다.")
    print("영웅문 HTS 창에서 종목을 자유롭게 변경해 보세요.")
    print("종료하려면 Ctrl+C를 누르세요.\n")
    
    # Find main window
    hts_hwnd = None
    def find_hts(hwnd, lparam):
        nonlocal hts_hwnd
        title = get_window_title(hwnd)
        if "영웅문4" in title:
            hts_hwnd = hwnd
            return False
        return True
        
    try:
        win32gui.EnumWindows(find_hts, None)
    except Exception:
        pass
        
    if not hts_hwnd:
        print("[오류] 실행 중인 '영웅문4' 창을 찾을 수 없습니다. HTS를 켜고 실행해 주세요.")
        input("\n종료하려면 엔터를 누르세요...")
        sys.exit(1)
        
    print(f"영웅문4 감지 완료 (HWND: {hts_hwnd})")
    print("실시간 감시 중...\n")
    
    last_detected = None
    
    try:
        while True:
            name = detect_current_stock(hts_hwnd)
            
            if name and name != last_detected:
                print(f"[종목 변경 감지] 종목명: {name:<12}")
                last_detected = name
                
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
        sys.exit(0)

if __name__ == "__main__":
    main()
