import http.server
import socketserver
import threading
import time
import json
import os
import re
import urllib.parse
import urllib.request
import sys
import win32gui
import ssl
import traceback

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIRECTORY, "data")

# Create data directory if not exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

BACKUP_DIR = os.path.join(DIRECTORY, "backup")
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def save_backup(stock_name, filepath):
    if os.path.exists(filepath):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(x for x in stock_name if x.isalnum() or x in " -_").strip()
            backup_filename = f"{timestamp}_{safe_name}.json"
            backup_filepath = os.path.join(BACKUP_DIR, backup_filename)
            import shutil
            shutil.copy2(filepath, backup_filepath)
        except Exception as e:
            print(f"[백업 실패] {e}")

# Global state
active_stock = None
active_stock_lock = threading.Lock()

# HTS scanner config
POTENTIAL_NAME_PATTERN = re.compile(r'^[가-힣A-Za-z0-9\s\&\-\.]{2,20}$')
EXCLUDED_WORDS = {
    "등록", "뉴스", "소리", "대상", "조건", "필드", "예상", "통", "평", "주", "연결", "매도", "매수",
    "지표분석", "비교분석", "자동삭제", "이탈삭제", "종목수", "선별종목", "관심종목", "키움종합차트",
    "조건검색실시간", "영웅문", "종목감시기", "테스트", "돋보기", "최근검색", "종목연동", "차트",
    "비밀번호", "계좌번호", "계좌연동", "메모보기", "수익률추이", "매매수익", "일별잔고", "조회",
    "손대원"
}
ALLOWED_WINDOW_KEYWORDS = ["차트", "일지", "주가", "분석", "종합"]
EXCLUDE_WINDOW_KEYWORDS = ["계좌", "잔고", "예수금", "주문", "체결", "신용"]

def sanitize_stock_name(text):
    if not text:
        return ""
    text = text.replace("\x00", "")
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', text)
    return text.strip()

def hts_monitor_thread():
    global active_stock
    print("[HTS 모니터] HTS 감지 스레드가 가동되었습니다.")
    
    target_title_part1 = '\uc601\uc6c5\ubb384'
    target_title_part2 = '\uc601\uc6c5\ubb38'
    
    while True:
        try:
            # Find main window of 영웅문4 / 영웅문
            hts_hwnd = None
            def find_hts(hwnd, lparam):
                nonlocal hts_hwnd
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if target_title_part1 in title or target_title_part2 in title:
                        hts_hwnd = hwnd
                        return False
                except Exception:
                    pass
                return True
            
            try:
                win32gui.EnumWindows(find_hts, None)
            except Exception:
                pass
                
            detected = None
            if hts_hwnd:
                # 1. Enumerate MDI child windows to find target containers (e.g. charts, quote screens)
                target_containers = []
                def enum_containers(hwnd, lparam):
                    try:
                        title = win32gui.GetWindowText(hwnd)
                        if title and any(kw in title for kw in ALLOWED_WINDOW_KEYWORDS):
                            # Exclude account/balance manager screens
                            if not any(ex_kw in title for ex_kw in EXCLUDE_WINDOW_KEYWORDS):
                                target_containers.append(hwnd)
                    except Exception:
                        pass
                    return True
                
                try:
                    win32gui.EnumChildWindows(hts_hwnd, enum_containers, None)
                except Exception:
                    pass
                
                # 2. Scan child controls of targeted containers for valid stock names
                for container_hwnd in target_containers:
                    container_children = []
                    def enum_container_children(hwnd, lparam):
                        try:
                            title = win32gui.GetWindowText(hwnd)
                            class_name = win32gui.GetClassName(hwnd)
                            if class_name == "AfxWnd110" and title:
                                container_children.append(title)
                        except Exception:
                            pass
                        return True
                    
                    try:
                        win32gui.EnumChildWindows(container_hwnd, enum_container_children, None)
                    except Exception:
                        pass
                        
                    for title in container_children:
                        name = sanitize_stock_name(title)
                        if name and name not in EXCLUDED_WORDS and POTENTIAL_NAME_PATTERN.match(name):
                            if 2 <= len(name) <= 10:
                                detected = name
                                break
                    if detected:
                        break
            
            with active_stock_lock:
                active_stock = detected
                
        except Exception as e:
            print(f"[HTS 모니터 에러] {e}")
            
        time.sleep(1.0)

