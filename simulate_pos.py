import time
import random
from datetime import datetime
from sqlalchemy import create_engine, text

# Connect directly to local PostgreSQL
engine = create_engine("postgresql+psycopg2://localhost:5432/inventro_test_db", pool_pre_ping=True)

print("⚡ Starting Real-Time Supermarket POS Simulator...")
print("🛒 Customers are entering checkout lanes. Press Ctrl+C to stop.\n")

lanes = ["Lane 1 (Express)", "Lane 2 (Self-Checkout)", "Lane 3 (Standard)", "Lane 4 (Scan & Go)"]

try:
    customer_id = 1001
    while True:
        with engine.connect() as conn:
            # Fetch products with available stock
            available_prods = conn.execute(text("SELECT sku, name, category, stock FROM products_master WHERE stock > 0")).fetchall()
            
            if not available_prods:
                print("⚠️ Supermarket is completely out of stock across all lines!")
                time.sleep(5)
                continue
            
            # Simulate a shopping basket (1 to 3 items per customer)
            basket_size = random.randint(1, min(3, len(available_prods)))
            selected_items = random.sample(available_prods, basket_size)
            lane = random.choice(lanes)
            
            print(f"🛍️  [Customer #{customer_id}] Checking out at {lane} | {datetime.now().strftime('%H:%M:%S')}")
            
            for prod in selected_items:
                sku, name, cat, current_stock = prod[0], prod[1], prod[2], prod[3]
                qty_bought = random.randint(1, min(2, max(1, current_stock)))
                
                # 1. Decrement Stock
                conn.execute(
                    text("UPDATE products_master SET stock = GREATEST(0, stock - :qty) WHERE sku = :sku"),
                    {"qty": qty_bought, "sku": sku}
                )
                
                # 2. Insert into POS Sales Ledger
                conn.execute(
                    text("INSERT INTO sales_ledger (transaction_date, sku, product_name, category, quantity_sold, is_weekend) VALUES (:dt, :sku, :name, :cat, :qty, 0)"),
                    {"dt": str(datetime.today().date()), "sku": sku, "name": name, "cat": cat, "qty": qty_bought}
                )
                
                # 3. Log Audit Movement
                conn.execute(
                    text("INSERT INTO stock_movements (movement_timestamp, sku, movement_type, quantity, notes) VALUES (:ts, :sku, 'POS_SCAN', :qty, :note)"),
                    {"ts": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), "sku": sku, "qty": qty_bought, "note": f"Scanned at {lane}"}
                )
                
                print(f"   ↳ Billed {qty_bought}x {name} ({sku}) | Remaining Stock: {max(0, current_stock - qty_bought)}")
            
            conn.commit()
            print("-" * 65)
            customer_id += 1
            
        # Delay between customer checkouts (1.5 to 3.0 seconds)
        time.sleep(random.uniform(1.5, 3.0))

except KeyboardInterrupt:
    print("\n🛑 POS Simulation halted.")
