import re
import os
import json
import sys

# Set stdout to UTF-8 to prevent encoding crashes on Windows console output
sys.stdout.reconfigure(encoding='utf-8')

# Paths
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
SOURCE_FILE = os.path.join(DIRECTORY, "통합메모(과거데이터).txt")
DATA_DIR = os.path.join(DIRECTORY, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Advanced Date Regex with lookbehinds/lookaheads to prevent boundary issues with Korean characters and ignore parenthesized dates
DATE_PATTERN = re.compile(
    r'('
    r'(?<!\()(?<!\d)\d{4}[./-]\d{2}[./-]\d{2}(?!\d)|' # YYYY-MM-DD, YYYY/MM/DD
    r'(?<!\()(?<!\d)\d{2}\d{2}:|'                    # MMDD:
    r'(?<!\()(?<!\d)202\d{5}(?!\d)|'                  # 20260522 (YYYYMMDD)
    r'(?<!\()(?<!\d)0[1-9]\d{2}(?!\d)|'               # 0331 (MMDD starting with 0)
    r'(?<!\()(?<!\d)1[0-2]\d{2}(?!\d)'                # 1024 (MMDD starting with 1)
    r')'
)

TAG_PATTERN = re.compile(r'[가-힣A-Za-z]+?\d+%?|[가-힣A-Za-z]+')

def parse_financial_tags(finance_str):
    """Parses finance text into Notion-style tag badges using verified regex."""
    if not finance_str:
        return []
    cleaned = finance_str.replace('(', ' ').replace(')', ' ').replace(',', ' ')
    raw_tags = TAG_PATTERN.findall(cleaned)
    return [t.strip() for t in raw_tags if t.strip()]

def parse_buy_prices(buy_str):
    """Parses buy prices and optional execution dates (e.g. 1767(0615), 1530(0629))."""
    buy_prices = []
    if not buy_str:
        return buy_prices
    
    # Split by comma
    items = re.split(r',\s*', buy_str)
    for item in items:
        item = item.strip()
        m = re.match(r'(\d+)(?:\((\d{4})\))?', item)
        if m:
            price = int(m.group(1))
            date_part = m.group(2)
            formatted_date = ""
            if date_part:
                formatted_date = f"2026-{date_part[:2]}-{date_part[2:]}"
            buy_prices.append((price, formatted_date))
    return buy_prices

def parse_timeline(timeline_text):
    """Slices timeline text into individual logs based on date patterns and sorts descending."""
    matches = list(DATE_PATTERN.finditer(timeline_text))
    logs = []
    if not matches:
        return logs
        
    for i, match in enumerate(matches):
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(timeline_text)
        
        content = timeline_text[start_idx:end_idx].strip()
        if content.startswith(":"):
            content = content[1:].strip()
            
        raw_date = match.group(0)
        formatted_date = ""
        
        # Clean colon if present in date match
        clean_date = raw_date.replace(":", "")
        
        if ":" in raw_date:
            # MMDD: format
            mm = clean_date[:2]
            dd = clean_date[2:4]
            formatted_date = f"2026-{mm}-{dd} 00:00:00"
        elif len(clean_date) == 8:
            # YYYYMMDD format
            yyyy = clean_date[:4]
            mm = clean_date[4:6]
            dd = clean_date[6:8]
            formatted_date = f"{yyyy}-{mm}-{dd} 00:00:00"
        elif len(clean_date) == 4:
            # MMDD format (e.g. 0331)
            mm = clean_date[:2]
            dd = clean_date[2:4]
            formatted_date = f"2026-{mm}-{dd} 00:00:00"
        else:
            # YYYY/MM/DD or YYYY-MM-DD format
            normalized = re.sub(r'[./]', '-', clean_date)
            formatted_date = f"{normalized} 00:00:00"
            
        if content:
            # Clean newlines inside content to look neat
            content_clean = re.sub(r'\s+', ' ', content).strip()
            logs.append({
                "time": formatted_date,
                "text": content_clean
            })
            
    # Sort logs by date descending (latest first)
    logs.sort(key=lambda x: x["time"], reverse=True)
    return logs

def process_stock_block(code, header_line, comment_lines):
    # Strip stock code match to get remaining text
    code_match = re.match(r'^\[\d{6}\]', header_line)
    remaining = header_line[code_match.end():]
    
    # Extract Stock Name: The first word of the remaining header string
    parts = remaining.strip().split(maxsplit=1)
    stock_name = parts[0].strip()
    header_details = parts[1].strip() if len(parts) > 1 else ""
    
    # Merge comment lines
    comments_text = "".join(comment_lines)
    full_text = header_details + "\n" + comments_text
    
    # Find the index of the first date pattern to separate headers and timeline logs
    first_date_match = DATE_PATTERN.search(full_text)
    
    if first_date_match:
        first_date_idx = first_date_match.start()
        header_details_parsed = full_text[:first_date_idx]
        timeline_text = full_text[first_date_idx:]
    else:
        header_details_parsed = full_text
        timeline_text = ""
        
    # Extract fields from header_details
    buy_str = ""
    target_str = ""
    stop_str = ""
    finance_str = ""
    yield_str = ""
    is_settled = False
    
    m_buy = re.search(r'매수\s*:\s*(.*?)(?=\s*(?:목표|손절|재무|\[실현|\[최종|\Z))', header_details_parsed)
    if m_buy:
        buy_str = m_buy.group(1).strip()
        
    m_target = re.search(r'목표\s*:\s*(.*?)(?=\s*(?:매수|손절|재무|\[실현|\[최종|\Z))', header_details_parsed)
    if m_target:
        target_str = m_target.group(1).strip()
        
    m_stop = re.search(r'손절\s*:\s*(.*?)(?=\s*(?:매수|목표|재무|\[실현|\[최종|\Z))', header_details_parsed)
    if m_stop:
        stop_str = m_stop.group(1).strip()
        
    m_finance = re.search(r'재무\s*:\s*(.*?)(?=\s*(?:매수|목표|손절|\[실현|\[최종|\Z))', header_details_parsed)
    if m_finance:
        finance_str = m_finance.group(1).strip()
        
    settle_date = ""
    m_settle1 = re.search(r'\[(?:실현|수익실현|최종)\s*:\s*(.*?)\]', header_details_parsed)
    if m_settle1:
        yield_str = m_settle1.group(1).strip()
        is_settled = True
        
    m_settle2 = re.search(r'(?:수익실현|실현|최종결산|최종|결산)\s*(?:\((\d{4})\))?\s*:\s*([+-]?\d+(?:\.\d+)?%?)', header_details_parsed)
    if m_settle2:
        if m_settle2.group(1):
            settle_date = f"2026-{m_settle2.group(1)[:2]}-{m_settle2.group(1)[2:]}"
        yield_str = m_settle2.group(2).strip()
        is_settled = True
        
    # Parse Sub-elements
    dynamic_tags = parse_financial_tags(finance_str)
    buy_prices = parse_buy_prices(buy_str)
    target_price = int(target_str) if target_str.isdigit() else 0
    stop_price = int(stop_str) if stop_str.isdigit() else 0
    
    # Parse timeline logs
    timeline_logs = parse_timeline(timeline_text)
    
    # Map Martin tiers
    tiers = [
        {"tier": 1, "ratio": 1, "price": 0, "qty": 0, "checked": False, "date": ""},
        {"tier": 2, "ratio": 1, "price": 0, "qty": 0, "checked": False, "date": ""},
        {"tier": 3, "ratio": 2, "price": 0, "qty": 0, "checked": False, "date": ""},
        {"tier": 4, "ratio": 4, "price": 0, "qty": 0, "checked": False, "date": ""}
    ]
    
    base_qty = 1
    base_price = buy_prices[0][0] if buy_prices else 0
    
    for i, (price, date) in enumerate(buy_prices[:4]):
        tiers[i]["price"] = price
        tiers[i]["qty"] = base_qty * tiers[i]["ratio"]
        tiers[i]["checked"] = True
        
        # Fallback date if not present in parenthesis
        if not date:
            if timeline_logs:
                oldest_date = timeline_logs[-1]["time"].split(" ")[0]
                tiers[i]["date"] = oldest_date
            else:
                tiers[i]["date"] = "2026-07-04"
        else:
            tiers[i]["date"] = date
            
    # Set default quantities for unchecked tiers
    for i in range(len(buy_prices), 4):
        tiers[i]["qty"] = base_qty * tiers[i]["ratio"]
        
    # Settlement Mapping
    settlement = {
        "final_price": 0,
        "is_settled": is_settled,
        "holding_period": "",
        "yield_rate": yield_str,
        "stamp": ""
    }
    
    if is_settled and buy_prices:
        try:
            start_date_str = tiers[0]["date"]
            end_date_str = settle_date if settle_date else (timeline_logs[0]["time"].split(" ")[0] if timeline_logs else start_date_str)
            
            # Date calculations
            start_parts = [int(x) for x in start_date_str.split("-")]
            end_parts = [int(x) for x in end_date_str.split("-")]
            
            from datetime import date as dt
            d_start = dt(start_parts[0], start_parts[1], start_parts[2])
            d_end = dt(end_parts[0], end_parts[1], end_parts[2])
            diff_days = (d_end - d_start).days + 1
            
            holding_period = f"{diff_days}D"
            settlement["holding_period"] = holding_period
            
            mmdd_start = f"{start_parts[1]:02d}{start_parts[2]:02d}"
            mmdd_end = f"{end_parts[1]:02d}{end_parts[2]:02d}"
            avg_price = base_price
            
            stamp = f"{mmdd_start}({avg_price}) - {mmdd_end}(청산) / ({holding_period}) / ({yield_str})"
            settlement["stamp"] = stamp
        except Exception:
            pass

    # Assemble JSON object
    data = {
        "trend_status": "",
        "dynamic_tags": dynamic_tags,
        "martin_calc": {
            "base_qty": base_qty,
            "base_price": base_price,
            "tiers": tiers
        },
        "target_price": target_price,
        "stop_price": stop_price,
        "settlement": settlement,
        "timeline_logs": timeline_logs
    }
    
    return stock_name, data

def main():
    print("==================================================")
    print(" HTS 통합메모 데이터 마이그레이션 실행기 V2.0")
    print("==================================================")
    
    if not os.path.exists(SOURCE_FILE):
        print(f"[오류] 소스 파일 '{SOURCE_FILE}'을 찾을 수 없습니다.")
        sys.exit(1)
        
    stocks_raw = []
    current_stock = None
    
    # Read CP949 file line by line
    with open(SOURCE_FILE, "r", encoding="cp949", errors="replace") as f:
        for line in f:
            m = re.match(r'^\[(\d{6})\]', line)
            if m:
                if current_stock:
                    stocks_raw.append(current_stock)
                current_stock = {
                    "code": m.group(1),
                    "header_line": line,
                    "comment_lines": []
                }
            else:
                if current_stock:
                    current_stock["comment_lines"].append(line)
        if current_stock:
            stocks_raw.append(current_stock)
            
    print(f"총 {len(stocks_raw)}개의 원본 종목 데이터를 수집했습니다.")
    
    processed_count = 0
    for s in stocks_raw:
        try:
            name, data = process_stock_block(s["code"], s["header_line"], s["comment_lines"])
            if not name:
                continue
                
            # Create valid file name
            safe_name = "".join(x for x in name if x.isalnum() or x in " -_").strip()
            if not safe_name:
                continue
                
            filepath = os.path.join(DATA_DIR, f"{safe_name}.json")
            with open(filepath, "w", encoding="utf-8") as out:
                json.dump(data, out, ensure_ascii=False, indent=4)
                
            processed_count += 1
        except Exception as e:
            print(f"[경고] {s.get('header_line', '').strip()[:30]}... 파싱 중 오류 발생: {e}")
            
    print("--------------------------------------------------")
    print(f"마이그레이션 완료! 총 {processed_count}개의 종목 일지가 데이터베이스화되었습니다.")
    print(f"결과물 저장 경로: {DATA_DIR}")
    print("==================================================")

if __name__ == "__main__":
    main()
