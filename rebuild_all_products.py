# rebuild_all_products.py
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
import pymupdf as fitz
from app.agents.digital_product_agent import DigitalProductPackagingAgent

def main():
    agent = DigitalProductPackagingAgent()
    products = agent.get_all_products()
    print(f"Total products found in DB: {len(products)}")
    
    results = []
    for prod in products:
        pid = prod["id"]
        title = prod.get("title", "")
        price = prod.get("price_inr", 0)
        try:
            pdf_path = agent.ensure_product_pdf(pid, force_rebuild=True)
            doc = fitz.open(str(pdf_path))
            page_count = len(doc)
            size_kb = pdf_path.stat().st_size / 1024
            results.append((pid, title, price, page_count, f"{size_kb:.1f} KB", "SUCCESS"))
            print(f"OK: [{pid}] {title[:35]} -> {page_count} pages, {size_kb:.1f} KB")
        except Exception as e:
            results.append((pid, title, price, 0, "0 KB", f"ERROR: {e}"))
            print(f"FAIL: [{pid}] Failed: {e}")
            
    print("\n" + "="*85)
    print(f"{'Product ID':<34} | {'Price':<6} | {'Pages':<6} | {'Size':<10} | {'Status'}")
    print("="*85)
    for pid, title, price, pages, sz, st in results:
        print(f"{pid:<34} | ₹{price:<5} | {pages:<6} | {sz:<10} | {st}")
    print("="*85)

if __name__ == "__main__":
    main()