# Default memo template v2.0
DEFAULT_TEMPLATE = {
    "trend_status": "",
    "dynamic_tags": [],
    "martin_calc": {
        "base_qty": 1,
        "base_price": 0,
        "tiers": [
            {"tier": 1, "ratio": 1, "price": 0, "qty": 0, "checked": False, "date": ""},
            {"tier": 2, "ratio": 1, "price": 0, "qty": 0, "checked": False, "date": ""},
            {"tier": 3, "ratio": 2, "price": 0, "qty": 0, "checked": False, "date": ""},
            {"tier": 4, "ratio": 4, "price": 0, "qty": 0, "checked": False, "date": ""}
        ]
    },
    "target_price": 0,
    "stop_price": 0,
    "settlement": {
        "final_price": 0,
        "is_settled": False,
        "holding_period": "",
        "yield_rate": "",
        "stamp": ""
    },
    "timeline_logs": []
}

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def translate_path(self, path):
        # Override to serve files from correct directory
        path = super().translate_path(path)
        rel = os.path.relpath(path, os.getcwd())
        return os.path.join(DIRECTORY, rel)

    def do_GET(self):
        url_parsed = urllib.parse.urlparse(self.path)
        
        # API: /api/status
        if url_parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            with active_stock_lock:
                response = {"active_stock": active_stock}
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            return
            
        # API: /api/debug_window
        elif url_parsed.path == "/api/debug_window":
            hts_hwnd = None
            target_title_part1 = '\uc601\uc6c5\ubb384'
            target_title_part2 = '\uc601\uc6c5\ubb38'
            
            def find_hts(hwnd, lparam):
                nonlocal hts_hwnd
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if target_title_part1 in title or target_title_part2 in title:
                        hts_hwnd = hwnd
                        return False
                except Exception:
                    pass
                return True
                
            try:
                win32gui.EnumWindows(find_hts, None)
            except Exception:
                pass
                
            if not hts_hwnd:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "HTS window not found. Make sure HTS is running on screen."}, ensure_ascii=False).encode('utf-8'))
                return
                
            children = []
            def enum_child_callback(hwnd, lparam):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    children.append({
                        "hwnd": hwnd,
                        "class": class_name,
                        "text": sanitize_stock_name(title)
                    })
                except Exception:
                    pass
                return True
                
            try:
                win32gui.EnumChildWindows(hts_hwnd, enum_child_callback, None)
            except Exception:
                pass
                
            # Write to local file for reference
            debug_filepath = os.path.join(DIRECTORY, "window_debug.txt")
            try:
                with open(debug_filepath, "w", encoding="utf-8") as f:
                    f.write(f"HTS Parent HWND: {hts_hwnd}\n")
                    f.write(f"Total children: {len(children)}\n\n")
                    for c in children:
                        if c["text"]:
                            f.write(f"HWND: {c['hwnd']:<10} | CLASS: {c['class']:<20} | TEXT: {c['text']}\n")
            except Exception:
                pass
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"hts_hwnd": hts_hwnd, "children_count": len(children), "children": children}, ensure_ascii=False).encode('utf-8'))
            return

        # API: /api/list
        elif url_parsed.path == "/api/list":
            stocks = []
            if os.path.exists(DATA_DIR):
                for filename in os.listdir(DATA_DIR):
                    if filename.endswith(".json"):
                        stock_name = filename[:-5]
                        filepath = os.path.join(DATA_DIR, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            settlement = data.get("settlement", {})
                            stocks.append({
                                "name": stock_name,
                                "is_settled": settlement.get("is_settled", False),
                                "yield_rate": settlement.get("yield_rate", ""),
                                "dynamic_tags": data.get("dynamic_tags", [])[:3]
                            })
                        except Exception:
                            stocks.append({
                                "name": stock_name,
                                "is_settled": False,
                                "yield_rate": "",
                                "dynamic_tags": []
                            })
            stocks.sort(key=lambda x: x["name"])
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"stocks": stocks}, ensure_ascii=False).encode('utf-8'))
            return

        # API: /api/memo
        elif url_parsed.path == "/api/memo":
            params = urllib.parse.parse_qs(url_parsed.query)
            stock_name = params.get("stock", [None])[0]
            
            if not stock_name:
                self.send_error(400, "Missing stock name")
                return
                
            # Sanitize filename
            safe_name = "".join(x for x in stock_name if x.isalnum() or x in " -_").strip()
            filepath = os.path.join(DATA_DIR, f"{safe_name}.json")
            
            data = DEFAULT_TEMPLATE.copy()
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"Error reading memo file: {e}")
                    
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            return

        # Serve static files normally
        super().do_GET()

    def do_POST(self):
        url_parsed = urllib.parse.urlparse(self.path)
        
        # API: /api/delete
        if url_parsed.path == "/api/delete":
            params = urllib.parse.parse_qs(url_parsed.query)
            stock_name = params.get("stock", [None])[0]
            
            if not stock_name:
                self.send_error(400, "Missing stock name")
                return
                
            try:
                # Sanitize filename
                safe_name = "".join(x for x in stock_name if x.isalnum() or x in " -_").strip()
                filepath = os.path.join(DATA_DIR, f"{safe_name}.json")
                
                if os.path.exists(filepath):
                    save_backup(stock_name, filepath)
                    os.remove(filepath)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "message": f"{stock_name} deleted"}, ensure_ascii=False).encode('utf-8'))
                else:
                    self.send_error(404, "Stock file not found")
            except Exception as e:
                self.send_error(500, f"Error deleting stock file: {e}")
            return
            
        # API: /api/memo
        elif url_parsed.path == "/api/memo":
            params = urllib.parse.parse_qs(url_parsed.query)
            stock_name = params.get("stock", [None])[0]
            
            if not stock_name:
                self.send_error(400, "Missing stock name")
                return
                
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                memo_data = json.loads(post_data.decode('utf-8'))
                
                # Sanitize filename
                safe_name = "".join(x for x in stock_name if x.isalnum() or x in " -_").strip()
                filepath = os.path.join(DATA_DIR, f"{safe_name}.json")
                
                # Backup old version before overwrite
                save_backup(stock_name, filepath)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(memo_data, f, ensure_ascii=False, indent=4)
                    
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Error saving data: {e}")
            return
            
        self.send_error(404, "Not Found")

def main():
    # Start HTS monitoring thread
    t = threading.Thread(target=hts_monitor_thread, daemon=True)
    t.start()
    
    # Configure and start server
    handler = CustomHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"로컬 웹서버가 가동되었습니다: http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버를 종료합니다.")
            sys.exit(0)

if __name__ == "__main__":
    main()
