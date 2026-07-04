import os
import csv
import json
import re
from datetime import datetime, date as dt

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(DIRECTORY, "거래내역(과거데이터).csv")
DATA_DIR = os.path.join(DIRECTORY, "data")

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

def load_or_create_json(stock_name):
    safe_name = "".join(x for x in stock_name if x.isalnum() or x in " -_").strip()
    filepath = os.path.join(DATA_DIR, f"{safe_name}.json")
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f), filepath
        except Exception:
            pass
            
    # Return copy of template
    return json.loads(json.dumps(DEFAULT_TEMPLATE)), filepath

def main():
    print("==================================================")
    # Target title translates to Korean: "HTS 거래내역 CSV 데이터 정리 및 이관기"
    print(" HTS 거래내역 CSV 데이터 정리 및 이관기 V2.0")
    print("==================================================")
    
    if not os.path.exists(CSV_FILE):
        print(f"[오류] CSV 파일 '{CSV_FILE}'을 찾을 수 없습니다.")
        return

    # 1. Read and parse CSV into trade records
    raw_rows = []
    with open(CSV_FILE, "r", encoding="cp949", errors="replace") as f:
        reader = csv.reader(f)
        for r in reader:
            raw_rows.append(r)
            
    trades_by_stock = {}
    
    i = 2
    while i < len(raw_rows) - 1:
        r1 = raw_rows[i]
        r2 = raw_rows[i+1]
        
        # Validate date and stock name
        if r1[0].startswith("202") and r1[1].strip():
            date_str = r1[0].strip().replace("/", "-")
            stock_name = r1[1].strip()
            qty_val = int(r1[2].strip()) if r1[2].strip() else 0
            amount_val = int(r1[3].strip().replace(",", "")) if r1[3].strip() else 0
            
            trade_type = r2[1].strip()
            price_val = float(r2[2].strip().replace(",", "")) if r2[2].strip() else 0.0
            time_str = r2[10].strip()
            
            is_buy = "매수" in trade_type
            is_sell = "매도" in trade_type
            
            if is_buy or is_sell:
                if stock_name not in trades_by_stock:
                    trades_by_stock[stock_name] = []
                trades_by_stock[stock_name].append({
                    "date": date_str,
                    "time": time_str,
                    "qty": qty_val,
                    "amount": amount_val,
                    "price": price_val,
                    "is_buy": is_buy,
                    "is_sell": is_sell,
                    "raw_type": trade_type
                })
        i += 2
        
    print(f"총 {len(trades_by_stock)}개 종목의 거래 내역을 찾았습니다.")
    
    # 2. Process each stock
    for stock_name, records in trades_by_stock.items():
        # Sort chronologically by date and time
        records.sort(key=lambda x: f"{x['date']} {x['time']}")
        
        # Load or create JSON
        data, filepath = load_or_create_json(stock_name)
        
        buys = [r for r in records if r["is_buy"]]
        sells = [r for r in records if r["is_sell"]]
        
        print(f"\n[{stock_name}] 매수: {len(buys)}건, 매도: {len(sells)}건")
        
        # A. Populate Martin Tiers from BUYs
        if buys:
            data["martin_calc"]["base_price"] = int(buys[0]["price"])
            data["martin_calc"]["base_qty"] = buys[0]["qty"]
            
            for index, buy in enumerate(buys[:4]):
                tier_idx = index
                data["martin_calc"]["tiers"][tier_idx]["price"] = int(buy["price"])
                data["martin_calc"]["tiers"][tier_idx]["qty"] = buy["qty"]
                data["martin_calc"]["tiers"][tier_idx]["checked"] = True
                data["martin_calc"]["tiers"][tier_idx]["date"] = buy["date"]
                
                # Add buy log to timeline
                log_time = f"{buy['date']} {buy['time']}"
                log_text = f"[실제 체결] {tier_idx + 1}차 매수 {buy['qty']}주 완료 (체결단가: {int(buy['price']):,}원)"
                
                # Check for duplicates in timeline logs
                exists = any(l["text"] == log_text for l in data["timeline_logs"])
                if not exists:
                    data["timeline_logs"].append({
                        "time": log_time,
                        "text": log_text
                    })
                    
        # B. Calculate Settlement if SELLs exist
        if sells:
            total_sell_qty = sum(s["qty"] for s in sells)
            total_sell_amount = sum(s["price"] * s["qty"] for s in sells)
            avg_sell_price = total_sell_amount / total_sell_qty if total_sell_qty > 0 else 0.0
            
            # Sum up buys
            total_buy_qty = sum(b["qty"] for b in buys) if buys else total_sell_qty # Fallback if buys not in CSV
            total_buy_amount = sum(b["price"] * b["qty"] for b in buys) if buys else (total_sell_amount * 0.95)
            avg_buy_price = total_buy_amount / total_buy_qty if total_buy_qty > 0 else 0.0
            
            if avg_buy_price > 0:
                yield_rate = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100
                sign = "+" if yield_rate >= 0 else ""
                yield_rate_str = f"{sign}{yield_rate:.2f}%"
                
                # Calculate holding period
                start_date_str = buys[0]["date"] if buys else sells[0]["date"]
                end_date_str = sells[-1]["date"]
                
                try:
                    start_parts = [int(x) for x in start_date_str.split("-")]
                    end_parts = [int(x) for x in end_date_str.split("-")]
                    d_start = dt(start_parts[0], start_parts[1], start_parts[2])
                    d_end = dt(end_parts[0], end_parts[1], end_parts[2])
                    diff_days = (d_end - d_start).days + 1
                    holding_period_str = f"{diff_days}D"
                except Exception:
                    holding_period_str = "1D"
                    
                # Format Stamp
                # mmdd formatted dates
                s_parts = start_date_str.split("-")
                e_parts = end_date_str.split("-")
                mmdd_start = f"{int(s_parts[1]):02d}{int(s_parts[2]):02d}"
                mmdd_end = f"{int(e_parts[1]):02d}{int(e_parts[2]):02d}"
                
                stamp = f"{mmdd_start}({int(avg_buy_price)}) - {mmdd_end}({int(avg_sell_price)}) / ({holding_period_str}) / ({yield_rate_str})"
                
                # Map to settlement object
                data["settlement"]["is_settled"] = True
                data["settlement"]["yield_rate"] = yield_rate_str
                data["settlement"]["final_price"] = int(avg_sell_price)
                data["settlement"]["holding_period"] = holding_period_str
                data["settlement"]["stamp"] = stamp
                
                # Add Sell and Settlement Logs to timeline
                for sell in sells:
                    log_time = f"{sell['date']} {sell['time']}"
                    log_text = f"[실제 체결] 매도 {sell['qty']}주 완료 (체결단가: {int(sell['price']):,}원)"
                    exists = any(l["text"] == log_text for l in data["timeline_logs"])
                    if not exists:
                        data["timeline_logs"].append({
                            "time": log_time,
                            "text": log_text
                        })
                        
                settle_time = f"{end_date_str} {sells[-1]['time']}"
                settle_text = f"[최종 청산 완료] 결산기록: {stamp}"
                exists = any(l["text"] == settle_text for l in data["timeline_logs"])
                if not exists:
                    data["timeline_logs"].append({
                        "time": settle_time,
                        "text": settle_text
                    })
                    
        # Sort all timeline logs descending
        data["timeline_logs"].sort(key=lambda x: x["time"], reverse=True)
        
        # Save JSON back
        with open(filepath, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=4)
            
        print(f" -> 성공적으로 데이터 이관 완료: {os.path.basename(filepath)}")
        
    print("\n==================================================")
    print(" CSV 거래내역 이관이 모두 완료되었습니다!")
    print("==================================================")

if __name__ == "__main__":
    main()
