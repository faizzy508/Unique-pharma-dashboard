#!/usr/bin/env python3
"""
generate_dummy_data.py
Creates 3 years of realistic dummy data for the Pharma BI dashboard.
Run this once to generate all data folders and files.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# ------------------------------
# CONFIGURATION
# ------------------------------
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Output folders
ITEM_MASTER_DIR = os.path.join(BASE_DIR, "ITEM MASTER")
LOCATION_MASTER_DIR = os.path.join(BASE_DIR, "Location & Branch Master")
SUPPLIER_MASTER_DIR = os.path.join(BASE_DIR, "Supplier Master")
SALES_DIR = os.path.join(BASE_DIR, "Sales Data")
RETURNS_DIR = os.path.join(BASE_DIR, "Sales Return Data")
STOCK_DIR = os.path.join(BASE_DIR, "Stock")
LOCAL_PURCHASE_DIR = os.path.join(BASE_DIR, "Local Purchase Data")
IMPORT_PURCHASE_DIR = os.path.join(BASE_DIR, "Purchase Data")
PRF_PO_DIR = os.path.join(BASE_DIR, "P.O.PRF,PI ETC")

for d in [ITEM_MASTER_DIR, LOCATION_MASTER_DIR, SUPPLIER_MASTER_DIR,
          SALES_DIR, RETURNS_DIR, STOCK_DIR,
          LOCAL_PURCHASE_DIR, IMPORT_PURCHASE_DIR, PRF_PO_DIR]:
    os.makedirs(d, exist_ok=True)

# ------------------------------
# 1. MASTER DATA
# ------------------------------
branches = [
    {"Branch": "Kinshasa", "Location": "Kinshasa"},
    {"Branch": "Goma", "Location": "Goma"},
    {"Branch": "Lubumbashi", "Location": "Lubumbashi"},
    {"Branch": "Boma Shop", "Location": "Kinshasa"},
    {"Branch": "Matadi Shop", "Location": "Kinshasa"},
    {"Branch": "Pascal Shop", "Location": "Kinshasa"},
    {"Branch": "Kimpese Shop", "Location": "Kinshasa"},
    {"Branch": "Unique Commercial", "Location": "Kinshasa"},
    {"Branch": "Tshikapa Shop", "Location": "Kinshasa"},
    {"Branch": "Appolo Depot", "Location": "Kinshasa"},
    {"Branch": "R P Ngaba", "Location": "Kinshasa"},
    {"Branch": "Liberte", "Location": "Kinshasa"},
    {"Branch": "UPN", "Location": "Kinshasa"},
    {"Branch": "NCPC Shop", "Location": "Kinshasa"},
    {"Branch": "Kisangani Shop", "Location": "Kinshasa"},
    {"Branch": "Mbandaka Shop", "Location": "Kinshasa"},
    {"Branch": "Kananga Shop", "Location": "Kinshasa"},
    {"Branch": "Mwevu Shop", "Location": "Lubumbashi"},
    {"Branch": "Kolwezi Shop", "Location": "Lubumbashi"},
    {"Branch": "Likasi Shop", "Location": "Lubumbashi"},
    {"Branch": "Bunia Shop", "Location": "Goma"},
    {"Branch": "Bukavu Shop", "Location": "Goma"},
    {"Branch": "Goma Shop", "Location": "Goma"},
    {"Branch": "Kikwit Shop", "Location": "Kinshasa"},
    {"Branch": "Matadi Kibala", "Location": "Kinshasa"},
    {"Branch": "Matete Shop", "Location": "Kinshasa"},
    {"Branch": "Kingaraz", "Location": "Kinshasa"},
    {"Branch": "Quartier 1 Shop", "Location": "Kinshasa"},
    {"Branch": "Bibwa Shop", "Location": "Kinshasa"},
    {"Branch": "Gemena Shop", "Location": "Kinshasa"},
    {"Branch": "Pompage Shop", "Location": "Kinshasa"},
    {"Branch": "Millennial Shop", "Location": "Kinshasa"},
]
df_location = pd.DataFrame(branches)
df_location.to_excel(os.path.join(LOCATION_MASTER_DIR, "Location & Branch Master.xlsx"), index=False)

# Supplier Master
suppliers_data = [
    {"Supplier_Name": "Biomatrix Healthcare Pvt Ltd", "Location": "India", "Lead_Time": 45, "Currency": "USD"},
    {"Supplier_Name": "Yiwu Royal", "Location": "China", "Lead_Time": 60, "Currency": "USD"},
    {"Supplier_Name": "Scott Edil Pharmacia Ltd", "Location": "India", "Lead_Time": 30, "Currency": "USD"},
    {"Supplier_Name": "Lincoln Pharmaceuticlas Ltd", "Location": "India", "Lead_Time": 35, "Currency": "USD"},
    {"Supplier_Name": "Coral Markering", "Location": "China", "Lead_Time": 50, "Currency": "USD"},
    {"Supplier_Name": "Prince Pharma CR", "Location": "DRC", "Lead_Time": 20, "Currency": "USD"},
    {"Supplier_Name": "Prince Pharma Lushi CR", "Location": "DRC", "Lead_Time": 25, "Currency": "USD"},
    {"Supplier_Name": "Moon CR", "Location": "DRC", "Lead_Time": 15, "Currency": "USD"},
    {"Supplier_Name": "Inter md (Epdis)", "Location": "Belgium", "Lead_Time": 70, "Currency": "EUR"},
    {"Supplier_Name": "MacLeods Pharmaceuticals Ltd", "Location": "India", "Lead_Time": 40, "Currency": "USD"},
    {"Supplier_Name": "Safeguard Contraceptives Pvt Ltd", "Location": "India", "Lead_Time": 55, "Currency": "USD"},
    {"Supplier_Name": "Kavit Soap Industries", "Location": "India", "Lead_Time": 28, "Currency": "USD"},
    {"Supplier_Name": "Ambadnya Life Science Llc", "Location": "India", "Lead_Time": 32, "Currency": "USD"},
    {"Supplier_Name": "Shalina Healthcare Sarl", "Location": "DRC", "Lead_Time": 18, "Currency": "USD"},
    {"Supplier_Name": "Medico Plus Pharma", "Location": "DRC", "Lead_Time": 22, "Currency": "USD"},
    {"Supplier_Name": "Cato Pharma", "Location": "DRC", "Lead_Time": 26, "Currency": "USD"},
    {"Supplier_Name": "Arau Phar Sarl CR", "Location": "DRC", "Lead_Time": 20, "Currency": "USD"},
    {"Supplier_Name": "Saarah Pharmacy", "Location": "DRC", "Lead_Time": 24, "Currency": "USD"},
    {"Supplier_Name": "Promed Pharma Lushi CR", "Location": "DRC", "Lead_Time": 16, "Currency": "USD"},
    {"Supplier_Name": "Inda Pharma CR", "Location": "DRC", "Lead_Time": 21, "Currency": "USD"},
    {"Supplier_Name": "Diver CR (Kisangani)", "Location": "DRC", "Lead_Time": 19, "Currency": "USD"},
    {"Supplier_Name": "Moon Pharma Lushi CR", "Location": "DRC", "Lead_Time": 23, "Currency": "USD"},
    {"Supplier_Name": "Cogezaf S.A.", "Location": "Belgium", "Lead_Time": 65, "Currency": "EUR"},
    {"Supplier_Name": "Ibis Pharma", "Location": "Belgium", "Lead_Time": 60, "Currency": "EUR"},
    {"Supplier_Name": "Sifa Pharma Lushi CR", "Location": "DRC", "Lead_Time": 17, "Currency": "USD"},
    {"Supplier_Name": "Aiveen Pharma CR", "Location": "DRC", "Lead_Time": 18, "Currency": "USD"},
    {"Supplier_Name": "Star Pharma Kisangani", "Location": "DRC", "Lead_Time": 22, "Currency": "USD"},
    {"Supplier_Name": "Union Pharma CR", "Location": "DRC", "Lead_Time": 20, "Currency": "USD"},
    {"Supplier_Name": "Auxi Pharmaceuticals", "Location": "India", "Lead_Time": 33, "Currency": "USD"},
    {"Supplier_Name": "Distriphar", "Location": "Belgium", "Lead_Time": 68, "Currency": "EUR"},
    {"Supplier_Name": "Sofaco CR", "Location": "DRC", "Lead_Time": 15, "Currency": "USD"},
    {"Supplier_Name": "Piex Life Provider", "Location": "DRC", "Lead_Time": 19, "Currency": "USD"},
    {"Supplier_Name": "Ets Merdi Pharma", "Location": "DRC", "Lead_Time": 21, "Currency": "USD"},
    {"Supplier_Name": "Pharmex CR", "Location": "DRC", "Lead_Time": 22, "Currency": "USD"},
    {"Supplier_Name": "Sun Gold Pharma CR", "Location": "DRC", "Lead_Time": 18, "Currency": "USD"},
    {"Supplier_Name": "Compegnon CR", "Location": "DRC", "Lead_Time": 20, "Currency": "USD"},
    {"Supplier_Name": "Patriot Pharma CR", "Location": "DRC", "Lead_Time": 23, "Currency": "USD"},
    {"Supplier_Name": "Aarmed Formulations Pvt Ltd", "Location": "India", "Lead_Time": 30, "Currency": "USD"},
    {"Supplier_Name": "Acme Lifetech Llp", "Location": "India", "Lead_Time": 34, "Currency": "USD"},
    {"Supplier_Name": "Alaina Healthcare Pvt Ltd", "Location": "India", "Lead_Time": 29, "Currency": "USD"},
    {"Supplier_Name": "Alliance", "Location": "Europe", "Lead_Time": 72, "Currency": "EUR"},
    {"Supplier_Name": "Olive Healthcare", "Location": "India", "Lead_Time": 35, "Currency": "USD"},
    {"Supplier_Name": "AykA Pharma", "Location": "India", "Lead_Time": 32, "Currency": "USD"},
    {"Supplier_Name": "Polybond India Pvt Ltd", "Location": "India", "Lead_Time": 38, "Currency": "USD"},
    {"Supplier_Name": "Vanguard Pharma", "Location": "India", "Lead_Time": 40, "Currency": "USD"},
]
df_supplier = pd.DataFrame(suppliers_data)
df_supplier.to_excel(os.path.join(SUPPLIER_MASTER_DIR, "Supplier Master.xlsx"), index=False)

# Items (500 products)
product_groups = [
    "UNIQUE A", "UNIQUE GENERIC", "UNIQUE SERGICAL", "UNIQUE CARDIAC",
    "UNIQUE FLAMINGO", "UNIQUE OPTHA", "UNIQUE HOSPITAL MATERIAL",
    "VITES", "GENERAL", "SPECIALITIES", "OTC PRODUCTS"
]
divisions = ["Marketing", "Generic", "Surgical", "Cardiac", "Optha", "Hospital", "OTC Products"]

items = []
for i in range(1, 501):
    code = f"FG{i:05d}"
    group = random.choice(product_groups)
    division = random.choice(divisions)
    brand = random.choice([
        "Panadol", "Amoxil", "Brufen", "Losec", "Glucophage", "Augmentin",
        "Zithromax", "Ciproxin", "Flagyl", "Ventolin", "Trixon", "Perfac",
        "Secours", "Luther", "Teltas", "Uniclav", "Ceftriaxone"
    ])
    name = f"{brand} {random.choice(['500MG', '1G', '250MG', '10MG', '20MG'])} {random.choice(['TAB', 'CAP', 'INJ', 'SUSP', 'CREAM'])}"
    supplier = random.choice(suppliers_data)["Supplier_Name"]
    items.append({
        "Item_Code": code,
        "Item Name (DRC)": name,
        "Brand Name": brand if random.random() > 0.3 else "",
        "Product Group": group,
        "Division": division,
        "Supplier Name 1": supplier,
        "Supplier Name 2": random.choice(suppliers_data)["Supplier_Name"] if random.random() > 0.6 else "",
        "Supplier Name 3": random.choice(suppliers_data)["Supplier_Name"] if random.random() > 0.8 else "",
        "Supplier Name 4": random.choice(suppliers_data)["Supplier_Name"] if random.random() > 0.9 else "",
        "Supplier Name 5": random.choice(suppliers_data)["Supplier_Name"] if random.random() > 0.95 else "",
    })
df_item = pd.DataFrame(items)
df_item.to_excel(os.path.join(ITEM_MASTER_DIR, "Item Master.xlsx"), index=False)

# ------------------------------
# 2. SALES DATA
# ------------------------------
item_map = {row["Item_Code"]: {"name": row["Item Name (DRC)"], "price": round(np.random.uniform(1, 50), 2)} for _, row in df_item.iterrows()}
for code, data in item_map.items():
    group = df_item[df_item["Item_Code"] == code]["Product Group"].iloc[0]
    if "INJECTABLE" in data["name"] or "INJ" in data["name"]:
        data["price"] = round(data["price"] * 1.5, 2)
    elif "CAP" in data["name"] or "TAB" in data["name"]:
        data["price"] = round(data["price"] * 0.8, 2)

customers = [f"Customer_{i}" for i in range(1, 101)]
customer_ids = [f"CUST{i:03d}" for i in range(1, 101)]

start_date = datetime(2024, 1, 1)
end_date = datetime(2026, 7, 31)
sales_records = []

current = start_date
while current <= end_date:
    year = current.year
    month = current.month
    num_transactions = int(np.random.normal(500, 150))
    num_transactions = max(200, min(1500, num_transactions))
    data = []
    for _ in range(num_transactions):
        day = random.randint(1, 28)
        sale_date = datetime(year, month, day)
        branch = random.choice(branches)["Branch"]
        item_code = random.choice(df_item["Item_Code"].tolist())
        item_info = item_map[item_code]
        quantity = int(np.random.normal(20, 10))
        quantity = max(1, quantity)
        free_qty = int(np.random.normal(2, 1)) if random.random() > 0.7 else 0
        free_qty = max(0, free_qty)
        price = item_info["price"]
        amount = (quantity + free_qty) * price
        customer = random.choice(customers)
        customer_id = customer_ids[customers.index(customer)]
        invoice_no = f"INV-{year}{month:02d}{day:02d}-{branch[:3]}-{random.randint(100,999)}"
        data.append({
            "Sale_Date": sale_date,
            "Branch": branch,
            "Item_Code": item_code,
            "Invoice_No": invoice_no,
            "Customer_Name": customer,
            "Customer_Id": customer_id,
            "Quantity": quantity,
            "Free_Qty": free_qty,
            "Price": price,
            "Amount_USD": amount,
            "Sales_Type": random.choice(["Retail", "Wholesale", "Hospital"])
        })
        sales_records.append({"Sale_Date": sale_date, "Branch": branch, "Item_Code": item_code, "Invoice_No": invoice_no, "Quantity": quantity, "Amount_USD": amount})
    df_month = pd.DataFrame(data)
    last_day = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    last_day_num = last_day.day
    filename = f"01) {year} {current.strftime('%b').upper()} 01-{last_day_num:02d}_CLEAN.csv"
    df_month.to_csv(os.path.join(SALES_DIR, filename), index=False)
    print(f"✅ Generated sales for {current.strftime('%Y-%m')} – {num_transactions} transactions")
    if current.month == 12:
        current = current.replace(year=current.year+1, month=1)
    else:
        current = current.replace(month=current.month+1)

print(f"✅ Total sales records generated: {len(sales_records)}")

# ------------------------------
# 3. RETURNS (5-10% of sales)
# ------------------------------
return_records = []
num_returns = int(len(sales_records) * 0.07)
chosen_sales = random.sample(sales_records, num_returns)
for sale in chosen_sales:
    return_qty = int(np.random.normal(sale["Quantity"] * 0.2, 2))
    return_qty = max(1, min(return_qty, sale["Quantity"]))
    return_date = sale["Sale_Date"] + timedelta(days=random.randint(1, 30))
    return_amt = return_qty * (sale["Amount_USD"] / sale["Quantity"])
    return_no = f"RET-{sale['Invoice_No']}"
    return_records.append({
        "Return_Date": return_date,
        "Branch": sale["Branch"],
        "Item_Code": sale["Item_Code"],
        "Return_No": return_no,
        "Customer_Name": random.choice(customers),
        "Invoice_No": sale["Invoice_No"],
        "Return_Qty": return_qty,
        "Amount_USD": return_amt
    })
df_returns = pd.DataFrame(return_records)
df_returns.to_excel(os.path.join(RETURNS_DIR, "SALES RETRUN DATA.xlsx"), index=False)
print(f"✅ Returns generated: {len(return_records)}")

# ------------------------------
# 4. STOCK FILES
# ------------------------------
sales_df = pd.DataFrame(sales_records)
avg_sales = sales_df.groupby(["Item_Code", "Branch"])["Quantity"].mean().reset_index()
avg_sales.columns = ["Item_Code", "Branch", "Avg_Daily_Sales"]

stock_data = []
stock_date = datetime(2026, 8, 20)
for branch in branches:
    branch_name = branch["Branch"]
    for item_code in df_item["Item_Code"].tolist():
        avg = avg_sales.loc[(avg_sales["Item_Code"] == item_code) & (avg_sales["Branch"] == branch_name), "Avg_Daily_Sales"]
        if not avg.empty:
            avg_val = avg.iloc[0]
            coverage = random.randint(15, 60)
            stock = int(avg_val * coverage * (0.8 + 0.4 * random.random()))
            stock = max(0, stock)
        else:
            stock = random.randint(50, 500)
        stock_data.append({
            "Item": df_item[df_item["Item_Code"] == item_code]["Item Name (DRC)"].iloc[0],
            "Item Code": item_code,
            "Branch": branch_name,
            "Stock": stock
        })

df_stock_pivot = pd.DataFrame(stock_data)
df_stock_wide = df_stock_pivot.pivot(index=["Item", "Item Code"], columns="Branch", values="Stock").reset_index()
df_stock_wide.columns.name = None

loc_groups = {
    "Kinshasa & Goma": [b["Branch"] for b in branches if b["Location"] in ["Kinshasa", "Goma"]],
    "Lubumbashi": [b["Branch"] for b in branches if b["Location"] == "Lubumbashi"]
}

for loc_name, branch_list in loc_groups.items():
    cols = ["Item", "Item Code"] + [b for b in branch_list if b in df_stock_wide.columns]
    df_loc = df_stock_wide[cols].copy()
    rename_dict = {b: f"{b}_STOCK" for b in branch_list if b in df_loc.columns}
    df_loc = df_loc.rename(columns=rename_dict)
    df_loc = df_loc.rename(columns={"Item": "ITEMNAME", "Item Code": "ITEMNUMBER"})
    for b in branch_list:
        col = f"{b}_STOCK"
        if col not in df_loc.columns:
            df_loc[col] = 0
    cols_order = ["ITEMNAME", "ITEMNUMBER"] + [f"{b}_STOCK" for b in branch_list]
    df_loc = df_loc[cols_order]
    stock_date_str = stock_date.strftime("%d.%m.%Y")
    filename = f"Stock Level File-{loc_name} -1({stock_date_str}).xlsx"
    df_loc.to_excel(os.path.join(STOCK_DIR, filename), index=False)
    print(f"✅ Stock file generated: {filename}")

# ------------------------------
# 5. LOCAL PURCHASE
# ------------------------------
local_purchases = []
for _ in range(2000):
    purchase_date = start_date + timedelta(days=random.randint(0, 900))
    branch = random.choice(branches)["Branch"]
    vendor = random.choice(suppliers_data)["Supplier_Name"]
    item_code = random.choice(df_item["Item_Code"].tolist())
    item_name = item_map[item_code]["name"]
    qty = int(np.random.normal(200, 80))
    qty = max(1, qty)
    cost = round(item_map[item_code]["price"] * random.uniform(0.6, 0.9), 2)
    foc_qty = int(np.random.normal(10, 5)) if random.random() > 0.8 else 0
    foc_qty = max(0, foc_qty)
    amount = (qty + foc_qty) * cost
    if random.random() < 0.03:
        qty = -qty
        amount = -amount
    local_purchases.append({
        "Branch": branch,
        "Doc ID": f"PO-{purchase_date.strftime('%Y%m%d')}-{random.randint(100,999)}",
        "Ref. No.": f"REF-{random.randint(1000,9999)}",
        "Doc Dt.": purchase_date,
        "Vendor Name": vendor,
        "Item Name": item_name,
        "Item Code": item_code,
        "Qty": qty,
        "Cost Rate": cost,
        "FOC Qty": foc_qty,
        "Amount-USD": amount
    })
df_local_purchase = pd.DataFrame(local_purchases)
df_local_purchase.to_excel(os.path.join(LOCAL_PURCHASE_DIR, "Local Purchase.xlsx"), index=False)
print(f"✅ Local purchase data generated: {len(local_purchases)} records.")

# ------------------------------
# 6. IMPORT PURCHASE
# ------------------------------
import_purchases = []
for _ in range(1000):
    purchase_date = start_date + timedelta(days=random.randint(0, 900))
    vendor = random.choice(suppliers_data)["Supplier_Name"]
    item_code = random.choice(df_item["Item_Code"].tolist())
    item_name = item_map[item_code]["name"]
    qty = int(np.random.normal(500, 150))
    qty = max(10, qty)
    cost = round(item_map[item_code]["price"] * random.uniform(0.5, 0.8), 2)
    foc_qty = int(np.random.normal(20, 10)) if random.random() > 0.7 else 0
    foc_qty = max(0, foc_qty)
    amount = (qty + foc_qty) * cost
    lead_time = random.choice([30, 45, 60, 90])
    import_purchases.append({
        "GRN No": f"GRN-{purchase_date.strftime('%Y%m%d')}-{random.randint(100,999)}",
        "GRN Date": purchase_date,
        "Item Name (DRC)": item_name,
        "Item Code": item_code,
        "Qty": qty,
        "FOC": foc_qty,
        "Supplier Rate": cost,
        "Amount": amount,
        "Shipping Lead Time": lead_time,
        "Country": random.choice(["Belgium", "India", "China", "Switzerland"]),
        "Location": random.choice(["Kinshasa", "Goma", "Lubumbashi"])
    })
df_import_purchase = pd.DataFrame(import_purchases)
df_import_purchase.to_excel(os.path.join(IMPORT_PURCHASE_DIR, "Purchase (import).xlsx"), index=False)
print(f"✅ Import purchase data generated: {len(import_purchases)} records.")

# ------------------------------
# 7. PRF/PO DATA
# ------------------------------
prf_data = []
for i in range(200):
    po_date = start_date + timedelta(days=random.randint(0, 800))
    supplier = random.choice(suppliers_data)["Supplier_Name"]
    item_code = random.choice(df_item["Item_Code"].tolist())
    item_name = item_map[item_code]["name"]
    po_qty = int(np.random.normal(300, 100))
    po_qty = max(10, po_qty)
    po_rate = round(item_map[item_code]["price"] * random.uniform(0.5, 0.9), 2)
    status = random.choice(["PO Issued – Awaiting BL", "Transit", "Goods Received at Warehouse", "Closed"])
    prf_data.append({
        "PRF_Date": po_date - timedelta(days=random.randint(10, 30)),
        "PO_Date": po_date,
        "Supplier_Name": supplier,
        "Item_Code": item_code,
        "Product_Name_(DRC)": item_name,
        "PO_Qty": po_qty,
        "PO_Rate": po_rate,
        "PO_Total_Amount": po_qty * po_rate,
        "Shipment_Status": status,
        "GRN_Date": po_date + timedelta(days=random.randint(5, 20)) if status in ["Goods Received at Warehouse", "Closed"] else None,
        "PO_Status": "Closed" if status in ["Goods Received at Warehouse", "Closed"] else "Open",
        "PRF_Location": random.choice(["Kinshasa", "Goma", "Lubumbashi"]),
        "PRF_Qty": po_qty,
        "PI_Qty": po_qty if random.random() > 0.2 else po_qty * 0.8,
        "Invoice_Amount": po_qty * po_rate,
    })
df_prf = pd.DataFrame(prf_data)
filepath = os.path.join(PRF_PO_DIR, "PRF,P.O,QTY(PENDING),ADVANCE,ADVANCE BALANCE,DEPTACH DETAILS,LEADTIME.xlsx")
with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
    df_prf.to_excel(writer, sheet_name="Data", index=False)
print(f"✅ PRF/PO data generated: {len(prf_data)} records.")

print("\n🎉 All dummy data generated successfully!")
print(f"Data folders created in: {BASE_DIR}")
