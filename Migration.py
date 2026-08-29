"""
PHARMA BI - COMPLETE MIGRATION SCRIPT (FIXED)
Reads all data files, inserts into DuckDB, and builds all tables.
Includes Supplier Master, Safety Stock, FOC, and Supplier‑enriched tables.
"""

import os
import sys
import json
import hashlib
import pandas as pd
import duckdb
from pathlib import Path
from datetime import datetime, timedelta
import warnings
import re
import traceback
import numpy as np
import gc

warnings.filterwarnings('ignore')

# ============================================================================
# PATHS
# ============================================================================
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_PATH, "duckdb", "business.db")
LOG_PATH = os.path.join(BASE_PATH, "logs")
METADATA_PATH = os.path.join(BASE_PATH, "metadata")
STOCK_PATH = os.path.join(BASE_PATH, "Stock")
LOCAL_PURCHASE_PATH = os.path.join(BASE_PATH, "Local Purchase Data")
IMPORT_PURCHASE_PATH = os.path.join(BASE_PATH, "Purchase Data")
SALES_PATH = os.path.join(BASE_PATH, "Sales Data")
RETURNS_PATH = os.path.join(BASE_PATH, "Sales Return Data")
LOC_MASTER_PATH = os.path.join(BASE_PATH, "Location & Branch Master", "Location & Branch Master.xlsx")
ITEM_MASTER_PATH = os.path.join(BASE_PATH, "ITEM MASTER", "Item Master.xlsx")
PRF_PO_PATH = os.path.join(BASE_PATH, "P.O.PRF,PI ETC")
SUPPLIER_MASTER_PATH = os.path.join(BASE_PATH, "Supplier Master")

# Ensure directories exist
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(LOG_PATH).mkdir(parents=True, exist_ok=True)
Path(METADATA_PATH).mkdir(parents=True, exist_ok=True)
Path(STOCK_PATH).mkdir(parents=True, exist_ok=True)
Path(LOCAL_PURCHASE_PATH).mkdir(parents=True, exist_ok=True)
Path(IMPORT_PURCHASE_PATH).mkdir(parents=True, exist_ok=True)
Path(SALES_PATH).mkdir(parents=True, exist_ok=True)
Path(RETURNS_PATH).mkdir(parents=True, exist_ok=True)
Path(PRF_PO_PATH).mkdir(parents=True, exist_ok=True)

# ============================================================================
# LOGGING
# ============================================================================
class AdvancedLogger:
    def __init__(self):
        self.start_time = datetime.now()
        self.log_file = os.path.join(LOG_PATH, f"migration_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log")
        self.log_handle = open(self.log_file, 'w', encoding='utf-8')
        self.write_header()
        self.processed_files = []
        self.skipped_files = []
        self.failed_files = []
        self.summary_data = []
        self.metadata = self.load_metadata()
    
    def write_header(self):
        self.log_handle.write("="*100 + "\n")
        self.log_handle.write("PHARMA BI - COMPLETE MIGRATION LOG (FIXED)\n")
        self.log_handle.write(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_handle.write("="*100 + "\n\n")
    
    def log(self, msg, level="INFO", print_console=True):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if print_console:
            icons = {
                "INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️",
                "FILE": "📄", "TABLE": "📊", "DATA": "📁", "PROGRESS": "⏳",
                "SKIP": "⏭️", "UPDATE": "🔄", "VALIDATE": "✔️", "STOCK": "📦",
                "PURCHASE": "🛒", "SALES": "💰", "RETURNS": "🔄", "SUPPLIER": "🏢",
                "FOC": "🎯", "SAFETY": "🛡️"
            }
            icon = icons.get(level, "ℹ️")
            print(f"{icon} [{timestamp}] {msg}")
        full_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_handle.write(f"[{full_timestamp}] [{level}] {msg}\n")
        self.log_handle.flush()
    
    def load_metadata(self):
        metadata_file = os.path.join(METADATA_PATH, "file_registry.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_metadata(self):
        metadata_file = os.path.join(METADATA_PATH, "file_registry.json")
        with open(metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    def get_file_hash(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None
    
    def get_file_info(self, file_path):
        try:
            stat = os.stat(file_path)
            return {
                'path': file_path,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'hash': self.get_file_hash(file_path)
            }
        except:
            return None
    
    def log_file_info(self, file_name, records, min_date, max_date, status="LOADED", warning=None):
        self.log(f"FILE: {file_name}", "FILE")
        self.log(f"  └─ Records: {records:,}", "DATA")
        self.log(f"  └─ Period: {min_date} → {max_date}", "DATA")
        if warning:
            self.log(f"  └─ ⚠️ WARNING: {warning}", "WARNING")
        self.log(f"  └─ Status: {status}", "SUCCESS" if status == "LOADED" else "WARNING")
        self.summary_data.append({
            'File': file_name,
            'Records': records,
            'Min_Date': min_date,
            'Max_Date': max_date,
            'Status': status,
            'Warning': warning or ''
        })
    
    def log_table_info(self, table_name, records, status="CREATED"):
        self.log(f"TABLE: {table_name} → {records:,} records", "TABLE")
        self.summary_data.append({
            'File': f"TABLE: {table_name}",
            'Records': records,
            'Min_Date': '',
            'Max_Date': '',
            'Status': status,
            'Warning': ''
        })
    
    def save_summary(self):
        if self.summary_data:
            df = pd.DataFrame(self.summary_data)
            csv_path = os.path.join(LOG_PATH, f"migration_summary_{self.start_time.strftime('%Y%m%d_%H%M%S')}.csv")
            df.to_csv(csv_path, index=False)
            self.log(f"Summary saved: {csv_path}", "INFO")
        self.save_metadata()
        self.log_handle.write("\n" + "="*100 + "\n")
        self.log_handle.write(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_handle.write(f"Processed: {len(self.processed_files)} files\n")
        self.log_handle.write(f"Skipped: {len(self.skipped_files)} files (unchanged)\n")
        self.log_handle.write(f"Failed: {len(self.failed_files)} files\n")
        self.log_handle.write("="*100 + "\n")
        self.log_handle.close()

logger = AdvancedLogger()

# ============================================================================
# DATE PARSER
# ============================================================================
class DateParser:
    @staticmethod
    def detect_format(series):
        sample = series.dropna().head(50)
        formats = [
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d',
            '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y',
            '%m-%d-%Y', '%m/%d/%Y', '%m.%d.%Y', '%m-%d-%y',
            '%d-%b-%Y', '%d-%b-%y', '%b-%d-%Y', '%d %b %Y',
            '%b %d, %Y', '%B %d, %Y',
        ]
        for fmt in formats:
            try:
                test = pd.to_datetime(sample, format=fmt, errors='coerce')
                if test.notna().sum() > len(sample) * 0.8:
                    return fmt
            except:
                continue
        return None
    
    @staticmethod
    def parse(series):
        if series.empty:
            return series
        fmt = DateParser.detect_format(series)
        if fmt:
            return pd.to_datetime(series, format=fmt, errors='coerce')
        else:
            return pd.to_datetime(series, errors='coerce')

# ============================================================================
# PURCHASE RETURN PROCESSOR (FIXED)
# ============================================================================
class PurchaseReturnProcessor:
    def __init__(self):
        self.folder = LOCAL_PURCHASE_PATH
    
    def process_returns_from_files(self):
        files = [f for f in os.listdir(self.folder) if f.endswith('.xlsx') and not f.startswith('~')]
        if not files:
            logger.log("No local purchase files found for returns extraction", "WARNING")
            return None
        
        all_returns = []
        for file in files:
            file_path = os.path.join(self.folder, file)
            try:
                df = pd.read_excel(file_path)
                df.columns = [str(c).strip() for c in df.columns.tolist()]
                
                rename_map = {
                    'BRANCH': 'Branch', 'Doc Id.': 'Doc_ID', 'Ref. No.': 'Ref_No',
                    'Doc Dt.': 'Purchase_Date', 'Vendor Name': 'Vendor',
                    'Supplier': 'Vendor', 'Supplier Name': 'Vendor',
                    'Item Name': 'Item_Name', 'Item Code': 'Item_Code',
                    'Purchaseunit': 'Unit', 'Qty': 'Qty', 'Quantity': 'Qty',
                    'Cost Rate': 'Cost_Rate', 'Unit Price': 'Cost_Rate',
                    'FOC Qty': 'FOC_Qty', 'Rate-USD': 'Rate_USD',
                    'Amount-USD': 'Amount_USD', 'Amount_USD': 'Amount_USD',
                    'Amount': 'Amount_USD',  # fallback
                    'Purchase Qty': 'Qty', 'FOC': 'FOC_Qty',
                }
                for old, new in rename_map.items():
                    if old in df.columns:
                        df = df.rename(columns={old: new})
                
                keep_cols = ['Branch', 'Doc_ID', 'Ref_No', 'Purchase_Date', 'Vendor',
                             'Item_Name', 'Item_Code', 'Qty', 'Cost_Rate', 'FOC_Qty', 'Amount_USD']
                df = df[[c for c in keep_cols if c in df.columns]]
                
                if 'Purchase_Date' in df.columns:
                    df['Purchase_Date'] = DateParser.parse(df['Purchase_Date'])
                
                for col in ['Qty', 'Cost_Rate', 'FOC_Qty', 'Amount_USD']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                df = df.dropna(subset=['Item_Code', 'Purchase_Date'])
                
                returns_df = df[(df['Qty'] < 0) | (df['Amount_USD'] < 0) | (df['FOC_Qty'] < 0)].copy()
                if not returns_df.empty:
                    for col in ['Qty', 'Amount_USD', 'FOC_Qty']:
                        if col in returns_df.columns:
                            returns_df[col] = returns_df[col].abs()
                    returns_df['Return_Type'] = 'PURCHASE_RETURN'
                    all_returns.append(returns_df)
                    logger.log(f"  └─ Found {len(returns_df)} return rows in {file}", "WARNING")
                del df, returns_df
                gc.collect()
            except Exception as e:
                logger.log(f"  ❌ Error processing {file} for returns: {e}", "ERROR")
                traceback.print_exc()
        
        if all_returns:
            combined = pd.concat(all_returns, ignore_index=True)
            logger.log(f"📊 Total purchase return records: {len(combined):,}", "DATA")
            return combined
        return None

# ============================================================================
# LOCAL PURCHASE PROCESSOR (FIXED)
# ============================================================================
class LocalPurchaseProcessor:
    def __init__(self):
        self.folder = LOCAL_PURCHASE_PATH
    
    def process_files(self):
        files = [f for f in os.listdir(self.folder) if f.endswith('.xlsx') and not f.startswith('~')]
        if not files:
            logger.log("No local purchase files found", "WARNING")
            return None
        
        all_dfs = []
        for file in files:
            file_path = os.path.join(self.folder, file)
            try:
                df = pd.read_excel(file_path)
                df.columns = [str(c).strip() for c in df.columns.tolist()]
                
                rename_map = {
                    'BRANCH': 'Branch', 'Doc Id.': 'Doc_ID', 'Ref. No.': 'Ref_No',
                    'Doc Dt.': 'Purchase_Date', 'Vendor Name': 'Vendor',
                    'Supplier': 'Vendor', 'Supplier Name': 'Vendor',
                    'Item Name': 'Item_Name', 'Item Code': 'Item_Code',
                    'Purchaseunit': 'Unit', 'Qty': 'Qty', 'Quantity': 'Qty',
                    'Cost Rate': 'Cost_Rate', 'Unit Price': 'Cost_Rate',
                    'FOC Qty': 'FOC_Qty', 'Rate-USD': 'Rate_USD',
                    'Amount-USD': 'Amount_USD', 'Amount_USD': 'Amount_USD',
                    'Amount': 'Amount_USD',  # fallback
                    'Purchase Qty': 'Qty', 'FOC': 'FOC_Qty',
                }
                for old, new in rename_map.items():
                    if old in df.columns:
                        df = df.rename(columns={old: new})
                
                keep_cols = ['Branch', 'Doc_ID', 'Ref_No', 'Purchase_Date', 'Vendor',
                             'Item_Name', 'Item_Code', 'Qty', 'Cost_Rate', 'FOC_Qty', 'Amount_USD']
                df = df[[c for c in keep_cols if c in df.columns]]
                
                if 'Purchase_Date' in df.columns:
                    df['Purchase_Date'] = DateParser.parse(df['Purchase_Date'])
                
                for col in ['Qty', 'Cost_Rate', 'FOC_Qty', 'Amount_USD']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                df = df.dropna(subset=['Item_Code', 'Purchase_Date'])
                
                # Filter out returns
                df = df[(df['Qty'] >= 0) & (df['Amount_USD'] >= 0) & (df['Cost_Rate'] >= 0)].copy()
                
                if not df.empty:
                    all_dfs.append(df)
                    min_date = df['Purchase_Date'].min().strftime('%Y-%m-%d') if not df['Purchase_Date'].isna().all() else 'N/A'
                    max_date = df['Purchase_Date'].max().strftime('%Y-%m-%d') if not df['Purchase_Date'].isna().all() else 'N/A'
                    logger.log(f"  ✅ Loaded local purchase file: {file} ({len(df)} rows, {min_date} → {max_date})", "SUCCESS")
                else:
                    logger.log(f"  ⚠️ No valid data in: {file}", "WARNING")
                del df
                gc.collect()
            except Exception as e:
                logger.log(f"  ❌ Error loading {file}: {e}", "ERROR")
                traceback.print_exc()
        
        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            logger.log(f"📊 Total local purchase records (clean): {len(combined):,}", "DATA")
            return combined
        return None

# ============================================================================
# IMPORT PURCHASE PROCESSOR
# ============================================================================
class ImportPurchaseProcessor:
    def __init__(self):
        self.folder = IMPORT_PURCHASE_PATH
    
    def _convert_time_to_decimal(self, val):
        if isinstance(val, str) and ':' in val:
            parts = val.split(':')
            if len(parts) == 3:
                return float(parts[0]) + float(parts[1])/60 + float(parts[2])/3600
            elif len(parts) == 2:
                return float(parts[0]) + float(parts[1])/60
        return val

    def process_files(self):
        files = [f for f in os.listdir(self.folder) if f.endswith('.xlsx') and not f.startswith('~')]
        if not files:
            logger.log("No import purchase files found", "WARNING")
            return None
        
        all_dfs = []
        for file in files:
            file_path = os.path.join(self.folder, file)
            try:
                df = pd.read_excel(file_path)
                df.columns = [str(c).strip() for c in df.columns.tolist()]
                
                rename_map = {
                    'GRN No': 'GRN_No', 'GRN Date': 'Purchase_Date',
                    'Item Name (DRC)': 'Item_Name', 'Item Name (Supplier)': 'Item_Name_Supplier',
                    'Item Code': 'Item_Code', 'Pack Unit (Sales)': 'Unit', 'Qty': 'Qty',
                    'Quantity': 'Qty', 'FOC': 'FOC_Qty', 'Inv No': 'Inv_No', 'Inv Date': 'Inv_Date',
                    'Invoice No': 'Inv_No', 'Invoice Date': 'Inv_Date',
                    'Suplier Name': 'Vendor', 'Supplier': 'Vendor', 'Supplier Name': 'Vendor',
                    'Supplier Rate': 'Supplier_Rate', 'Discount %': 'Discount_Pct', 
                    'Rate After Discount': 'Rate_After_Discount', 'Amount': 'Amount_USD',
                    'BL No': 'BL_No', 'BL Date': 'BL_Date', 'Carrier': 'Carrier',
                    'Transit Time / Shipping Lead Time': 'Shipping_Lead_Time',
                    'Invoice-to-Receipt Lead Time': 'Invoice_Receipt_Lead',
                    'BL Lag / Invoice–Shipment Lag': 'BL_Lag', 'Country': 'Country', 'Location': 'Location',
                    'BL No.': 'BL_No', 'BL Date.': 'BL_Date',
                }
                for old, new in rename_map.items():
                    if old in df.columns:
                        df = df.rename(columns={old: new})
                
                keep_cols = ['GRN_No', 'Purchase_Date', 'Item_Name', 'Item_Name_Supplier',
                             'Item_Code', 'Unit', 'Qty', 'FOC_Qty', 'Inv_No', 'Inv_Date',
                             'Vendor', 'Supplier_Rate', 'Discount_Pct', 'Rate_After_Discount',
                             'Amount_USD', 'BL_No', 'BL_Date', 'Carrier', 'Shipping_Lead_Time',
                             'Invoice_Receipt_Lead', 'BL_Lag', 'Country', 'Location']
                df = df[[c for c in keep_cols if c in df.columns]]
                if 'Supplier_Rate' in df.columns:
                    df['Supplier_Rate'] = df['Supplier_Rate'].apply(self._convert_time_to_decimal)
                for col in ['Purchase_Date', 'Inv_Date', 'BL_Date']:
                    if col in df.columns:
                        df[col] = DateParser.parse(df[col])
                for col in ['Qty', 'FOC_Qty', 'Supplier_Rate', 'Discount_Pct', 
                           'Rate_After_Discount', 'Amount_USD', 'Shipping_Lead_Time',
                           'Invoice_Receipt_Lead', 'BL_Lag']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df = df[(df['Qty'] >= 0) & (df['Amount_USD'] >= 0) & (df['Supplier_Rate'] >= 0)].copy()
                df = df.dropna(subset=['Item_Code', 'Purchase_Date'])
                if not df.empty:
                    all_dfs.append(df)
                    min_date = df['Purchase_Date'].min().strftime('%Y-%m-%d') if not df['Purchase_Date'].isna().all() else 'N/A'
                    max_date = df['Purchase_Date'].max().strftime('%Y-%m-%d') if not df['Purchase_Date'].isna().all() else 'N/A'
                    logger.log(f"  ✅ Loaded import purchase file: {file} ({len(df)} rows, {min_date} → {max_date})", "SUCCESS")
                else:
                    logger.log(f"  ⚠️ No valid data in: {file}", "WARNING")
                del df
                gc.collect()
            except Exception as e:
                logger.log(f"  ❌ Error loading {file}: {e}", "ERROR")
                traceback.print_exc()
        
        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            logger.log(f"📊 Total import purchase records: {len(combined):,}", "DATA")
            return combined
        return None

# ============================================================================
# STOCK FILE PROCESSOR
# ============================================================================
class StockFileProcessor:
    def __init__(self):
        self.folder = STOCK_PATH
    
    def detect_file_format(self, df_raw):
        row0 = df_raw.iloc[0].fillna('').astype(str).tolist()
        row1 = df_raw.iloc[1].fillna('').astype(str).tolist()
        row2 = df_raw.iloc[2].fillna('').astype(str).tolist()
        has_location_header = any('Location' in str(v) for v in row0)
        row1_has_stock = any('STOCK' in str(v).upper() for v in row1)
        row2_has_stock = any('STOCK' in str(v).upper() for v in row2)
        if has_location_header and row2_has_stock and not row1_has_stock:
            return 'lubumbashi'
        else:
            return 'kinshasa'
    
    def parse_stock_file(self, file_path, location_name, month_end_date):
        try:
            df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=10)
            file_format = self.detect_file_format(df_raw)
            row0 = df_raw.iloc[0].fillna('').astype(str).tolist()
            row1 = df_raw.iloc[1].fillna('').astype(str).tolist()
            row2 = df_raw.iloc[2].fillna('').astype(str).tolist()
            
            data_start_row = 2
            for i in range(2, min(10, len(df_raw))):
                row_values = df_raw.iloc[i].fillna('').astype(str).tolist()
                if any('ITEM' in str(v).upper() for v in row_values[:3]):
                    data_start_row = i
                    break
            
            columns = ['ITEMNAME', 'ITEMNUMBER']
            branch_pairs = {}
            
            if file_format == 'lubumbashi':
                col_idx = 2
                while col_idx < len(row1):
                    loc_name = row1[col_idx].strip() if col_idx < len(row1) else ''
                    if not loc_name or loc_name.upper() in ['', 'NAN', 'GRAND TOTAL']:
                        col_idx += 1
                        continue
                    next_val = row2[col_idx + 1].strip() if col_idx + 1 < len(row2) else ''
                    if next_val.upper() in ['STOCKVALUE', 'STOCK VALUE']:
                        stock_col = f"{loc_name}_STOCK"
                        value_col = f"{loc_name}_STOCKVALUE"
                        columns.append(stock_col)
                        columns.append(value_col)
                        branch_pairs[loc_name] = {'stock': stock_col, 'value': value_col}
                        col_idx += 2
                    else:
                        stock_col = f"{loc_name}_STOCK"
                        columns.append(stock_col)
                        branch_pairs[loc_name] = {'stock': stock_col, 'value': None}
                        col_idx += 1
            else:
                col_idx = 2
                while col_idx < len(row0):
                    loc_name = row0[col_idx].strip() if col_idx < len(row0) else ''
                    if not loc_name or loc_name.upper() in ['', 'NAN', 'LOCATION']:
                        col_idx += 1
                        continue
                    next_val = row1[col_idx + 1].strip() if col_idx + 1 < len(row1) else ''
                    if next_val.upper() in ['STOCKVALUE', 'STOCK VALUE']:
                        stock_col = f"{loc_name}_STOCK"
                        value_col = f"{loc_name}_STOCKVALUE"
                        columns.append(stock_col)
                        columns.append(value_col)
                        branch_pairs[loc_name] = {'stock': stock_col, 'value': value_col}
                        col_idx += 2
                    else:
                        stock_col = f"{loc_name}_STOCK"
                        columns.append(stock_col)
                        branch_pairs[loc_name] = {'stock': stock_col, 'value': None}
                        col_idx += 1
            
            df_full = pd.read_excel(file_path, sheet_name=0, header=None)
            data_rows = []
            for i in range(data_start_row + 1, len(df_full)):
                row = df_full.iloc[i].fillna('').tolist()
                if all(str(v).strip() in ['', '-', '--'] for v in row[:3]):
                    continue
                data_rows.append(row)
            
            if not data_rows:
                return None
            
            actual_cols = len(data_rows[0])
            if len(columns) < actual_cols:
                extra_cols = actual_cols - len(columns)
                if extra_cols == 2:
                    columns = columns + ['Grand_Total_STOCK', 'Grand_Total_STOCKVALUE']
                else:
                    columns = columns + [f"EXTRA_{i}" for i in range(extra_cols)]
            
            df = pd.DataFrame(data_rows, columns=columns[:actual_cols])
            if 'ITEMNAME' in df.columns:
                df = df.rename(columns={'ITEMNAME': 'Item_Name'})
            if 'ITEMNUMBER' in df.columns:
                df = df.rename(columns={'ITEMNUMBER': 'Item_Number'})
            
            for col in df.columns:
                if col not in ['Item_Name', 'Item_Number']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            if 'Item_Name' in df.columns:
                df = df[~df['Item_Name'].astype(str).str.upper().isin(['ITEMNAME', 'NAN', '', ' ', 'NONE', 'N/A'])]
                df = df[df['Item_Name'].astype(str).str.strip() != '']
            
            df['File_Location'] = location_name
            df['Month_End_Date'] = month_end_date
            df.attrs['branch_pairs'] = branch_pairs
            return df
        except Exception as e:
            logger.log(f"Error parsing stock file {file_path}: {e}", "ERROR")
            traceback.print_exc()
            return None
    
    def process_stock_files(self):
        stock_files = list(Path(self.folder).glob("Stock Level File-*.xlsx"))
        if not stock_files:
            logger.log("No stock files found", "WARNING")
            return None
        
        logger.log(f"Found {len(stock_files)} stock files", "PROGRESS")
        all_dfs = []
        
        for file_path in stock_files:
            filename = file_path.name
            pattern = r"Stock Level File-(.+?)(?:-\d+)?\((\d{2}\.\d{2}\.\d{4})\)\.xlsx"
            match = re.search(pattern, filename)
            if match:
                location_name = match.group(1).strip()
                month_end_date = datetime.strptime(match.group(2), "%d.%m.%Y")
            else:
                pattern2 = r"Stock Level File-(.+?)\((\d{2}\.\d{2}\.\d{4})\)\.xlsx"
                match2 = re.search(pattern2, filename)
                if match2:
                    location_name = match2.group(1).strip()
                    month_end_date = datetime.strptime(match2.group(2), "%d.%m.%Y")
                else:
                    logger.log(f"Could not parse filename: {filename}", "WARNING")
                    continue
            
            logger.log(f"Processing stock file: {filename}", "STOCK")
            logger.log(f"  └─ Location: {location_name}")
            logger.log(f"  └─ Month End: {month_end_date.strftime('%Y-%m-%d')}")
            
            df = self.parse_stock_file(file_path, location_name, month_end_date)
            if df is not None and not df.empty:
                all_dfs.append(df)
                logger.log(f"  └─ Records: {len(df):,}", "DATA")
            else:
                logger.log(f"  └─ No data loaded", "WARNING")
            del df
            gc.collect()
        
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            logger.log(f"Total stock records: {len(combined_df):,}", "DATA")
            return combined_df
        return None

# ============================================================================
# INCREMENTAL SALES / RETURNS PROCESSOR
# ============================================================================
class IncrementalFileProcessor:
    def __init__(self):
        max_retries = 5
        conn = None
        for attempt in range(max_retries):
            try:
                conn = duckdb.connect(DB_PATH)
                break
            except duckdb.IOException as e:
                if "Resource temporarily unavailable" in str(e) and attempt < max_retries - 1:
                    print(f"⚠️ Database locked, retrying... ({attempt+1}/{max_retries})")
                    import time
                    time.sleep(1.5)
                else:
                    raise
        self.conn = conn
        self.sales_folder = SALES_PATH
        self.returns_folder = RETURNS_PATH

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sales_raw (
                Sale_Date DATE, Branch VARCHAR, Item_Code VARCHAR,
                Invoice_No VARCHAR, Customer_Name VARCHAR, Customer_Id VARCHAR,
                Quantity DOUBLE, Free_Qty DOUBLE, Price DOUBLE, Amount_USD DOUBLE,
                Sales_Type VARCHAR, file_name VARCHAR, file_hash VARCHAR
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS returns_raw (
                Return_Date DATE, Branch VARCHAR, Item_Code VARCHAR,
                Return_No VARCHAR, Customer_Name VARCHAR, Invoice_No VARCHAR,
                Return_Qty DOUBLE, Amount_USD DOUBLE,
                file_name VARCHAR, file_hash VARCHAR
            )
        """)
    
    def process_sales_files(self):
        files = sorted([f for f in os.listdir(self.sales_folder) if f.endswith('.csv') and not f.startswith('~')])
        logger.log(f"Found {len(files)} sales files", "PROGRESS")
        
        for file in files:
            file_path = os.path.join(self.sales_folder, file)
            file_info = logger.get_file_info(file_path)
            if not file_info:
                continue
            
            registry_key = f"sales_{file}"
            prev_info = logger.metadata.get(registry_key)
            current_hash = file_info['hash']
            
            if prev_info and prev_info.get('hash') == current_hash:
                logger.log(f"  ⏭️ Unchanged: {file}", "SKIP")
                logger.skipped_files.append(file)
                continue
            
            logger.log(f"  📄 Processing (new/modified): {file}", "FILE")
            df = self.process_single_sales_file(file_path, file)
            
            if df is not None and not df.empty:
                df = df.drop_duplicates(subset=['Invoice_No', 'Item_Code', 'Sale_Date'])
                self.conn.execute("DELETE FROM sales_raw WHERE file_name = ?", [file])
                df['file_name'] = file
                df['file_hash'] = current_hash
                required_cols = ['Sale_Date', 'Branch', 'Item_Code', 'Invoice_No',
                                 'Customer_Name', 'Customer_Id', 'Quantity', 'Free_Qty',
                                 'Price', 'Amount_USD', 'Sales_Type', 'file_name', 'file_hash']
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = None
                df_subset = df[required_cols]
                self.conn.register('temp_sales', df_subset)
                self.conn.execute("INSERT INTO sales_raw SELECT * FROM temp_sales")
                logger.metadata[registry_key] = {
                    'hash': current_hash,
                    'size': file_info['size'],
                    'modified': file_info['modified'],
                    'processed': datetime.now().isoformat(),
                    'records': len(df)
                }
                logger.processed_files.append(file)
                del df, df_subset
                gc.collect()
            else:
                logger.failed_files.append(file)
        return True
    
    def process_single_sales_file(self, file_path, file_name):
        try:
            df = None
            for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
                    if len(df.columns) > 3:
                        break
                except:
                    continue
            if df is None or df.empty:
                return None
            
            df.columns = [str(c).strip() for c in df.columns.tolist()]
            date_col = None
            for col in df.columns:
                if 'DATE' in col.upper() or 'DT' in col.upper():
                    date_col = col
                    break
            if date_col is None:
                for col in df.columns:
                    try:
                        test = pd.to_datetime(df[col], errors='coerce')
                        if test.notna().sum() > len(df) * 0.5:
                            date_col = col
                            break
                    except:
                        continue
            if date_col is None:
                return None
            df[date_col] = DateParser.parse(df[date_col])
            df = df.dropna(subset=[date_col])
            df = df.rename(columns={date_col: 'Sale_Date'})
            df['Sale_Date'] = pd.to_datetime(df['Sale_Date']).dt.date
            
            rename_map = {
                "BRANCH": "Branch", "INV.NO": "Invoice_No", "CUSTOMER NAME": "Customer_Name",
                "CUSTOMER ID": "Customer_Id", "ITEM NAME": "Item_Name", "ITEM CODE": "Item_Code",
                "Quantity": "Quantity", "Free Qty": "Free_Qty", "Price": "Price",
                "Amount(USD)": "Amount_USD", "Sales Type": "Sales_Type",
                "AMOUNT": "Amount_USD", "CUSTOMER": "Customer_Name"
            }
            for old, new in rename_map.items():
                if old in df.columns:
                    df = df.rename(columns={old: new})
            
            for col in ["Quantity", "Free_Qty", "Price", "Amount_USD"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            if "Quantity" in df.columns:
                df = df[df["Quantity"] > 0]
            
            records = len(df)
            if records > 0:
                min_date = df["Sale_Date"].min().strftime('%Y-%m-%d')
                max_date = df["Sale_Date"].max().strftime('%Y-%m-%d')
                logger.log_file_info(file_name, records, min_date, max_date, "LOADED")
                return df
            else:
                logger.log_file_info(file_name, 0, "N/A", "N/A", "EMPTY")
                return None
        except Exception as e:
            logger.log(f"  Error processing {file_name}: {e}", "ERROR")
            traceback.print_exc()
            return None
    
    def process_returns_file(self):
        files = [f for f in os.listdir(self.returns_folder) 
                 if f.endswith(('.xlsx', '.csv')) and not f.startswith('~')]
        if not files:
            logger.log("No returns files found", "WARNING")
            return False

        processed_any = False
        for file in files:
            file_path = os.path.join(self.returns_folder, file)
            file_info = logger.get_file_info(file_path)
            if not file_info:
                continue

            registry_key = f"returns_{file}"
            prev_info = logger.metadata.get(registry_key)
            current_hash = file_info['hash']

            if prev_info and prev_info.get('hash') == current_hash:
                logger.log(f"  ⏭️ Unchanged returns file: {file}", "SKIP")
                logger.skipped_files.append(file)
                continue

            logger.log(f"  🔄 Processing returns file: {file}", "UPDATE")
            try:
                if file.endswith('.xlsx'):
                    df = pd.read_excel(file_path)
                else:
                    df = None
                    for enc in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
                        try:
                            df = pd.read_csv(file_path, encoding=enc)
                            break
                        except:
                            continue
                    if df is None:
                        raise ValueError("Could not read CSV with any encoding.")

                if df.empty:
                    logger.log(f"  ⚠️ File {file} is empty", "WARNING")
                    logger.failed_files.append(file)
                    continue

                df.columns = [str(c).strip() for c in df.columns]

                rename_map = {
                    "Branch": "Branch", "Return No": "Return_No", "Return Date": "Return_Date",
                    "Customer Name": "Customer_Name", "Invoice No.": "Invoice_No",
                    "Item Name": "Item_Name", "ITEM CODE": "Item_Code",
                    "Return Qty": "Return_Qty", "Amount(USD)": "Amount_USD",
                    "AMOUNT": "Amount_USD", "RETURN DATE": "Return_Date",
                    "RETURN NO": "Return_No", "CUSTOMER": "Customer_Name",
                }
                for old, new in rename_map.items():
                    if old in df.columns:
                        df = df.rename(columns={old: new})

                required = ['Return_Date', 'Branch', 'Item_Code', 'Return_No',
                            'Customer_Name', 'Invoice_No', 'Return_Qty', 'Amount_USD']
                missing = [c for c in required if c not in df.columns]
                if missing:
                    logger.log(f"  ❌ Missing columns in {file}: {missing}", "ERROR")
                    logger.failed_files.append(file)
                    continue

                df['Return_Date'] = pd.to_datetime(df['Return_Date'], errors='coerce')
                df['Return_Date'] = df['Return_Date'].dt.date
                df = df.dropna(subset=['Return_Date'])

                for col in ['Return_Qty', 'Amount_USD']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df = df.dropna(subset=['Item_Code'])

                if df.empty:
                    logger.log(f"  ⚠️ No valid rows after cleaning in {file}", "WARNING")
                    logger.failed_files.append(file)
                    continue

                df = df.drop_duplicates(subset=['Return_No', 'Item_Code', 'Return_Date'])

                min_date = df['Return_Date'].min().strftime('%Y-%m-%d')
                max_date = df['Return_Date'].max().strftime('%Y-%m-%d')
                logger.log_file_info(file, len(df), min_date, max_date, "LOADED")

                self.conn.execute("DELETE FROM returns_raw WHERE file_name = ?", [file])

                df['file_name'] = file
                df['file_hash'] = current_hash

                schema_cols = ['Return_Date', 'Branch', 'Item_Code', 'Return_No',
                               'Customer_Name', 'Invoice_No', 'Return_Qty', 'Amount_USD',
                               'file_name', 'file_hash']
                for col in schema_cols:
                    if col not in df.columns:
                        df[col] = None
                df_subset = df[schema_cols]

                self.conn.register('temp_returns_single', df_subset)
                self.conn.execute("INSERT INTO returns_raw SELECT * FROM temp_returns_single")

                logger.metadata[registry_key] = {
                    'hash': current_hash,
                    'size': file_info['size'],
                    'modified': file_info['modified'],
                    'processed': datetime.now().isoformat(),
                    'records': len(df)
                }
                logger.processed_files.append(file)
                processed_any = True
                del df, df_subset
                gc.collect()

            except Exception as e:
                logger.log(f"  ❌ Error processing returns file {file}: {e}", "ERROR")
                traceback.print_exc()
                logger.failed_files.append(file)
                continue

        return processed_any

# ============================================================================
# PRF/PO PROCESSOR
# ============================================================================
class PRFPOProcessor:
    def __init__(self):
        self.folder = PRF_PO_PATH
        self.file_name = "PRF,P.O,QTY(PENDING),ADVANCE,ADVANCE BALANCE,DEPTACH DETAILS,LEADTIME.xlsx"

    def process_file(self):
        file_path = os.path.join(self.folder, self.file_name)
        if not os.path.exists(file_path):
            logger.log("PRF/PO file not found", "WARNING")
            return None

        try:
            df = pd.read_excel(file_path, sheet_name="Data")
            df.columns = [str(c).strip() for c in df.columns.tolist()]

            date_cols = ['PRF_Date', 'PO_Date', 'PI_Date', 'Advance_Paid_Date',
                        'Invoice_Date', 'BL_Date', 'GRN_Date',
                        'Balance_Paid_Date_Part1', 'Balance_Paid_Date_Part2']
            for col in date_cols:
                if col in df.columns:
                    df[col] = DateParser.parse(df[col])

            numeric_cols = ['PRF_Qty', 'PO_Qty', 'PO_Rate', 'PO_Net_Amount',
                           'PI_Qty', 'PI_FOC_Qty', 'PI_Rate', 'PI_Net_Amount',
                           'Advance_Amount', 'Advance_Amount_Paid',
                           'Dispatched_Qty', 'Invoice_Qty', 'Invoice_Rate',
                           'Invoice_Amount', 'GRN_Qty', 'PO_Other_Charge_Amount',
                           'PO_Total_Amount', 'PI_Total_Amount',
                           'Advance_Percent', 'PO_Age_Days']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            df = df.dropna(subset=['Item_Code'])
            df = df[df['Item_Code'].astype(str).str.strip() != '']

            if df.empty:
                logger.log("PRF/PO file loaded but no valid rows", "WARNING")
                return None

            logger.log(f"📊 Loaded PRF/PO file: {len(df)} rows", "DATA")
            return df

        except Exception as e:
            logger.log(f"Error loading PRF/PO file: {e}", "ERROR")
            traceback.print_exc()
            return None

# ============================================================================
# SUPPLIER MASTER PROCESSOR
# ============================================================================
class SupplierMasterProcessor:
    def __init__(self):
        self.folder = SUPPLIER_MASTER_PATH
        self.file_name = "Supplier Master.xlsx"
    
    def process_file(self):
        file_path = os.path.join(self.folder, self.file_name)
        if not os.path.exists(file_path):
            logger.log("Supplier Master file not found", "WARNING")
            return None
        
        try:
            df = pd.read_excel(file_path, sheet_name="Sheet1")
            df.columns = [str(c).strip() for c in df.columns.tolist()]
            
            rename_map = {
                'Name Of The Supplier': 'Supplier_Name',
                'Location': 'Location',
                'Address': 'Address',
                'File': 'File',
                'Company': 'Company',
                'Currency': 'Currency',
                'City': 'City',
                'District': 'District',
                'State': 'State',
                'Balance Checking Status': 'Balance_Checking_Status',
                'Rate': 'Rate',
                'EURO TO USD RATE': 'Euro_To_USD_Rate',
                'Opening Balance': 'Opening_Balance',
                'Opening Balance Date': 'Opening_Balance_Date',
                'Lead Time': 'Lead_Time',
                'Leadtime': 'Lead_Time',
                'LEAD TIME': 'Lead_Time',
                'LEADTIME': 'Lead_Time',
                'Supplier Lead Time': 'Lead_Time',
                'Delivery Time': 'Lead_Time',
                'Delivery Lead Time': 'Lead_Time',
                'Lead_Time': 'Lead_Time',
                'Supplier Leadtime': 'Lead_Time',
            }
            for old, new in rename_map.items():
                if old in df.columns:
                    df = df.rename(columns={old: new})
            
            if 'Lead_Time' in df.columns:
                df['Lead_Time_Str'] = df['Lead_Time'].astype(str)
                logger.log(f"  └─ Lead Time sample values: {df['Lead_Time_Str'].head(10).tolist()}", "DATA")
                df['Lead_Time_Extracted'] = df['Lead_Time_Str'].str.extract(r'(\d+)')[0]
                df['Lead_Time'] = pd.to_numeric(df['Lead_Time_Extracted'], errors='coerce')
                df['Lead_Time'] = df['Lead_Time'].fillna(
                    pd.to_numeric(df['Lead_Time_Str'].str.replace(' days', '').str.replace(' day', ''), errors='coerce')
                )
                df['Lead_Time'] = df['Lead_Time'].fillna(
                    df['Lead_Time_Str'].str.extract(r'(\d+)\s*[-–]\s*(\d+)').apply(
                        lambda x: (int(x[0]) + int(x[1])) / 2 if pd.notna(x[0]) and pd.notna(x[1]) else None, axis=1
                    )
                )
                df['Lead_Time'] = df['Lead_Time'].fillna(180)
                logger.log(f"  └─ Lead Time distribution:", "DATA")
                logger.log(f"     - Mean: {df['Lead_Time'].mean():.0f} days", "DATA")
                logger.log(f"     - Min: {df['Lead_Time'].min():.0f} days", "DATA")
                logger.log(f"     - Max: {df['Lead_Time'].max():.0f} days", "DATA")
                df = df.drop(['Lead_Time_Str', 'Lead_Time_Extracted'], axis=1, errors='ignore')
            else:
                logger.log("  └─ ⚠️ 'Lead Time' column not found - using default 180 days", "WARNING")
                df['Lead_Time'] = 180
            
            if 'Supplier_Name' in df.columns:
                df['Supplier_Name'] = df['Supplier_Name'].astype(str).str.strip()
            if 'Location' in df.columns:
                df['Location'] = df['Location'].astype(str).str.strip().str.title()
            
            if 'Opening_Balance_Date' in df.columns:
                df['Opening_Balance_Date'] = DateParser.parse(df['Opening_Balance_Date'])
            for col in ['Rate', 'Euro_To_USD_Rate', 'Opening_Balance']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            logger.log(f"📊 Loaded Supplier Master: {len(df)} suppliers", "DATA")
            return df
            
        except Exception as e:
            logger.log(f"Error loading Supplier Master: {e}", "ERROR")
            traceback.print_exc()
            return None

# ============================================================================
# MASTER TABLES CREATION (FIXED – fill nulls)
# ============================================================================
def create_master_tables(conn):
    logger.log("📋 Creating item_master with supplier enhancements...", "PROGRESS")
    item_path = ITEM_MASTER_PATH
    try:
        df = pd.read_excel(item_path, sheet_name="ITEM MASTER")
        df.columns = [str(c).strip() for c in df.columns.tolist()]
        
        rename_map = {
            "Item Code": "Item_Code", "Item Name (DRC)": "Item_Name",
            "Brand Name": "Brand_Name", "Product Group": "Product_Group",
            "Division": "Division", "Dosage Form": "Dosage_Form",
            "Strength / Composition": "Strength", "Pack Size / Presentation": "Pack_Size",
            "Route of Admin": "Route_Admin", "Indications (Summary)": "Indications",
            "Posology / Dosage": "Posology", "Supplier Name 1": "Supplier_1",
            "Supplier Name 2": "Supplier_2", "Supplier Name 3": "Supplier_3",
            "Supplier Name 4": "Supplier_4", "Supplier Name 5": "Supplier_5",
            "Supplier": "Supplier_1", "Supplier 1": "Supplier_1",
            "Supplier 2": "Supplier_2", "Supplier 3": "Supplier_3",
            "Supplier 4": "Supplier_4", "Supplier 5": "Supplier_5",
        }
        for old, new in rename_map.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        
        if "Item_Code" in df.columns:
            df["Item_Code"] = df["Item_Code"].astype(str).str.strip()
            df = df[~df["Item_Code"].str.lower().isin(['nan', 'none', ''])]
        
        supplier_cols = ['Supplier_1', 'Supplier_2', 'Supplier_3', 'Supplier_4', 'Supplier_5']
        for col in supplier_cols:
            if col in df.columns:
                df[col] = df[col].fillna('')
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace(['', 'nan', 'None', 'NaN', 'none', 'N/A'], None)
        
        def get_all_suppliers(row):
            suppliers = []
            for col in supplier_cols:
                if col in row and row[col] and row[col] != '' and str(row[col]).lower() not in ['nan', 'none', 'n/a']:
                    suppliers.append(str(row[col]).strip())
            return suppliers if suppliers else None
        
        df['All_Suppliers'] = df.apply(get_all_suppliers, axis=1)
        df['All_Suppliers'] = df['All_Suppliers'].apply(
            lambda val: [str(v).strip() for v in val] if isinstance(val, list) else None
        )
        
        def get_primary_supplier(row):
            for col in supplier_cols:
                if col in row and row[col] and row[col] != '' and str(row[col]).lower() not in ['nan', 'none', 'n/a']:
                    return str(row[col]).strip()
            return None
        
        df['Primary_Supplier'] = df.apply(get_primary_supplier, axis=1)
        
        # --- FIX: fill all string columns with '' and convert to str ---
        for col in ['Item_Name', 'Brand_Name', 'Product_Group', 'Division', 'Dosage_Form',
                    'Strength', 'Pack_Size', 'Route_Admin', 'Indications', 'Posology']:
            if col not in df.columns:
                df[col] = ''
            df[col] = df[col].fillna('').astype(str)
        
        for col in supplier_cols:
            if col in df.columns:
                df[col] = df[col].fillna('').astype(str)
        
        if 'Primary_Supplier' in df.columns:
            df['Primary_Supplier'] = df['Primary_Supplier'].fillna('').astype(str)
        
        # Clean All_Suppliers to be a list (not None)
        def clean_supplier_list(val):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return []
            if isinstance(val, list):
                return [str(v).strip() for v in val if v and str(v).strip()]
            if isinstance(val, str):
                return [val.strip()] if val.strip() else []
            return []
        df['All_Suppliers'] = df['All_Suppliers'].apply(clean_supplier_list)
        # ----------------------------------------------------------------
        
        conn.register('item_temp', df)
        conn.execute("DROP TABLE IF EXISTS item_master")
        conn.execute("""
            CREATE TABLE item_master AS
            SELECT 
                CAST(Item_Code AS VARCHAR) AS Item_Code,
                CAST(Item_Name AS VARCHAR) AS Item_Name,
                CAST(Brand_Name AS VARCHAR) AS Brand_Name,
                CAST(Product_Group AS VARCHAR) AS Product_Group,
                CAST(Division AS VARCHAR) AS Division,
                CAST(Dosage_Form AS VARCHAR) AS Dosage_Form,
                CAST(Strength AS VARCHAR) AS Strength,
                CAST(Pack_Size AS VARCHAR) AS Pack_Size,
                CAST(Route_Admin AS VARCHAR) AS Route_Admin,
                CAST(Indications AS VARCHAR) AS Indications,
                CAST(Posology AS VARCHAR) AS Posology,
                CAST(Supplier_1 AS VARCHAR) AS Supplier_1,
                CAST(Supplier_2 AS VARCHAR) AS Supplier_2,
                CAST(Supplier_3 AS VARCHAR) AS Supplier_3,
                CAST(Supplier_4 AS VARCHAR) AS Supplier_4,
                CAST(Supplier_5 AS VARCHAR) AS Supplier_5,
                CAST(Primary_Supplier AS VARCHAR) AS Primary_Supplier,
                CAST(All_Suppliers AS VARCHAR[]) AS All_Suppliers
            FROM item_temp
        """)
        count = conn.execute("SELECT COUNT(*) FROM item_master").fetchone()[0]
        logger.log_table_info("item_master", count)
        del df
        gc.collect()
        
    except FileNotFoundError:
        logger.log("⚠️ Item Master file not found – creating from existing data", "WARNING")
        conn.execute("DROP TABLE IF EXISTS item_master")
        conn.execute("""
            CREATE TABLE item_master (
                Item_Code VARCHAR,
                Item_Name VARCHAR,
                Brand_Name VARCHAR,
                Product_Group VARCHAR,
                Division VARCHAR,
                Dosage_Form VARCHAR,
                Strength VARCHAR,
                Pack_Size VARCHAR,
                Route_Admin VARCHAR,
                Indications VARCHAR,
                Posology VARCHAR,
                Supplier_1 VARCHAR,
                Supplier_2 VARCHAR,
                Supplier_3 VARCHAR,
                Supplier_4 VARCHAR,
                Supplier_5 VARCHAR,
                Primary_Supplier VARCHAR,
                All_Suppliers VARCHAR[]
            )
        """)
        conn.execute("""
            INSERT INTO item_master (Item_Code, Item_Name)
            SELECT DISTINCT Item_Code, Item_Name
            FROM (
                SELECT Item_Code, Item_Name FROM sales_raw
                UNION
                SELECT Item_Code, Item_Name FROM import_purchase
                UNION
                SELECT Item_Code, Item_Name FROM local_purchase
                UNION
                SELECT Item_Number AS Item_Code, Item_Name FROM stock_data
            ) AS all_items
            WHERE Item_Code IS NOT NULL AND Item_Name IS NOT NULL
        """)
        count = conn.execute("SELECT COUNT(*) FROM item_master").fetchone()[0]
        logger.log_table_info("item_master (fallback)", count)
        
    except Exception as e:
        logger.log(f"Error creating item_master: {e}", "ERROR")
        traceback.print_exc()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS item_master (
                Item_Code VARCHAR, Item_Name VARCHAR, Brand_Name VARCHAR,
                Product_Group VARCHAR, Division VARCHAR, Dosage_Form VARCHAR,
                Strength VARCHAR, Pack_Size VARCHAR, Route_Admin VARCHAR,
                Indications VARCHAR, Posology VARCHAR,
                Supplier_1 VARCHAR, Supplier_2 VARCHAR, Supplier_3 VARCHAR,
                Supplier_4 VARCHAR, Supplier_5 VARCHAR,
                Primary_Supplier VARCHAR, All_Suppliers VARCHAR[]
            )
        """)
    
    logger.log("📍 Creating location_master...", "PROGRESS")
    loc_path = LOC_MASTER_PATH
    try:
        loc_df = pd.read_excel(loc_path, sheet_name="Sheet1")
        loc_df.columns = ["Branch", "Location"]
        loc_df["Branch"] = loc_df["Branch"].astype(str).str.strip()
        loc_df["Location"] = loc_df["Location"].astype(str).str.strip().str.title()
        conn.register('loc_temp', loc_df)
        conn.execute("DROP TABLE IF EXISTS location_master")
        conn.execute("CREATE TABLE location_master AS SELECT * FROM loc_temp")
        count = conn.execute("SELECT COUNT(*) FROM location_master").fetchone()[0]
        logger.log_table_info("location_master", count)
        del loc_df
        gc.collect()
    except Exception as e:
        logger.log(f"Error creating location_master: {e}", "ERROR")
        traceback.print_exc()
        conn.execute("CREATE TABLE IF NOT EXISTS location_master (Branch VARCHAR, Location VARCHAR)")

# ============================================================================
# AGGREGATED TABLES (unchanged)
# ============================================================================
def rebuild_aggregated_tables(conn):
    logger.log("🔄 Rebuilding aggregated tables from raw data...", "PROGRESS")
    
    conn.execute("DROP TABLE IF EXISTS aggregated_sales")
    conn.execute("""
        CREATE TABLE aggregated_sales AS
        SELECT 
            DATE_TRUNC('month', Sale_Date) as Month,
            Branch,
            Item_Code,
            SUM(Quantity) as Total_Qty,
            SUM(Amount_USD) as Total_Amount,
            COUNT(DISTINCT Invoice_No) as Transactions,
            COUNT(DISTINCT Customer_Id) as Unique_Customers,
            EXTRACT(YEAR FROM DATE_TRUNC('month', Sale_Date)) as Year,
            EXTRACT(MONTH FROM DATE_TRUNC('month', Sale_Date)) as Month_Num,
            EXTRACT(QUARTER FROM DATE_TRUNC('month', Sale_Date)) as Quarter
        FROM sales_raw
        WHERE Sale_Date IS NOT NULL AND Quantity > 0
        GROUP BY DATE_TRUNC('month', Sale_Date), Branch, Item_Code
    """)
    count = conn.execute("SELECT COUNT(*) FROM aggregated_sales").fetchone()[0]
    logger.log_table_info("aggregated_sales", count)
    
    conn.execute("DROP TABLE IF EXISTS aggregated_returns")
    conn.execute("""
        CREATE TABLE aggregated_returns AS
        SELECT 
            DATE_TRUNC('month', Return_Date) as Month,
            Branch,
            Item_Code,
            SUM(Return_Qty) as Total_Return_Qty,
            SUM(Amount_USD) as Total_Return_Amount,
            COUNT(DISTINCT Return_No) as Return_Transactions,
            EXTRACT(YEAR FROM DATE_TRUNC('month', Return_Date)) as Year,
            EXTRACT(MONTH FROM DATE_TRUNC('month', Return_Date)) as Month_Num,
            EXTRACT(QUARTER FROM DATE_TRUNC('month', Return_Date)) as Quarter
        FROM returns_raw
        WHERE Return_Date IS NOT NULL
        GROUP BY DATE_TRUNC('month', Return_Date), Branch, Item_Code
    """)
    count = conn.execute("SELECT COUNT(*) FROM aggregated_returns").fetchone()[0]
    logger.log_table_info("aggregated_returns", count)
    
    logger.log("📊 Creating materialized dashboard_data table...", "PROGRESS")
    try:
        conn.execute("DROP TABLE IF EXISTS dashboard_data")
    except:
        pass
    try:
        conn.execute("DROP VIEW IF EXISTS dashboard_data")
    except:
        pass
    
    conn.execute("""
        CREATE TABLE dashboard_data AS
        SELECT 
            COALESCE(s.Month, r.Month) as Month,
            COALESCE(s.Branch, r.Branch) as Branch,
            COALESCE(s.Item_Code, r.Item_Code) as Item_Code,
            im.Item_Name,
            im.Product_Group,
            im.Brand_Name,
            im.Division,
            lm.Location,
            COALESCE(s.Total_Qty, 0) as Qty_Sold,
            COALESCE(s.Total_Amount, 0) as Sales_Amount,
            COALESCE(s.Transactions, 0) as Sales_Transactions,
            COALESCE(s.Unique_Customers, 0) as Unique_Customers,
            COALESCE(r.Total_Return_Qty, 0) as Qty_Returned,
            COALESCE(r.Total_Return_Amount, 0) as Return_Amount,
            COALESCE(r.Return_Transactions, 0) as Return_Transactions,
            COALESCE(s.Total_Qty, 0) - COALESCE(r.Total_Return_Qty, 0) as Net_Qty,
            COALESCE(s.Total_Amount, 0) - COALESCE(r.Total_Return_Amount, 0) as Net_Amount,
            COALESCE(s.Transactions, 0) - COALESCE(r.Return_Transactions, 0) as Net_Transactions,
            COALESCE(s.Year, r.Year) as Year,
            COALESCE(s.Month_Num, r.Month_Num) as Month_Num,
            COALESCE(s.Quarter, r.Quarter) as Quarter,
            STRFTIME(COALESCE(s.Month, r.Month), '%Y-%m') as Month_Label
        FROM aggregated_sales s
        FULL OUTER JOIN aggregated_returns r 
            ON s.Month = r.Month AND LOWER(s.Branch) = LOWER(r.Branch) AND LOWER(s.Item_Code) = LOWER(r.Item_Code)
        LEFT JOIN item_master im ON LOWER(COALESCE(s.Item_Code, r.Item_Code)) = LOWER(im.Item_Code)
        LEFT JOIN location_master lm ON LOWER(COALESCE(s.Branch, r.Branch)) = LOWER(lm.Branch)
        WHERE COALESCE(s.Month, r.Month) IS NOT NULL
    """)
    count = conn.execute("SELECT COUNT(*) FROM dashboard_data").fetchone()[0]
    logger.log_table_info("dashboard_data", count)

# ============================================================================
# PRE-AGGREGATED SUMMARIES (unchanged)
# ============================================================================
def create_pre_aggregated_summaries(conn):
    logger.log("📊 Creating pre-aggregated summary tables...", "PROGRESS")
    
    conn.execute("DROP TABLE IF EXISTS branch_monthly_summary")
    conn.execute("""
        CREATE TABLE branch_monthly_summary AS
        SELECT 
            Month_Label, Year, Month_Num, Quarter, Branch, Location,
            SUM(Sales_Amount) as Sales_Amount,
            SUM(Qty_Sold) as Qty_Sold,
            SUM(Sales_Transactions) as Sales_Transactions,
            SUM(Return_Amount) as Return_Amount,
            SUM(Qty_Returned) as Qty_Returned,
            SUM(Return_Transactions) as Return_Transactions,
            SUM(Net_Amount) as Net_Amount,
            SUM(Net_Qty) as Net_Qty,
            SUM(Net_Transactions) as Net_Transactions,
            COUNT(DISTINCT Item_Code) as Unique_Products
        FROM dashboard_data
        GROUP BY Month_Label, Year, Month_Num, Quarter, Branch, Location
    """)
    count = conn.execute("SELECT COUNT(*) FROM branch_monthly_summary").fetchone()[0]
    logger.log_table_info("branch_monthly_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS item_monthly_summary")
    conn.execute("""
        CREATE TABLE item_monthly_summary AS
        SELECT 
            Month_Label, Year, Month_Num,
            Item_Code, Item_Name, Product_Group, Brand_Name, Division,
            SUM(Sales_Amount) as Sales_Amount,
            SUM(Qty_Sold) as Qty_Sold,
            SUM(Sales_Transactions) as Sales_Transactions,
            SUM(Return_Amount) as Return_Amount,
            SUM(Qty_Returned) as Qty_Returned,
            SUM(Return_Transactions) as Return_Transactions,
            SUM(Net_Amount) as Net_Amount,
            SUM(Net_Qty) as Net_Qty,
            SUM(Net_Transactions) as Net_Transactions
        FROM dashboard_data
        GROUP BY Month_Label, Year, Month_Num, Item_Code, Item_Name, Product_Group, Brand_Name, Division
    """)
    count = conn.execute("SELECT COUNT(*) FROM item_monthly_summary").fetchone()[0]
    logger.log_table_info("item_monthly_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS category_monthly_summary")
    conn.execute("""
        CREATE TABLE category_monthly_summary AS
        SELECT 
            Month_Label, Year, Month_Num, Product_Group,
            SUM(Sales_Amount) as Sales_Amount,
            SUM(Qty_Sold) as Qty_Sold,
            SUM(Sales_Transactions) as Sales_Transactions,
            SUM(Return_Amount) as Return_Amount,
            SUM(Qty_Returned) as Qty_Returned,
            SUM(Return_Transactions) as Return_Transactions,
            SUM(Net_Amount) as Net_Amount,
            SUM(Net_Qty) as Net_Qty,
            SUM(Net_Transactions) as Net_Transactions,
            COUNT(DISTINCT Item_Code) as Unique_Products
        FROM dashboard_data
        GROUP BY Month_Label, Year, Month_Num, Product_Group
    """)
    count = conn.execute("SELECT COUNT(*) FROM category_monthly_summary").fetchone()[0]
    logger.log_table_info("category_monthly_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS brand_monthly_summary")
    conn.execute("""
        CREATE TABLE brand_monthly_summary AS
        SELECT 
            Month_Label, Year, Month_Num, Brand_Name,
            SUM(Sales_Amount) as Sales_Amount,
            SUM(Qty_Sold) as Qty_Sold,
            SUM(Sales_Transactions) as Sales_Transactions,
            SUM(Return_Amount) as Return_Amount,
            SUM(Qty_Returned) as Qty_Returned,
            SUM(Return_Transactions) as Return_Transactions,
            SUM(Net_Amount) as Net_Amount,
            SUM(Net_Qty) as Net_Qty,
            SUM(Net_Transactions) as Net_Transactions,
            COUNT(DISTINCT Item_Code) as Unique_Products
        FROM dashboard_data
        WHERE Brand_Name IS NOT NULL AND Brand_Name != ''
        GROUP BY Month_Label, Year, Month_Num, Brand_Name
    """)
    count = conn.execute("SELECT COUNT(*) FROM brand_monthly_summary").fetchone()[0]
    logger.log_table_info("brand_monthly_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS division_monthly_summary")
    conn.execute("""
        CREATE TABLE division_monthly_summary AS
        SELECT 
            Month_Label, Year, Month_Num, Division,
            SUM(Sales_Amount) as Sales_Amount,
            SUM(Qty_Sold) as Qty_Sold,
            SUM(Sales_Transactions) as Sales_Transactions,
            SUM(Return_Amount) as Return_Amount,
            SUM(Qty_Returned) as Qty_Returned,
            SUM(Return_Transactions) as Return_Transactions,
            SUM(Net_Amount) as Net_Amount,
            SUM(Net_Qty) as Net_Qty,
            SUM(Net_Transactions) as Net_Transactions,
            COUNT(DISTINCT Item_Code) as Unique_Products
        FROM dashboard_data
        WHERE Division IS NOT NULL AND Division != ''
        GROUP BY Month_Label, Year, Month_Num, Division
    """)
    count = conn.execute("SELECT COUNT(*) FROM division_monthly_summary").fetchone()[0]
    logger.log_table_info("division_monthly_summary", count)

# ============================================================================
# INSTANT FILTER TABLES (unchanged)
# ============================================================================
def create_instant_filter_tables(conn):
    logger.log("📊 Creating INSTANT FILTER TABLES...", "PROGRESS")
    
    try:
        conn.execute("DROP TABLE IF EXISTS item_total_summary")
        conn.execute("""
            CREATE TABLE item_total_summary AS
            SELECT 
                Item_Code, Item_Name, Product_Group, Brand_Name, Division,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Total_Qty,
                SUM(Sales_Transactions) as Total_Transactions,
                SUM(Return_Amount) as Total_Returns,
                SUM(Qty_Returned) as Total_Qty_Returned,
                SUM(Return_Transactions) as Total_Return_Transactions,
                SUM(Net_Amount) as Total_Net,
                SUM(Net_Qty) as Total_Net_Qty,
                SUM(Net_Transactions) as Total_Net_Transactions,
                COUNT(DISTINCT Month_Label) as Active_Months
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Product_Group, Brand_Name, Division
        """)
        count = conn.execute("SELECT COUNT(*) FROM item_total_summary").fetchone()[0]
        logger.log_table_info("item_total_summary", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create item_total_summary: {e}", "ERROR")
        traceback.print_exc()
    
    try:
        conn.execute("DROP TABLE IF EXISTS branch_item_summary")
        conn.execute("""
            CREATE TABLE branch_item_summary AS
            SELECT 
                Item_Code, Item_Name, Branch, Location, Product_Group, Brand_Name, Division,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Total_Qty,
                SUM(Sales_Transactions) as Total_Transactions,
                SUM(Return_Amount) as Total_Returns,
                SUM(Qty_Returned) as Total_Qty_Returned,
                SUM(Return_Transactions) as Total_Return_Transactions,
                SUM(Net_Amount) as Total_Net,
                SUM(Net_Qty) as Total_Net_Qty,
                SUM(Net_Transactions) as Total_Net_Transactions,
                COUNT(DISTINCT Month_Label) as Active_Months
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Branch, Location, Product_Group, Brand_Name, Division
        """)
        count = conn.execute("SELECT COUNT(*) FROM branch_item_summary").fetchone()[0]
        logger.log_table_info("branch_item_summary", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create branch_item_summary: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# BRANCH-ITEM MONTHLY SUMMARY (unchanged)
# ============================================================================
def create_branch_item_monthly_summary(conn):
    logger.log("📊 Creating branch_item_monthly_summary...", "PROGRESS")
    try:
        conn.execute("DROP TABLE IF EXISTS branch_item_monthly_summary")
        conn.execute("""
            CREATE TABLE branch_item_monthly_summary AS
            SELECT 
                Branch, Location, Item_Code, Item_Name, Product_Group, Brand_Name, Division,
                Month_Label, Year, Month_Num,
                SUM(Sales_Amount) as Sales_Amount,
                SUM(Qty_Sold) as Qty_Sold,
                SUM(Sales_Transactions) as Sales_Transactions,
                SUM(Return_Amount) as Return_Amount,
                SUM(Qty_Returned) as Qty_Returned,
                SUM(Return_Transactions) as Return_Transactions,
                SUM(Net_Amount) as Net_Amount,
                SUM(Net_Qty) as Net_Qty,
                SUM(Net_Transactions) as Net_Transactions
            FROM dashboard_data
            GROUP BY Branch, Location, Item_Code, Item_Name, Product_Group, Brand_Name, Division,
                     Month_Label, Year, Month_Num
        """)
        count = conn.execute("SELECT COUNT(*) FROM branch_item_monthly_summary").fetchone()[0]
        logger.log_table_info("branch_item_monthly_summary", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create branch_item_monthly_summary: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# DECISION SUPPORT TABLES (unchanged)
# ============================================================================
def create_decision_support_tables(conn):
    logger.log("📊 Creating decision support tables...", "PROGRESS")
    
    try:
        conn.execute("DROP TABLE IF EXISTS item_abc_classification")
        conn.execute("""
            CREATE TABLE item_abc_classification AS
            WITH item_totals AS (
                SELECT 
                    Item_Code, Item_Name, Product_Group,
                    SUM(Sales_Amount) as Total_Sales,
                    SUM(Qty_Sold) as Total_Qty,
                    SUM(Sales_Transactions) as Total_Transactions
                FROM dashboard_data
                GROUP BY Item_Code, Item_Name, Product_Group
            ),
            ranked AS (
                SELECT *,
                    SUM(Total_Sales) OVER (ORDER BY Total_Sales DESC) as cum_sales,
                    SUM(Total_Sales) OVER () as total_all
                FROM item_totals
            )
            SELECT 
                Item_Code, Item_Name, Product_Group,
                Total_Sales, Total_Qty, Total_Transactions,
                ROUND(cum_sales / total_all * 100, 2) as cum_pct,
                CASE 
                    WHEN cum_sales / total_all <= 0.80 THEN 'A'
                    WHEN cum_sales / total_all <= 0.95 THEN 'B'
                    ELSE 'C'
                END as ABC_Class
            FROM ranked
            ORDER BY Total_Sales DESC
        """)
        count = conn.execute("SELECT COUNT(*) FROM item_abc_classification").fetchone()[0]
        logger.log_table_info("item_abc_classification", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create item_abc_classification: {e}", "ERROR")
        traceback.print_exc()
    
    try:
        conn.execute("DROP TABLE IF EXISTS item_performance_ranking")
        conn.execute("""
            CREATE TABLE item_performance_ranking AS
            SELECT 
                Item_Code, Item_Name, Product_Group, Brand_Name, Division,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Total_Qty,
                SUM(Sales_Transactions) as Total_Transactions,
                RANK() OVER (ORDER BY SUM(Sales_Amount) DESC) as Sales_Rank,
                RANK() OVER (ORDER BY SUM(Qty_Sold) DESC) as Qty_Rank,
                RANK() OVER (ORDER BY SUM(Sales_Transactions) DESC) as Trans_Rank
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Product_Group, Brand_Name, Division
            ORDER BY Sales_Rank
        """)
        count = conn.execute("SELECT COUNT(*) FROM item_performance_ranking").fetchone()[0]
        logger.log_table_info("item_performance_ranking", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create item_performance_ranking: {e}", "ERROR")
        traceback.print_exc()
    
    try:
        conn.execute("DROP TABLE IF EXISTS product_group_performance")
        conn.execute("""
            CREATE TABLE product_group_performance AS
            SELECT 
                Product_Group,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Total_Qty,
                SUM(Sales_Transactions) as Total_Transactions,
                SUM(Return_Amount) as Total_Returns,
                SUM(Net_Amount) as Total_Net,
                COUNT(DISTINCT Item_Code) as Unique_Products,
                AVG(Sales_Amount) as Avg_Sales_Per_Item
            FROM dashboard_data
            GROUP BY Product_Group
            ORDER BY Total_Sales DESC
        """)
        count = conn.execute("SELECT COUNT(*) FROM product_group_performance").fetchone()[0]
        logger.log_table_info("product_group_performance", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create product_group_performance: {e}", "ERROR")
        traceback.print_exc()
    
    try:
        conn.execute("DROP TABLE IF EXISTS brand_performance")
        conn.execute("""
            CREATE TABLE brand_performance AS
            SELECT 
                Brand_Name,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Total_Qty,
                SUM(Sales_Transactions) as Total_Transactions,
                COUNT(DISTINCT Item_Code) as Unique_Products
            FROM dashboard_data
            WHERE Brand_Name IS NOT NULL AND Brand_Name != ''
            GROUP BY Brand_Name
            ORDER BY Total_Sales DESC
        """)
        count = conn.execute("SELECT COUNT(*) FROM brand_performance").fetchone()[0]
        logger.log_table_info("brand_performance", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create brand_performance: {e}", "ERROR")
        traceback.print_exc()
    
    try:
        conn.execute("DROP TABLE IF EXISTS division_performance")
        conn.execute("""
            CREATE TABLE division_performance AS
            SELECT 
                Division,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Total_Qty,
                SUM(Sales_Transactions) as Total_Transactions,
                COUNT(DISTINCT Item_Code) as Unique_Products
            FROM dashboard_data
            WHERE Division IS NOT NULL AND Division != ''
            GROUP BY Division
            ORDER BY Total_Sales DESC
        """)
        count = conn.execute("SELECT COUNT(*) FROM division_performance").fetchone()[0]
        logger.log_table_info("division_performance", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create division_performance: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# PIVOT TABLES (unchanged)
# ============================================================================
def create_all_pivot_tables(conn):
    logger.log("📊 Creating ALL pivot tables...", "PROGRESS")
    
    pivot_configs = [
        ('sales', 'Sales_Amount', 'Qty_Sold', 'Sales_Transactions'),
        ('returns', 'Return_Amount', 'Qty_Returned', 'Return_Transactions'),
        ('net_sales', 'Net_Amount', 'Net_Qty', 'Net_Transactions')
    ]
    
    for prefix, val_col, qty_col, trans_col in pivot_configs:
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_monthly_pivot_value")
        conn.execute(f"""
            CREATE TABLE {prefix}_monthly_pivot_value AS
            SELECT Item_Code, Item_Name, Month_Label, SUM({val_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Month_Label
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_monthly_pivot_value").fetchone()[0]
        logger.log_table_info(f"{prefix}_monthly_pivot_value", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_monthly_pivot_qty")
        conn.execute(f"""
            CREATE TABLE {prefix}_monthly_pivot_qty AS
            SELECT Item_Code, Item_Name, Month_Label, SUM({qty_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Month_Label
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_monthly_pivot_qty").fetchone()[0]
        logger.log_table_info(f"{prefix}_monthly_pivot_qty", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_monthly_pivot_trans")
        conn.execute(f"""
            CREATE TABLE {prefix}_monthly_pivot_trans AS
            SELECT Item_Code, Item_Name, Month_Label, SUM({trans_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Month_Label
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_monthly_pivot_trans").fetchone()[0]
        logger.log_table_info(f"{prefix}_monthly_pivot_trans", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_quarterly_pivot_value")
        conn.execute(f"""
            CREATE TABLE {prefix}_quarterly_pivot_value AS
            SELECT Item_Code, Item_Name, CONCAT(Year, '-Q', Quarter) as Quarter_Label, SUM({val_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Year, Quarter
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_quarterly_pivot_value").fetchone()[0]
        logger.log_table_info(f"{prefix}_quarterly_pivot_value", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_quarterly_pivot_qty")
        conn.execute(f"""
            CREATE TABLE {prefix}_quarterly_pivot_qty AS
            SELECT Item_Code, Item_Name, CONCAT(Year, '-Q', Quarter) as Quarter_Label, SUM({qty_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Year, Quarter
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_quarterly_pivot_qty").fetchone()[0]
        logger.log_table_info(f"{prefix}_quarterly_pivot_qty", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_quarterly_pivot_trans")
        conn.execute(f"""
            CREATE TABLE {prefix}_quarterly_pivot_trans AS
            SELECT Item_Code, Item_Name, CONCAT(Year, '-Q', Quarter) as Quarter_Label, SUM({trans_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Year, Quarter
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_quarterly_pivot_trans").fetchone()[0]
        logger.log_table_info(f"{prefix}_quarterly_pivot_trans", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_yearly_pivot_value")
        conn.execute(f"""
            CREATE TABLE {prefix}_yearly_pivot_value AS
            SELECT Item_Code, Item_Name, Year, SUM({val_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Year
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_yearly_pivot_value").fetchone()[0]
        logger.log_table_info(f"{prefix}_yearly_pivot_value", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_yearly_pivot_qty")
        conn.execute(f"""
            CREATE TABLE {prefix}_yearly_pivot_qty AS
            SELECT Item_Code, Item_Name, Year, SUM({qty_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Year
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_yearly_pivot_qty").fetchone()[0]
        logger.log_table_info(f"{prefix}_yearly_pivot_qty", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_yearly_pivot_trans")
        conn.execute(f"""
            CREATE TABLE {prefix}_yearly_pivot_trans AS
            SELECT Item_Code, Item_Name, Year, SUM({trans_col}) as Value
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name, Year
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_yearly_pivot_trans").fetchone()[0]
        logger.log_table_info(f"{prefix}_yearly_pivot_trans", count)
    
    current_year = datetime.now().year
    prev_year = current_year - 1
    
    for prefix, val_col, qty_col, trans_col in pivot_configs:
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_yoy_pivot_value")
        conn.execute(f"""
            CREATE TABLE {prefix}_yoy_pivot_value AS
            SELECT 
                Item_Code, Item_Name,
                SUM(CASE WHEN Year = {current_year} THEN {val_col} ELSE 0 END) as Current_Year,
                SUM(CASE WHEN Year = {prev_year} THEN {val_col} ELSE 0 END) as Previous_Year,
                CASE 
                    WHEN SUM(CASE WHEN Year = {prev_year} THEN {val_col} ELSE 0 END) > 0 
                    THEN ((SUM(CASE WHEN Year = {current_year} THEN {val_col} ELSE 0 END) - 
                           SUM(CASE WHEN Year = {prev_year} THEN {val_col} ELSE 0 END)) / 
                           SUM(CASE WHEN Year = {prev_year} THEN {val_col} ELSE 0 END)) * 100
                    ELSE NULL
                END as YoY_Growth_Pct
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_yoy_pivot_value").fetchone()[0]
        logger.log_table_info(f"{prefix}_yoy_pivot_value", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_yoy_pivot_qty")
        conn.execute(f"""
            CREATE TABLE {prefix}_yoy_pivot_qty AS
            SELECT 
                Item_Code, Item_Name,
                SUM(CASE WHEN Year = {current_year} THEN {qty_col} ELSE 0 END) as Current_Year,
                SUM(CASE WHEN Year = {prev_year} THEN {qty_col} ELSE 0 END) as Previous_Year,
                CASE 
                    WHEN SUM(CASE WHEN Year = {prev_year} THEN {qty_col} ELSE 0 END) > 0 
                    THEN ((SUM(CASE WHEN Year = {current_year} THEN {qty_col} ELSE 0 END) - 
                           SUM(CASE WHEN Year = {prev_year} THEN {qty_col} ELSE 0 END)) / 
                           SUM(CASE WHEN Year = {prev_year} THEN {qty_col} ELSE 0 END)) * 100
                    ELSE NULL
                END as YoY_Growth_Pct
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_yoy_pivot_qty").fetchone()[0]
        logger.log_table_info(f"{prefix}_yoy_pivot_qty", count)
        
        conn.execute(f"DROP TABLE IF EXISTS {prefix}_yoy_pivot_trans")
        conn.execute(f"""
            CREATE TABLE {prefix}_yoy_pivot_trans AS
            SELECT 
                Item_Code, Item_Name,
                SUM(CASE WHEN Year = {current_year} THEN {trans_col} ELSE 0 END) as Current_Year,
                SUM(CASE WHEN Year = {prev_year} THEN {trans_col} ELSE 0 END) as Previous_Year,
                CASE 
                    WHEN SUM(CASE WHEN Year = {prev_year} THEN {trans_col} ELSE 0 END) > 0 
                    THEN ((SUM(CASE WHEN Year = {current_year} THEN {trans_col} ELSE 0 END) - 
                           SUM(CASE WHEN Year = {prev_year} THEN {trans_col} ELSE 0 END)) / 
                           SUM(CASE WHEN Year = {prev_year} THEN {trans_col} ELSE 0 END)) * 100
                    ELSE NULL
                END as YoY_Growth_Pct
            FROM dashboard_data
            GROUP BY Item_Code, Item_Name
        """)
        count = conn.execute(f"SELECT COUNT(*) FROM {prefix}_yoy_pivot_trans").fetchone()[0]
        logger.log_table_info(f"{prefix}_yoy_pivot_trans", count)
    
    conn.execute("DROP TABLE IF EXISTS monthly_summary")
    conn.execute("""
        CREATE TABLE monthly_summary AS
        SELECT 
            Month_Label, Year, Month_Num, Quarter,
            SUM(Sales_Amount) as Total_Sales,
            SUM(Qty_Sold) as Total_Qty,
            SUM(Sales_Transactions) as Total_Transactions,
            SUM(Return_Amount) as Total_Returns,
            SUM(Qty_Returned) as Total_Return_Qty,
            SUM(Return_Transactions) as Total_Return_Transactions,
            SUM(Net_Amount) as Total_Net,
            SUM(Net_Qty) as Total_Net_Qty,
            SUM(Net_Transactions) as Total_Net_Transactions,
            COUNT(DISTINCT Item_Code) as Active_Products,
            COUNT(DISTINCT Branch) as Active_Branches
        FROM dashboard_data
        GROUP BY Month_Label, Year, Month_Num, Quarter
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM monthly_summary").fetchone()[0]
    logger.log_table_info("monthly_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS yearly_summary")
    conn.execute("""
        CREATE TABLE yearly_summary AS
        SELECT 
            Year,
            SUM(Sales_Amount) as Total_Sales,
            SUM(Qty_Sold) as Total_Qty,
            SUM(Sales_Transactions) as Total_Transactions,
            SUM(Return_Amount) as Total_Returns,
            SUM(Qty_Returned) as Total_Return_Qty,
            SUM(Return_Transactions) as Total_Return_Transactions,
            SUM(Net_Amount) as Total_Net,
            SUM(Net_Qty) as Total_Net_Qty,
            SUM(Net_Transactions) as Total_Net_Transactions
        FROM dashboard_data
        GROUP BY Year
        ORDER BY Year DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM yearly_summary").fetchone()[0]
    logger.log_table_info("yearly_summary", count)

# ============================================================================
# DEMAND PLANNING TABLES (unchanged)
# ============================================================================
def create_demand_planning_tables(conn):
    logger.log("📊 Creating DEMAND PLANNING tables...", "PROGRESS")
    
    conn.execute("DROP TABLE IF EXISTS monthly_demand")
    conn.execute("""
        CREATE TABLE monthly_demand AS
        SELECT 
            Month_Label, Year, Month_Num,
            SUM(Sales_Amount) as Total_Sales,
            SUM(Qty_Sold) as Total_Qty,
            SUM(Sales_Transactions) as Total_Transactions,
            COUNT(DISTINCT Item_Code) as Active_Products,
            COUNT(DISTINCT Branch) as Active_Branches,
            AVG(Sales_Amount) as Avg_Sales,
            STDDEV(Sales_Amount) as StdDev_Sales
        FROM dashboard_data
        GROUP BY Month_Label, Year, Month_Num
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM monthly_demand").fetchone()[0]
    logger.log_table_info("monthly_demand", count)
    
    conn.execute("DROP TABLE IF EXISTS moving_averages")
    conn.execute("""
        CREATE TABLE moving_averages AS
        SELECT 
            Month_Label, Year, Month_Num, Total_Sales, Total_Qty,
            AVG(Total_Sales) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as MA_3,
            AVG(Total_Sales) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as MA_6,
            AVG(Total_Sales) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) as MA_12,
            AVG(Total_Qty) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as MA_Qty_3,
            AVG(Total_Qty) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as MA_Qty_6,
            AVG(Total_Qty) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) as MA_Qty_12
        FROM monthly_demand
    """)
    count = conn.execute("SELECT COUNT(*) FROM moving_averages").fetchone()[0]
    logger.log_table_info("moving_averages", count)
    
    conn.execute("DROP TABLE IF EXISTS monthly_growth")
    conn.execute("""
        CREATE TABLE monthly_growth AS
        SELECT 
            Month_Label, Year, Month_Num, Total_Sales,
            LAG(Total_Sales, 1) OVER (ORDER BY Year, Month_Num) as Prev_Month_Sales,
            LAG(Total_Sales, 12) OVER (ORDER BY Year, Month_Num) as Prev_Year_Sales,
            CASE 
                WHEN LAG(Total_Sales, 1) OVER (ORDER BY Year, Month_Num) > 0 
                THEN ((Total_Sales - LAG(Total_Sales, 1) OVER (ORDER BY Year, Month_Num)) / 
                      LAG(Total_Sales, 1) OVER (ORDER BY Year, Month_Num)) * 100
                ELSE NULL
            END as MoM_Growth_Pct,
            CASE 
                WHEN LAG(Total_Sales, 12) OVER (ORDER BY Year, Month_Num) > 0 
                THEN ((Total_Sales - LAG(Total_Sales, 12) OVER (ORDER BY Year, Month_Num)) / 
                      LAG(Total_Sales, 12) OVER (ORDER BY Year, Month_Num)) * 100
                ELSE NULL
            END as YoY_Growth_Pct
        FROM monthly_demand
    """)
    count = conn.execute("SELECT COUNT(*) FROM monthly_growth").fetchone()[0]
    logger.log_table_info("monthly_growth", count)
    
    conn.execute("DROP TABLE IF EXISTS seasonality_index")
    conn.execute("""
        CREATE TABLE seasonality_index AS
        WITH monthly_avg AS (
            SELECT Month_Num, AVG(Total_Sales) as Avg_Sales_By_Month
            FROM monthly_demand
            GROUP BY Month_Num
        ),
        overall_avg AS (
            SELECT AVG(Total_Sales) as Overall_Avg
            FROM monthly_demand
        )
        SELECT 
            ma.Month_Num,
            ma.Avg_Sales_By_Month,
            oa.Overall_Avg,
            ROUND((ma.Avg_Sales_By_Month / NULLIF(oa.Overall_Avg, 0)) * 100, 2) as Seasonality_Index,
            CASE 
                WHEN ma.Avg_Sales_By_Month / NULLIF(oa.Overall_Avg, 0) > 1.2 THEN 'PEAK'
                WHEN ma.Avg_Sales_By_Month / NULLIF(oa.Overall_Avg, 0) < 0.8 THEN 'OFF_PEAK'
                ELSE 'NORMAL'
            END as Seasonality_Type
        FROM monthly_avg ma
        CROSS JOIN overall_avg oa
        ORDER BY ma.Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM seasonality_index").fetchone()[0]
    logger.log_table_info("seasonality_index", count)
    
    conn.execute("DROP TABLE IF EXISTS demand_forecast")
    conn.execute("""
        CREATE TABLE demand_forecast AS
        WITH forecast_data AS (
            SELECT 
                Month_Label, Year, Month_Num, Total_Sales,
                AVG(Total_Sales) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as MA_3,
                AVG(Total_Sales) OVER (ORDER BY Year, Month_Num ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as MA_6,
                ROW_NUMBER() OVER (ORDER BY Year DESC, Month_Num DESC) as Recency
            FROM monthly_demand
        )
        SELECT 
            Month_Label, Year, Month_Num,
            Total_Sales as Actual_Sales,
            MA_3 as Forecast_MA_3,
            MA_6 as Forecast_MA_6,
            ABS(Total_Sales - MA_3) / NULLIF(MA_3, 0) * 100 as MAPE_MA_3,
            ABS(Total_Sales - MA_6) / NULLIF(MA_6, 0) * 100 as MAPE_MA_6
        FROM forecast_data
    """)
    count = conn.execute("SELECT COUNT(*) FROM demand_forecast").fetchone()[0]
    logger.log_table_info("demand_forecast", count)
    
    conn.execute("DROP TABLE IF EXISTS forecast_accuracy")
    conn.execute("""
        CREATE TABLE forecast_accuracy AS
        SELECT 
            AVG(MAPE_MA_3) as MAPE_MA_3,
            AVG(MAPE_MA_6) as MAPE_MA_6,
            AVG(ABS(Actual_Sales - Forecast_MA_3)) as MAE_MA_3,
            AVG(ABS(Actual_Sales - Forecast_MA_6)) as MAE_MA_6,
            SQRT(AVG(POWER(Actual_Sales - Forecast_MA_3, 2))) as RMSE_MA_3,
            SQRT(AVG(POWER(Actual_Sales - Forecast_MA_6, 2))) as RMSE_MA_6,
            COUNT(*) as Forecast_Periods
        FROM demand_forecast
        WHERE Forecast_MA_3 IS NOT NULL AND Forecast_MA_6 IS NOT NULL
    """)
    count = conn.execute("SELECT COUNT(*) FROM forecast_accuracy").fetchone()[0]
    logger.log_table_info("forecast_accuracy", count)
    
    conn.execute("DROP TABLE IF EXISTS item_demand")
    conn.execute("""
        CREATE TABLE item_demand AS
        SELECT 
            Item_Code, Item_Name, Product_Group,
            SUM(Sales_Amount) as Total_Revenue,
            SUM(Qty_Sold) as Total_Qty,
            AVG(Sales_Amount) as Avg_Revenue,
            STDDEV(Sales_Amount) as Revenue_StdDev,
            COUNT(DISTINCT Month_Label) as Active_Months,
            MAX(Month_Label) as Last_Sale_Month,
            MIN(Month_Label) as First_Sale_Month,
            AVG(Sales_Amount) / NULLIF(STDDEV(Sales_Amount), 0) as Demand_Stability_Index
        FROM dashboard_data
        GROUP BY Item_Code, Item_Name, Product_Group
    """)
    count = conn.execute("SELECT COUNT(*) FROM item_demand").fetchone()[0]
    logger.log_table_info("item_demand", count)
    
    conn.execute("DROP TABLE IF EXISTS branch_demand")
    conn.execute("""
        CREATE TABLE branch_demand AS
        SELECT 
            Branch, Location,
            SUM(Sales_Amount) as Total_Revenue,
            SUM(Qty_Sold) as Total_Qty,
            AVG(Sales_Amount) as Avg_Revenue,
            STDDEV(Sales_Amount) as Revenue_StdDev,
            COUNT(DISTINCT Month_Label) as Active_Months,
            COUNT(DISTINCT Item_Code) as Unique_Products,
            AVG(Sales_Amount) / NULLIF(STDDEV(Sales_Amount), 0) as Demand_Stability_Index
        FROM dashboard_data
        GROUP BY Branch, Location
    """)
    count = conn.execute("SELECT COUNT(*) FROM branch_demand").fetchone()[0]
    logger.log_table_info("branch_demand", count)
    
    conn.execute("DROP TABLE IF EXISTS demand_patterns")
    conn.execute("""
        CREATE TABLE demand_patterns AS
        SELECT 
            Item_Code, Item_Name, Product_Group,
            Total_Revenue, Total_Qty, Active_Months, Demand_Stability_Index,
            CASE 
                WHEN Demand_Stability_Index > 0.5 THEN 'STABLE'
                WHEN Demand_Stability_Index > 0.2 THEN 'VARIABLE'
                ELSE 'VOLATILE'
            END as Demand_Stability,
            CASE 
                WHEN Total_Revenue > (SELECT AVG(Total_Revenue) FROM item_demand) 
                     AND Demand_Stability_Index > 0.5 THEN 'HIGH_VALUE_STABLE'
                WHEN Total_Revenue > (SELECT AVG(Total_Revenue) FROM item_demand) 
                     AND Demand_Stability_Index <= 0.5 THEN 'HIGH_VALUE_VARIABLE'
                WHEN Total_Revenue <= (SELECT AVG(Total_Revenue) FROM item_demand) 
                     AND Demand_Stability_Index > 0.5 THEN 'LOW_VALUE_STABLE'
                ELSE 'LOW_VALUE_VARIABLE'
            END as Demand_Classification
        FROM item_demand
    """)
    count = conn.execute("SELECT COUNT(*) FROM demand_patterns").fetchone()[0]
    logger.log_table_info("demand_patterns", count)
    
    conn.execute("DROP TABLE IF EXISTS seasonal_demand_by_product")
    conn.execute("""
        CREATE TABLE seasonal_demand_by_product AS
        SELECT 
            Item_Code, Item_Name,
            EXTRACT(MONTH FROM Month) as Month_Num,
            SUM(Sales_Amount) as Monthly_Revenue,
            SUM(Sales_Amount) / NULLIF(SUM(SUM(Sales_Amount)) OVER (PARTITION BY Item_Code), 0) * 100 as Revenue_Share_Pct
        FROM dashboard_data
        GROUP BY Item_Code, Item_Name, EXTRACT(MONTH FROM Month)
    """)
    count = conn.execute("SELECT COUNT(*) FROM seasonal_demand_by_product").fetchone()[0]
    logger.log_table_info("seasonal_demand_by_product", count)
    
    conn.execute("DROP TABLE IF EXISTS forecast_summary")
    conn.execute("""
        CREATE TABLE forecast_summary AS
        SELECT 'MA_3' as Forecast_Method, MAPE_MA_3 as Avg_MAPE, MAE_MA_3 as Avg_MAE,
               RMSE_MA_3 as RMSE, Forecast_Periods as Periods,
               '3-Month Moving Average' as Description
        FROM forecast_accuracy
        UNION ALL
        SELECT 'MA_6' as Forecast_Method, MAPE_MA_6 as Avg_MAPE, MAE_MA_6 as Avg_MAE,
               RMSE_MA_6 as RMSE, Forecast_Periods as Periods,
               '6-Month Moving Average' as Description
        FROM forecast_accuracy
    """)
    count = conn.execute("SELECT COUNT(*) FROM forecast_summary").fetchone()[0]
    logger.log_table_info("forecast_summary", count)

# ============================================================================
# STOCK TABLES (unchanged)
# ============================================================================
def create_stock_tables(conn, stock_df):
    if stock_df is None or stock_df.empty:
        logger.log("No stock data available", "WARNING")
        return
    
    logger.log("📊 Creating STOCK tables...", "PROGRESS")
    
    conn.register('stock_temp', stock_df)
    conn.execute("DROP TABLE IF EXISTS stock_data")
    conn.execute("CREATE TABLE stock_data AS SELECT * FROM stock_temp")
    count = conn.execute("SELECT COUNT(*) FROM stock_data").fetchone()[0]
    logger.log_table_info("stock_data", count)
    
    stock_cols = [c for c in stock_df.columns 
                 if c not in ['Item_Name', 'Item_Number', 'File_Location', 'Month_End_Date']
                 and c.upper().endswith('_STOCK')
                 and 'GRAND' not in c.upper()
                 and 'EXTRA' not in c.upper()]
    
    if stock_cols:
        select_parts = []
        for col in stock_cols:
            loc_name = col.replace('_STOCK', '')
            value_col = f"{loc_name}_STOCKVALUE"
            if value_col in stock_df.columns:
                select_parts.append(f"""
                    SELECT Item_Name, Item_Number, '{loc_name}' as Branch_Location,
                           "{col}" as Stock_Qty, "{value_col}" as Stock_Value,
                           File_Location, Month_End_Date
                    FROM stock_data WHERE "{col}" IS NOT NULL AND "{col}" > 0
                """)
        if select_parts:
            unpivot_query = " UNION ALL ".join(select_parts)
            conn.execute("DROP TABLE IF EXISTS stock_unpivoted")
            conn.execute(f"CREATE TABLE stock_unpivoted AS SELECT * FROM ({unpivot_query})")
            count = conn.execute("SELECT COUNT(*) FROM stock_unpivoted").fetchone()[0]
            logger.log_table_info("stock_unpivoted", count)
        else:
            conn.execute("DROP TABLE IF EXISTS stock_unpivoted")
            conn.execute("""
                CREATE TABLE stock_unpivoted (
                    Item_Name VARCHAR, Item_Number VARCHAR, Branch_Location VARCHAR,
                    Stock_Qty DOUBLE, Stock_Value DOUBLE, File_Location VARCHAR, Month_End_Date DATE
                )
            """)
            logger.log_table_info("stock_unpivoted", 0)
    else:
        conn.execute("DROP TABLE IF EXISTS stock_unpivoted")
        conn.execute("""
            CREATE TABLE stock_unpivoted (
                Item_Name VARCHAR, Item_Number VARCHAR, Branch_Location VARCHAR,
                Stock_Qty DOUBLE, Stock_Value DOUBLE, File_Location VARCHAR, Month_End_Date DATE
            )
        """)
        logger.log_table_info("stock_unpivoted", 0)
    
    conn.execute("DROP TABLE IF EXISTS stock_by_location")
    conn.execute("""
        CREATE TABLE stock_by_location AS
        SELECT 
            Branch_Location,
            COUNT(DISTINCT Item_Name) as Unique_Items,
            SUM(Stock_Qty) as Total_Stock_Qty,
            SUM(Stock_Value) as Total_Stock_Value,
            AVG(Stock_Qty) as Avg_Stock_Qty,
            MAX(Stock_Qty) as Max_Stock_Qty,
            MIN(Stock_Qty) as Min_Stock_Qty,
            MAX(Month_End_Date) as Latest_Stock_Date,
            File_Location
        FROM stock_unpivoted
        WHERE Branch_Location IS NOT NULL AND Branch_Location != ''
        GROUP BY Branch_Location, File_Location
        ORDER BY Total_Stock_Qty DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_by_location").fetchone()[0]
    logger.log_table_info("stock_by_location", count)
    
    conn.execute("DROP TABLE IF EXISTS stock_by_file_location")
    conn.execute("""
        CREATE TABLE stock_by_file_location AS
        SELECT 
            File_Location,
            COUNT(DISTINCT Branch_Location) as Branches,
            COUNT(DISTINCT Item_Name) as Unique_Items,
            SUM(Stock_Qty) as Total_Stock_Qty,
            SUM(Stock_Value) as Total_Stock_Value,
            AVG(Stock_Qty) as Avg_Stock_Qty,
            MIN(Month_End_Date) as First_Stock_Date,
            MAX(Month_End_Date) as Latest_Stock_Date
        FROM stock_unpivoted
        WHERE File_Location IS NOT NULL AND File_Location != ''
        GROUP BY File_Location
        ORDER BY Total_Stock_Qty DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_by_file_location").fetchone()[0]
    logger.log_table_info("stock_by_file_location", count)
    
    conn.execute("DROP TABLE IF EXISTS stock_by_month")
    conn.execute("""
        CREATE TABLE stock_by_month AS
        SELECT 
            DATE_TRUNC('month', Month_End_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Month_End_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Month_End_Date) as Year,
            EXTRACT(MONTH FROM Month_End_Date) as Month_Num,
            File_Location,
            COUNT(DISTINCT Item_Name) as Unique_Items,
            COUNT(DISTINCT Branch_Location) as Active_Locations,
            SUM(Stock_Qty) as Total_Stock_Qty,
            SUM(Stock_Value) as Total_Stock_Value,
            AVG(Stock_Qty) as Avg_Stock_Qty
        FROM stock_unpivoted
        WHERE Branch_Location IS NOT NULL AND Branch_Location != ''
        GROUP BY DATE_TRUNC('month', Month_End_Date), STRFTIME(DATE_TRUNC('month', Month_End_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Month_End_Date), EXTRACT(MONTH FROM Month_End_Date), File_Location
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_by_month").fetchone()[0]
    logger.log_table_info("stock_by_month", count)
    
    conn.execute("DROP TABLE IF EXISTS stock_by_quarter")
    conn.execute("""
        CREATE TABLE stock_by_quarter AS
        SELECT 
            CONCAT(Year, '-Q', Quarter) as Quarter_Label, Year, Quarter, File_Location,
            COUNT(DISTINCT Item_Name) as Unique_Items,
            COUNT(DISTINCT Branch_Location) as Active_Locations,
            SUM(Stock_Qty) as Total_Stock_Qty,
            SUM(Stock_Value) as Total_Stock_Value,
            AVG(Stock_Qty) as Avg_Stock_Qty
        FROM (            
            SELECT *, EXTRACT(YEAR FROM Month_End_Date) as Year, EXTRACT(QUARTER FROM Month_End_Date) as Quarter
            FROM stock_unpivoted
            WHERE Branch_Location IS NOT NULL AND Branch_Location != ''
        )
        GROUP BY Year, Quarter, File_Location
        ORDER BY Year DESC, Quarter DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_by_quarter").fetchone()[0]
    logger.log_table_info("stock_by_quarter", count)
    
    conn.execute("DROP TABLE IF EXISTS stock_by_year")
    conn.execute("""
        CREATE TABLE stock_by_year AS
        SELECT 
            EXTRACT(YEAR FROM Month_End_Date) as Year, File_Location,
            COUNT(DISTINCT Item_Name) as Unique_Items,
            COUNT(DISTINCT Branch_Location) as Active_Locations,
            SUM(Stock_Qty) as Total_Stock_Qty,
            SUM(Stock_Value) as Total_Stock_Value,
            AVG(Stock_Qty) as Avg_Stock_Qty
        FROM stock_unpivoted
        WHERE Branch_Location IS NOT NULL AND Branch_Location != ''
        GROUP BY EXTRACT(YEAR FROM Month_End_Date), File_Location
        ORDER BY Year DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_by_year").fetchone()[0]
    logger.log_table_info("stock_by_year", count)
    
    conn.execute("DROP TABLE IF EXISTS stock_out_analysis")
    conn.execute("""
        CREATE TABLE stock_out_analysis AS
        WITH latest_date AS (
            SELECT MAX(Month_End_Date) as max_date FROM stock_unpivoted
        ),
        active_combos AS (
            SELECT DISTINCT Item_Code, Branch
            FROM dashboard_data
            WHERE Month >= (SELECT max_date FROM latest_date) - INTERVAL '3 months'
        ),
        latest_stock AS (
            SELECT 
                Item_Number,
                Branch_Location,
                SUM(Stock_Qty) as Current_Stock
            FROM stock_unpivoted
            WHERE Month_End_Date = (SELECT max_date FROM latest_date)
            GROUP BY Item_Number, Branch_Location
        )
        SELECT 
            ac.Item_Code as Item_Number,
            ac.Branch as Branch_Location,
            COALESCE(ls.Current_Stock, 0) as Current_Stock,
            CASE WHEN COALESCE(ls.Current_Stock, 0) = 0 THEN 'STOCKOUT' ELSE 'IN_STOCK' END as Stockout_Status,
            COALESCE(sd.Avg_Monthly_Sales, 0) as Avg_Monthly_Sales,
            (SELECT max_date FROM latest_date) as Snapshot_Date
        FROM active_combos ac
        LEFT JOIN latest_stock ls ON ac.Item_Code = ls.Item_Number AND ac.Branch = ls.Branch_Location
        LEFT JOIN (
            SELECT Item_Code, Branch, AVG(Qty_Sold) as Avg_Monthly_Sales
            FROM dashboard_data
            GROUP BY Item_Code, Branch
        ) sd ON ac.Item_Code = sd.Item_Code AND ac.Branch = sd.Branch
        WHERE COALESCE(ls.Current_Stock, 0) = 0
        ORDER BY ac.Branch, sd.Avg_Monthly_Sales DESC NULLS LAST
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_out_analysis").fetchone()[0]
    logger.log_table_info("stock_out_analysis", count)
    
    conn.execute("DROP VIEW IF EXISTS stock_vs_sales")
    conn.execute("""
        CREATE VIEW stock_vs_sales AS
        SELECT 
            s.Item_Name, s.Item_Number, s.Branch_Location, s.File_Location,
            s.Month_End_Date as Stock_Date, s.Stock_Qty, s.Stock_Value,
            COALESCE(d.Sales_Amount, 0) as Monthly_Sales,
            COALESCE(d.Qty_Sold, 0) as Monthly_Qty_Sold,
            CASE 
                WHEN COALESCE(d.Qty_Sold, 0) > 0 THEN s.Stock_Qty / NULLIF(d.Qty_Sold, 0)
                ELSE NULL
            END as Stock_to_Sales_Ratio,
            CASE 
                WHEN s.Stock_Qty = 0 AND COALESCE(d.Qty_Sold, 0) > 0 THEN 'STOCKOUT'
                WHEN s.Stock_Qty < COALESCE(d.Qty_Sold, 0) THEN 'LOW_STOCK'
                WHEN s.Stock_Qty > COALESCE(d.Qty_Sold, 0) * 3 THEN 'OVERSTOCK'
                ELSE 'HEALTHY'
            END as Stock_Status
        FROM stock_unpivoted s
        LEFT JOIN dashboard_data d 
            ON s.Item_Number = d.Item_Code 
            AND DATE_TRUNC('month', s.Month_End_Date) = DATE_TRUNC('month', d.Month)
        WHERE s.Branch_Location IS NOT NULL AND s.Branch_Location != ''
    """)
    count = conn.execute("SELECT COUNT(*) FROM stock_vs_sales").fetchone()[0]
    logger.log_table_info("stock_vs_sales (view)", count)

# ============================================================================
# STOCK HEALTH DASHBOARD (unchanged)
# ============================================================================
def create_stock_health_dashboard(conn):
    logger.log("📊 Creating stock_health_dashboard...", "PROGRESS")
    try:
        conn.execute("DROP TABLE IF EXISTS stock_health_dashboard")
        conn.execute("""
            CREATE TABLE stock_health_dashboard AS
            WITH latest_stock AS (
                SELECT 
                    s.Item_Number,
                    s.Branch_Location,
                    s.Stock_Qty,
                    s.Month_End_Date,
                    im.Product_Group,
                    im.Division
                FROM stock_unpivoted s
                LEFT JOIN item_master im ON s.Item_Number = im.Item_Code
                WHERE s.Month_End_Date = (SELECT MAX(Month_End_Date) FROM stock_unpivoted)
            ),
            branch_avg_sales AS (
                SELECT 
                    d.Item_Code,
                    d.Branch,
                    AVG(d.Qty_Sold) as Avg_Sales
                FROM dashboard_data d
                GROUP BY d.Item_Code, d.Branch
            )
            SELECT 
                ls.Branch_Location,
                COUNT(*) as Total_Items,
                SUM(CASE WHEN ls.Stock_Qty = 0 THEN 1 ELSE 0 END) as Stockout_Count,
                SUM(CASE WHEN ls.Stock_Qty > 0 AND ls.Stock_Qty < COALESCE(bas.Avg_Sales, 0) THEN 1 ELSE 0 END) as Low_Stock_Count,
                SUM(CASE WHEN ls.Stock_Qty > COALESCE(bas.Avg_Sales, 0) * 3 THEN 1 ELSE 0 END) as Overstock_Count,
                SUM(ls.Stock_Qty) as Total_Stock_Qty,
                SUM(ls.Stock_Qty * ls.Stock_Qty) as Stock_Value
            FROM latest_stock ls
            LEFT JOIN branch_avg_sales bas ON ls.Item_Number = bas.Item_Code AND ls.Branch_Location = bas.Branch
            GROUP BY ls.Branch_Location
            ORDER BY Total_Stock_Qty DESC
        """)
        count = conn.execute("SELECT COUNT(*) FROM stock_health_dashboard").fetchone()[0]
        logger.log_table_info("stock_health_dashboard", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create stock_health_dashboard: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# BRANCH-ITEM MONTHLY ANALYSIS (unchanged)
# ============================================================================
def create_branch_item_monthly_analysis(conn):
    logger.log("📊 Creating branch_item_monthly_analysis...", "PROGRESS")
    try:
        conn.execute("DROP TABLE IF EXISTS branch_item_monthly_analysis")
        conn.execute("""
            CREATE TABLE branch_item_monthly_analysis AS
            WITH sales_agg AS (
                SELECT 
                    Item_Code, Branch, Location, Month_Label, Year, Month_Num,
                    SUM(Qty_Sold) as Qty_Sold,
                    SUM(Sales_Amount) as Sales_Amount
                FROM dashboard_data
                GROUP BY Item_Code, Branch, Location, Month_Label, Year, Month_Num
            ),
            stock_agg AS (
                SELECT 
                    Item_Number, Branch_Location,
                    STRFTIME(DATE_TRUNC('month', Month_End_Date), '%Y-%m') as Month_Label,
                    SUM(Stock_Qty) as Stock_Qty
                FROM stock_unpivoted
                GROUP BY Item_Number, Branch_Location, Month_Label
            )
            SELECT 
                s.Item_Code, im.Item_Name, s.Branch, s.Location,
                s.Month_Label, s.Year, s.Month_Num,
                s.Qty_Sold, s.Sales_Amount,
                COALESCE(st.Stock_Qty, 0) as Stock_Qty,
                CASE WHEN COALESCE(st.Stock_Qty, 0) = 0 THEN 1 ELSE 0 END as Stockout_Flag,
                CASE WHEN COALESCE(st.Stock_Qty, 0) = 0 THEN s.Qty_Sold ELSE 0 END as Potential_Lost_Sales
            FROM sales_agg s
            LEFT JOIN stock_agg st ON s.Item_Code = st.Item_Number 
                AND s.Branch = st.Branch_Location 
                AND s.Month_Label = st.Month_Label
            LEFT JOIN item_master im ON s.Item_Code = im.Item_Code
            ORDER BY s.Year, s.Month_Num, s.Branch, s.Item_Code
        """)
        count = conn.execute("SELECT COUNT(*) FROM branch_item_monthly_analysis").fetchone()[0]
        logger.log_table_info("branch_item_monthly_analysis", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create branch_item_monthly_analysis: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# CURRENT STOCK RECOMMENDATIONS (unchanged)
# ============================================================================
def create_current_stock_recommendations(conn):
    logger.log("📊 Creating current_stock_recommendations...", "PROGRESS")
    try:
        latest_date = conn.execute("SELECT MAX(Month_End_Date) FROM stock_unpivoted").fetchone()[0]
        if latest_date is None:
            logger.log("  ⚠️ No stock data found, skipping current_stock_recommendations.", "WARNING")
            return

        conn.execute("DROP TABLE IF EXISTS current_stock_recommendations")
        conn.execute("""
            CREATE TABLE current_stock_recommendations AS
            WITH current_stock AS (
                SELECT 
                    s.Item_Name, s.Item_Number, s.Branch_Location, s.File_Location,
                    SUM(s.Stock_Qty) as Current_Stock,
                    im.Product_Group, im.Division
                FROM stock_unpivoted s
                LEFT JOIN item_master im ON s.Item_Number = im.Item_Code
                WHERE s.Month_End_Date = ?
                AND s.Branch_Location IS NOT NULL
                GROUP BY s.Item_Name, s.Item_Number, s.Branch_Location, s.File_Location,
                         im.Product_Group, im.Division
            ),
            branch_avg_sales AS (
                SELECT 
                    d.Item_Code, d.Branch,
                    AVG(d.Qty_Sold) as Branch_Avg_Sales
                FROM dashboard_data d
                GROUP BY d.Item_Code, d.Branch
            )
            SELECT 
                cs.Item_Name, cs.Item_Number, cs.Branch_Location, cs.File_Location,
                cs.Current_Stock, cs.Product_Group, cs.Division,
                COALESCE(bas.Branch_Avg_Sales, 0) as Branch_Avg_Sales,
                CASE 
                    WHEN COALESCE(bas.Branch_Avg_Sales, 0) > 0 
                    THEN (COALESCE(bas.Branch_Avg_Sales, 0) * 2) - cs.Current_Stock
                    ELSE 0                END as Recommended_Order_Qty,
                CASE 
                    WHEN cs.Current_Stock = 0 AND COALESCE(bas.Branch_Avg_Sales, 0) > 0 THEN 'CRITICAL - STOCKOUT'
                    WHEN cs.Current_Stock < COALESCE(bas.Branch_Avg_Sales, 0) THEN 'LOW STOCK - ORDER SOON'
                    WHEN cs.Current_Stock < COALESCE(bas.Branch_Avg_Sales, 0) * 2 THEN 'REORDER SOON'
                    WHEN cs.Current_Stock > COALESCE(bas.Branch_Avg_Sales, 0) * 4 THEN 'OVERSTOCKED'
                    ELSE 'HEALTHY'
                END as Order_Priority,
                CASE 
                    WHEN cs.Current_Stock = 0 AND COALESCE(bas.Branch_Avg_Sales, 0) > 0 THEN 'IMMEDIATE'
                    WHEN cs.Current_Stock < COALESCE(bas.Branch_Avg_Sales, 0) THEN 'URGENT'
                    WHEN cs.Current_Stock < COALESCE(bas.Branch_Avg_Sales, 0) * 2 THEN 'SOON'
                    ELSE 'NOT URGENT'
                END as Urgency
            FROM current_stock cs
            LEFT JOIN branch_avg_sales bas 
                ON cs.Item_Number = bas.Item_Code 
                AND cs.Branch_Location = bas.Branch
            ORDER BY (COALESCE(bas.Branch_Avg_Sales, 0) * 2) - cs.Current_Stock DESC
        """, [latest_date])
        count = conn.execute("SELECT COUNT(*) FROM current_stock_recommendations").fetchone()[0]
        logger.log_table_info("current_stock_recommendations", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create current_stock_recommendations: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# STOCK STATUS SUMMARY (unchanged)
# ============================================================================
def create_stock_status_summary(conn):
    logger.log("📊 Creating stock_status_summary...", "PROGRESS")
    try:
        latest_date = conn.execute("SELECT MAX(Month_End_Date) FROM stock_unpivoted").fetchone()[0]
        if latest_date is None:
            logger.log("  ⚠️ No stock data found, skipping stock_status_summary.", "WARNING")
            return

        conn.execute("DROP TABLE IF EXISTS stock_status_summary")
        conn.execute("""
            CREATE TABLE stock_status_summary AS
            WITH latest_stock AS (
                SELECT 
                    Item_Number, Branch_Location, File_Location,
                    SUM(Stock_Qty) as Stock_Qty
                FROM stock_unpivoted
                WHERE Month_End_Date = ?
                AND Branch_Location IS NOT NULL
                GROUP BY Item_Number, Branch_Location, File_Location
            ),
            branch_avg_sales AS (
                SELECT 
                    d.Item_Code, d.Branch,
                    AVG(d.Qty_Sold) as Avg_Sales
                FROM dashboard_data d
                GROUP BY d.Item_Code, d.Branch
            ),
            stock_status AS (
                SELECT 
                    ls.Branch_Location, ls.File_Location, ls.Item_Number, ls.Stock_Qty,
                    COALESCE(bas.Avg_Sales, 0) as Avg_Sales,
                    CASE 
                        WHEN ls.Stock_Qty = 0 AND COALESCE(bas.Avg_Sales, 0) > 0 THEN 'STOCKOUT'
                        WHEN ls.Stock_Qty < COALESCE(bas.Avg_Sales, 0) THEN 'LOW_STOCK'
                        WHEN ls.Stock_Qty > COALESCE(bas.Avg_Sales, 0) * 3 THEN 'OVERSTOCK'
                        ELSE 'HEALTHY'
                    END as Stock_Status
                FROM latest_stock ls
                LEFT JOIN branch_avg_sales bas ON ls.Item_Number = bas.Item_Code AND ls.Branch_Location = bas.Branch
            )
            SELECT 
                Branch_Location, File_Location, Stock_Status,
                COUNT(*) as Item_Count
            FROM stock_status
            GROUP BY Branch_Location, File_Location, Stock_Status
        """, [latest_date])
        count = conn.execute("SELECT COUNT(*) FROM stock_status_summary").fetchone()[0]
        logger.log_table_info("stock_status_summary", count)
    except Exception as e:
        logger.log(f"  ❌ Failed to create stock_status_summary: {e}", "ERROR")
        traceback.print_exc()

# ============================================================================
# MONTHLY STOCK (unchanged)
# ============================================================================
def create_monthly_stock(conn):
    logger.log("📊 Creating monthly_stock table...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS monthly_stock")
    conn.execute("""
        CREATE TABLE monthly_stock AS
        SELECT 
            DATE_TRUNC('month', Month_End_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Month_End_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Month_End_Date) as Year,
            EXTRACT(MONTH FROM Month_End_Date) as Month_Num,
            SUM(Stock_Qty) as Total_Stock_Qty,
            SUM(Stock_Value) as Total_Stock_Value,
            COUNT(DISTINCT Item_Number) as Unique_Items,
            COUNT(DISTINCT Branch_Location) as Active_Branches
        FROM stock_unpivoted
        WHERE Branch_Location IS NOT NULL AND Branch_Location != ''
        GROUP BY DATE_TRUNC('month', Month_End_Date), 
                 STRFTIME(DATE_TRUNC('month', Month_End_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Month_End_Date),
                 EXTRACT(MONTH FROM Month_End_Date)
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM monthly_stock").fetchone()[0]
    logger.log_table_info("monthly_stock", count)

# ============================================================================
# PURCHASE RETURNS TABLE (unchanged)
# ============================================================================
def create_purchase_returns_table(conn, returns_df):
    if returns_df is None or returns_df.empty:
        logger.log("No purchase returns data available", "INFO")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchase_returns (
                Return_Date DATE, Branch VARCHAR, Vendor VARCHAR,
                Item_Code VARCHAR, Item_Name VARCHAR,
                Return_Qty DOUBLE, Amount_USD DOUBLE, Unit_Cost DOUBLE,
                FOC_Qty DOUBLE, Return_Doc_ID VARCHAR, Return_Ref_No VARCHAR,
                Return_Type VARCHAR
            )
        """)
        return
    
    logger.log("📊 Creating purchase_returns table...", "PROGRESS")
    
    returns_df = returns_df.rename(columns={
        'Purchase_Date': 'Return_Date',
        'Vendor': 'Vendor',
        'Cost_Rate': 'Unit_Cost',
        'Doc_ID': 'Return_Doc_ID',
        'Ref_No': 'Return_Ref_No'
    })
    
    if 'Return_Type' not in returns_df.columns:
        returns_df['Return_Type'] = 'PURCHASE_RETURN'
    
    conn.register('returns_temp', returns_df)
    conn.execute("DROP TABLE IF EXISTS purchase_returns")
    conn.execute("""
        CREATE TABLE purchase_returns AS
        SELECT 
            Return_Date,
            Branch,
            Vendor,
            Item_Code,
            Item_Name,
            Qty as Return_Qty,
            Amount_USD,
            Unit_Cost,
            FOC_Qty,
            Return_Doc_ID,
            Return_Ref_No,
            Return_Type
        FROM returns_temp
    """)
    
    count = conn.execute("SELECT COUNT(*) FROM purchase_returns").fetchone()[0]
    logger.log_table_info("purchase_returns", count)

# ============================================================================
# PURCHASE TABLES (unchanged)
# ============================================================================
def create_purchase_tables(conn, local_df, import_df, returns_df):
    logger.log("📊 Creating PURCHASE tables...", "PROGRESS")
    
    if local_df is not None and not local_df.empty:
        conn.register('local_purchase_temp', local_df)
        conn.execute("DROP TABLE IF EXISTS local_purchase")
        conn.execute("CREATE TABLE local_purchase AS SELECT * FROM local_purchase_temp")
        count = conn.execute("SELECT COUNT(*) FROM local_purchase").fetchone()[0]
        logger.log_table_info("local_purchase (clean)", count)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS local_purchase (
                Branch VARCHAR, Doc_ID VARCHAR, Ref_No VARCHAR, Purchase_Date DATE,
                Vendor VARCHAR, Item_Name VARCHAR, Item_Code VARCHAR,
                Qty DOUBLE, Cost_Rate DOUBLE, FOC_Qty DOUBLE, Amount_USD DOUBLE
            )
        """)
        logger.log_table_info("local_purchase", 0)
    
    create_purchase_returns_table(conn, returns_df)
    
    if import_df is not None and not import_df.empty:
        conn.register('import_purchase_temp', import_df)
        conn.execute("DROP TABLE IF EXISTS import_purchase")
        conn.execute("CREATE TABLE import_purchase AS SELECT * FROM import_purchase_temp")
        count = conn.execute("SELECT COUNT(*) FROM import_purchase").fetchone()[0]
        logger.log_table_info("import_purchase", count)
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_purchase (
                GRN_No VARCHAR, Purchase_Date DATE, Item_Name VARCHAR, Item_Name_Supplier VARCHAR,
                Item_Code VARCHAR, Unit VARCHAR, Qty DOUBLE, FOC_Qty DOUBLE,
                Inv_No VARCHAR, Inv_Date DATE, Vendor VARCHAR, Supplier_Rate DOUBLE,
                Discount_Pct DOUBLE, Rate_After_Discount DOUBLE, Amount_USD DOUBLE,
                BL_No VARCHAR, BL_Date DATE, Carrier VARCHAR, Shipping_Lead_Time DOUBLE,
                Invoice_Receipt_Lead DOUBLE, BL_Lag DOUBLE, Country VARCHAR, Location VARCHAR
            )
        """)
        logger.log_table_info("import_purchase", 0)
    
    conn.execute("DROP VIEW IF EXISTS purchase_all_clean")
    conn.execute("""
        CREATE VIEW purchase_all_clean AS
        SELECT 
            'Local' as Purchase_Type,
            Branch,
            Purchase_Date,
            Vendor,
            Item_Code,
            Item_Name,
            Qty,
            Amount_USD,
            NULL as Supplier_Rate,
            NULL as Carrier,
            NULL as Shipping_Lead_Time,
            NULL as Country,
            NULL as Unit,
            FOC_Qty
        FROM local_purchase
        WHERE Qty > 0 AND Amount_USD > 0 AND Cost_Rate > 0 AND Qty < 1000000
        UNION ALL
        SELECT 
            'Import' as Purchase_Type,
            Location as Branch,
            Purchase_Date,
            Vendor,
            Item_Code,
            Item_Name,
            Qty,
            Amount_USD,
            Supplier_Rate,
            Carrier,
            Shipping_Lead_Time,
            Country,
            Unit,
            FOC_Qty
        FROM import_purchase
        WHERE Qty > 0 AND Amount_USD > 0 AND Supplier_Rate > 0 AND Qty < 1000000
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_all_clean").fetchone()[0]
    logger.log_table_info("purchase_all_clean (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_all")
    conn.execute("""
        CREATE VIEW purchase_all AS
        SELECT 
            'Local' as Purchase_Type,
            Branch,
            Purchase_Date,
            Vendor,
            Item_Code,
            Item_Name,
            Qty,
            Amount_USD,
            NULL as Supplier_Rate,
            NULL as Carrier,
            NULL as Shipping_Lead_Time,
            NULL as Country,
            NULL as Unit,
            FOC_Qty
        FROM local_purchase
        UNION ALL
        SELECT 
            'Import' as Purchase_Type,
            Location as Branch,
            Purchase_Date,
            Vendor,
            Item_Code,
            Item_Name,
            Qty,
            Amount_USD,
            Supplier_Rate,
            Carrier,
            Shipping_Lead_Time,
            Country,
            Unit,
            FOC_Qty
        FROM import_purchase
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_all").fetchone()[0]
    logger.log_table_info("purchase_all (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_by_item")
    conn.execute("""
        CREATE VIEW purchase_by_item AS
        SELECT 
            Item_Code, Item_Name,
            COUNT(DISTINCT Vendor) as Vendor_Count,
            SUM(Qty) as Total_Qty,
            SUM(Amount_USD) as Total_Spend,
            AVG(Amount_USD / NULLIF(Qty, 0)) as Avg_Cost,
            COUNT(*) as Purchase_Count,
            MIN(Purchase_Date) as First_Purchase,
            MAX(Purchase_Date) as Last_Purchase
        FROM purchase_all_clean
        GROUP BY Item_Code, Item_Name
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_by_item").fetchone()[0]
    logger.log_table_info("purchase_by_item (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_by_vendor")
    conn.execute("""
        CREATE VIEW purchase_by_vendor AS
        SELECT 
            Vendor,
            COUNT(DISTINCT Item_Code) as Unique_Items,
            SUM(Qty) as Total_Qty,
            SUM(Amount_USD) as Total_Spend,
            COUNT(*) as Transaction_Count,
            MIN(Purchase_Date) as First_Purchase,
            MAX(Purchase_Date) as Last_Purchase
        FROM purchase_all_clean
        WHERE Vendor IS NOT NULL AND Vendor != ''
        GROUP BY Vendor
        ORDER BY Total_Spend DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_by_vendor").fetchone()[0]
    logger.log_table_info("purchase_by_vendor (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_by_branch")
    conn.execute("""
        CREATE VIEW purchase_by_branch AS
        SELECT 
            Branch,
            SUM(Qty) as Total_Qty,
            SUM(Amount_USD) as Total_Spend,
            COUNT(DISTINCT Vendor) as Vendor_Count,
            COUNT(DISTINCT Item_Code) as Unique_Items,
            COUNT(*) as Transaction_Count
        FROM purchase_all_clean
        GROUP BY Branch
        ORDER BY Total_Spend DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_by_branch").fetchone()[0]
    logger.log_table_info("purchase_by_branch (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_trend")
    conn.execute("""
        CREATE VIEW purchase_trend AS
        SELECT 
            DATE_TRUNC('month', Purchase_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Purchase_Date) as Year,
            EXTRACT(MONTH FROM Purchase_Date) as Month_Num,
            Purchase_Type,
            SUM(Qty) as Total_Qty,
            SUM(Amount_USD) as Total_Spend,
            COUNT(*) as Transaction_Count
        FROM purchase_all_clean
        GROUP BY DATE_TRUNC('month', Purchase_Date), STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Purchase_Date), EXTRACT(MONTH FROM Purchase_Date), Purchase_Type
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_trend").fetchone()[0]
    logger.log_table_info("purchase_trend (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS avg_purchase_price")
    conn.execute("""
        CREATE VIEW avg_purchase_price AS
        SELECT 
            Item_Code, Item_Name,
            AVG(Amount_USD / NULLIF(Qty, 0)) as Avg_Cost,
            COUNT(*) as Observations
        FROM purchase_all_clean
        WHERE Qty > 0 AND Amount_USD > 0
        GROUP BY Item_Code, Item_Name
    """)
    count = conn.execute("SELECT COUNT(*) FROM avg_purchase_price").fetchone()[0]
    logger.log_table_info("avg_purchase_price (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_summary")
    conn.execute("""
        CREATE VIEW purchase_summary AS
        SELECT 
            DATE_TRUNC('month', Purchase_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Purchase_Date) as Year,
            EXTRACT(MONTH FROM Purchase_Date) as Month_Num,
            Purchase_Type,
            COUNT(DISTINCT Vendor) as Vendor_Count,
            COUNT(DISTINCT Item_Code) as Item_Count,
            COUNT(*) as Transaction_Count,
            SUM(Qty) as Total_Qty,
            SUM(Amount_USD) as Total_Spend,
            AVG(Amount_USD / NULLIF(Qty, 0)) as Avg_Cost_Per_Unit
        FROM purchase_all_clean
        GROUP BY DATE_TRUNC('month', Purchase_Date), 
                 STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Purchase_Date),
                 EXTRACT(MONTH FROM Purchase_Date),
                 Purchase_Type
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_summary").fetchone()[0]
    logger.log_table_info("purchase_summary (view)", count)
    
    conn.execute("DROP VIEW IF EXISTS purchase_vs_sales")
    conn.execute("""
        CREATE VIEW purchase_vs_sales AS
        WITH purchase_agg AS (
            SELECT 
                DATE_TRUNC('month', Purchase_Date) as Month,
                SUM(Amount_USD) as Total_Purchases,
                SUM(Qty) as Purchase_Qty,
                COUNT(*) as Purchase_Transactions
            FROM purchase_all_clean
            GROUP BY DATE_TRUNC('month', Purchase_Date)
        ),
        sales_agg AS (
            SELECT 
                DATE_TRUNC('month', Month) as Month,
                SUM(Sales_Amount) as Total_Sales,
                SUM(Qty_Sold) as Sales_Qty,
                SUM(Sales_Transactions) as Sales_Transactions
            FROM dashboard_data
            GROUP BY DATE_TRUNC('month', Month)
        )
        SELECT 
            COALESCE(p.Month, s.Month) as Month,
            STRFTIME(COALESCE(p.Month, s.Month), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM COALESCE(p.Month, s.Month)) as Year,
            EXTRACT(MONTH FROM COALESCE(p.Month, s.Month)) as Month_Num,
            COALESCE(p.Total_Purchases, 0) as Total_Purchases,
            COALESCE(s.Total_Sales, 0) as Total_Sales,
            COALESCE(p.Purchase_Qty, 0) as Purchase_Qty,
            COALESCE(s.Sales_Qty, 0) as Sales_Qty,
            COALESCE(p.Purchase_Transactions, 0) as Purchase_Transactions,
            COALESCE(s.Sales_Transactions, 0) as Sales_Transactions,
            CASE 
                WHEN COALESCE(s.Total_Sales, 0) > 0 
                THEN COALESCE(p.Total_Purchases, 0) / NULLIF(s.Total_Sales, 0) * 100
                ELSE 0
            END as Purchase_to_Sales_Ratio,
            CASE 
                WHEN COALESCE(p.Total_Purchases, 0) > 0 
                THEN COALESCE(s.Total_Sales, 0) / NULLIF(p.Total_Purchases, 0) * 100
                ELSE 0
            END as Sales_to_Purchase_Ratio
        FROM purchase_agg p
        FULL OUTER JOIN sales_agg s ON p.Month = s.Month
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM purchase_vs_sales").fetchone()[0]
    logger.log_table_info("purchase_vs_sales (view)", count)

# ============================================================================
# PRF/PO TABLES (unchanged)
# ============================================================================
def create_prf_po_tables(conn, prf_df):
    if prf_df is None or prf_df.empty:
        logger.log("No PRF/PO data available", "WARNING")
        return

    logger.log("📊 Creating PRF/PO tables...", "PROGRESS")

    conn.register('prf_temp', prf_df)
    conn.execute("DROP TABLE IF EXISTS purchase_orders")
    conn.execute("CREATE TABLE purchase_orders AS SELECT * FROM prf_temp")
    count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    logger.log_table_info("purchase_orders", count)

    conn.execute("DROP TABLE IF EXISTS supplier_performance")
    conn.execute("""
        CREATE TABLE supplier_performance AS
        SELECT 
            Supplier_Name,
            COUNT(DISTINCT PO_No) as Total_POs,
            COUNT(DISTINCT Item_Code) as Unique_Items,
            SUM(PO_Qty) as Total_Ordered_Qty,
            SUM(Invoice_Amount) as Total_Invoiced_Value,
            AVG(Invoice_Amount / NULLIF(PO_Qty, 0)) as Avg_Unit_Price,
            COUNT(CASE WHEN PO_Status = 'Closed' THEN 1 END) as Closed_POs,
            COUNT(CASE WHEN PO_Status = 'Open' THEN 1 END) as Open_POs,
            AVG(PO_Age_Days) as Avg_PO_Age_Days,
            SUM(Advance_Amount_Paid) as Total_Advance_Paid,
            SUM(Final_Outstanding) as Total_Outstanding_Balance
        FROM purchase_orders
        WHERE Supplier_Name IS NOT NULL AND Supplier_Name != ''
        GROUP BY Supplier_Name
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_performance").fetchone()[0]
    logger.log_table_info("supplier_performance", count)

    conn.execute("DROP TABLE IF EXISTS item_purchase_summary")
    conn.execute("""
        CREATE TABLE item_purchase_summary AS
        SELECT 
            Item_Code,
            "Product_Name_(DRC)" as Item_Name,
            COUNT(DISTINCT Supplier_Name) as Supplier_Count,
            SUM(PO_Qty) as Total_PO_Qty,
            SUM(PI_Qty) as Total_PI_Qty,
            SUM(GRN_Qty) as Total_GRN_Qty,
            AVG(PO_Rate) as Avg_PO_Rate,
            AVG(Invoice_Rate) as Avg_Invoice_Rate,
            SUM(Invoice_Amount) as Total_Invoice_Amount,
            MIN(PO_Date) as First_PO_Date,
            MAX(PO_Date) as Last_PO_Date
        FROM purchase_orders
        WHERE Item_Code IS NOT NULL AND Item_Code != ''
        GROUP BY Item_Code, "Product_Name_(DRC)"
    """)
    count = conn.execute("SELECT COUNT(*) FROM item_purchase_summary").fetchone()[0]
    logger.log_table_info("item_purchase_summary", count)

    conn.execute("DROP VIEW IF EXISTS supplier_lead_time_performance")
    conn.execute("""
        CREATE VIEW supplier_lead_time_performance AS
        SELECT 
            Vendor,
            AVG(Shipping_Lead_Time) as Avg_Shipping_Lead_Time,
            AVG(Invoice_Receipt_Lead) as Avg_Invoice_Receipt_Lead,
            AVG(BL_Lag) as Avg_BL_Lag,
            COUNT(*) as Total_Orders,
            STDDEV(Shipping_Lead_Time) as Lead_Time_StdDev,
            AVG(Shipping_Lead_Time) - STDDEV(Shipping_Lead_Time) as Min_Expected_Lead_Time,
            AVG(Shipping_Lead_Time) + STDDEV(Shipping_Lead_Time) as Max_Expected_Lead_Time
        FROM import_purchase
        WHERE Shipping_Lead_Time > 0
        GROUP BY Vendor
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_lead_time_performance").fetchone()[0]
    logger.log_table_info("supplier_lead_time_performance (view)", count)

# ============================================================================
# SUPPLIER MASTER TABLES (unchanged)
# ============================================================================
def create_supplier_master_tables(conn, supplier_df):
    if supplier_df is None or supplier_df.empty:
        logger.log("No Supplier Master data available", "WARNING")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS supplier_master (
                Supplier_Name VARCHAR,
                Location VARCHAR,
                Address VARCHAR,
                File VARCHAR,
                Company VARCHAR,
                Currency VARCHAR,
                City VARCHAR,
                District VARCHAR,
                State VARCHAR,
                Balance_Checking_Status VARCHAR,
                Rate DOUBLE,
                Euro_To_USD_Rate DOUBLE,
                Opening_Balance DOUBLE,
                Opening_Balance_Date DATE,
                Lead_Time DOUBLE
            )
        """)
        return
    
    logger.log("📊 Creating supplier_master table...", "PROGRESS")
    
    conn.register('supplier_master_temp', supplier_df)
    conn.execute("DROP TABLE IF EXISTS supplier_master")
    conn.execute("CREATE TABLE supplier_master AS SELECT * FROM supplier_master_temp")
    
    count = conn.execute("SELECT COUNT(*) FROM supplier_master").fetchone()[0]
    logger.log_table_info("supplier_master", count)
    
    lead_summary = conn.execute("""
        SELECT 
            AVG(Lead_Time) as Avg_Lead_Time,
            MIN(Lead_Time) as Min_Lead_Time,
            MAX(Lead_Time) as Max_Lead_Time,
            COUNT(*) as Total_Suppliers,
            SUM(CASE WHEN Lead_Time > 0 THEN 1 ELSE 0 END) as Suppliers_With_Lead_Time
        FROM supplier_master
    """).fetchone()
    
    logger.log(f"  └─ Lead Time Summary:", "DATA")
    logger.log(f"     - Avg Lead Time: {lead_summary[0]:.0f} days", "DATA")
    logger.log(f"     - Min Lead Time: {lead_summary[1]:.0f} days", "DATA")
    logger.log(f"     - Max Lead Time: {lead_summary[2]:.0f} days", "DATA")
    logger.log(f"     - Suppliers with Lead Time: {lead_summary[4]:,}/{lead_summary[3]:,}", "DATA")

# ============================================================================
# SAFETY STOCK TABLES (unchanged)
# ============================================================================
def create_safety_stock_tables(conn):
    logger.log("🛡️ Creating SAFETY STOCK tables...", "PROGRESS")
    
    try:
        conn.execute("SELECT COUNT(*) FROM item_demand").fetchone()
    except:
        logger.log("  ⚠️ item_demand table not found, skipping safety stock tables", "WARNING")
        return
    
    conn.execute("DROP TABLE IF EXISTS safety_stock_by_supplier")
    conn.execute("""
        CREATE TABLE safety_stock_by_supplier AS
        WITH supplier_lead_time AS (
            SELECT 
                sm.Supplier_Name,
                sm.Lead_Time,
                sm.Location,
                sm.Currency,
                COALESCE(sp.Total_Sales, 0) as Total_Sales,
                COALESCE(sp.Total_Qty, 0) as Total_Qty,
                COALESCE(sp.Unique_Products, 0) as Unique_Products
            FROM supplier_master sm
            LEFT JOIN supplier_summary sp ON UPPER(sm.Supplier_Name) = UPPER(sp.Supplier)
        ),
        supplier_daily_demand AS (
            SELECT 
                s.Supplier_Name,
                s.Lead_Time,
                s.Total_Qty,
                s.Unique_Products,
                s.Total_Qty / NULLIF(s.Unique_Products, 0) / 30 as Avg_Daily_Demand_Qty,
                s.Total_Sales / NULLIF(s.Unique_Products, 0) / 30 as Avg_Daily_Demand_Value,
                CASE 
                    WHEN s.Lead_Time <= 30 THEN 0.5
                    WHEN s.Lead_Time <= 60 THEN 1.0
                    WHEN s.Lead_Time <= 90 THEN 1.5
                    WHEN s.Lead_Time <= 120 THEN 2.0
                    ELSE 2.5
                END as Lead_Time_Factor
            FROM supplier_lead_time s
        )
        SELECT 
            Supplier_Name,
            Lead_Time,
            Unique_Products,
            Avg_Daily_Demand_Qty,
            Avg_Daily_Demand_Value,
            Lead_Time_Factor,
            ROUND(Avg_Daily_Demand_Qty * Lead_Time * Lead_Time_Factor, 0) as Safety_Stock_Qty,
            ROUND(Avg_Daily_Demand_Value * Lead_Time * Lead_Time_Factor, 2) as Safety_Stock_Value,
            ROUND(Avg_Daily_Demand_Qty * Lead_Time * Lead_Time_Factor + Avg_Daily_Demand_Qty * Lead_Time, 0) as Reorder_Point_Qty,
            ROUND(Avg_Daily_Demand_Value * Lead_Time * Lead_Time_Factor + Avg_Daily_Demand_Value * Lead_Time, 2) as Reorder_Point_Value,
            CASE 
                WHEN Avg_Daily_Demand_Qty = 0 THEN 'No Demand Data'
                WHEN Lead_Time_Factor <= 0.5 THEN 'Fast Delivery - Low Safety Stock'
                WHEN Lead_Time_Factor <= 1.0 THEN 'Normal - Standard Safety Stock'
                WHEN Lead_Time_Factor <= 1.5 THEN 'Extended Lead Time - Higher Safety Stock'
                ELSE 'Long Lead Time - High Safety Stock'
            END as Safety_Stock_Strategy
        FROM supplier_daily_demand
        ORDER BY Safety_Stock_Qty DESC
    """)
    
    count = conn.execute("SELECT COUNT(*) FROM safety_stock_by_supplier").fetchone()[0]
    logger.log_table_info("safety_stock_by_supplier", count)
    
    conn.execute("DROP TABLE IF EXISTS safety_stock_by_item")
    conn.execute("""
        CREATE TABLE safety_stock_by_item AS
        WITH item_daily_demand AS (
            SELECT 
                id.Item_Code,
                id.Item_Name,
                id.Product_Group,
                id.Total_Qty,
                id.Total_Revenue,
                id.Demand_Stability_Index,
                id.Active_Months,
                im.Primary_Supplier,
                sm.Lead_Time,
                sm.Location as Supplier_Location,
                CASE 
                    WHEN id.Active_Months >= 3 THEN id.Total_Qty / NULLIF(id.Active_Months, 0) / 30
                    ELSE id.Total_Qty / NULLIF(365, 0)
                END as Avg_Daily_Demand_Qty,
                CASE 
                    WHEN id.Active_Months >= 3 THEN id.Total_Revenue / NULLIF(id.Active_Months, 0) / 30
                    ELSE id.Total_Revenue / NULLIF(365, 0)
                END as Avg_Daily_Demand_Value
            FROM item_demand id
            LEFT JOIN item_master im ON id.Item_Code = im.Item_Code
            LEFT JOIN supplier_master sm ON UPPER(im.Primary_Supplier) = UPPER(sm.Supplier_Name)
            WHERE id.Total_Qty > 0 AND id.Active_Months >= 1
        ),
        lead_time_factor AS (
            SELECT 
                *,
                CASE 
                    WHEN Lead_Time IS NULL OR Lead_Time = 0 THEN 180
                    WHEN Lead_Time <= 30 THEN 0.5
                    WHEN Lead_Time <= 60 THEN 1.0
                    WHEN Lead_Time <= 90 THEN 1.5
                    WHEN Lead_Time <= 120 THEN 2.0
                    ELSE 2.5
                END as Lead_Time_Factor,
                CASE 
                    WHEN Demand_Stability_Index IS NULL OR Demand_Stability_Index > 0.7 THEN 1.0
                    WHEN Demand_Stability_Index > 0.4 THEN 1.5
                    ELSE 2.5
                END as Variability_Factor
            FROM item_daily_demand
        )
        SELECT 
            Item_Code,
            Item_Name,
            Product_Group,
            Primary_Supplier,
            Supplier_Location,
            Lead_Time,
            Avg_Daily_Demand_Qty,
            Avg_Daily_Demand_Value,
            Demand_Stability_Index,
            Active_Months,
            Lead_Time_Factor,
            Variability_Factor,
            ROUND(Avg_Daily_Demand_Qty * COALESCE(Lead_Time, 180) * Lead_Time_Factor * Variability_Factor, 0) as Safety_Stock_Qty,
            ROUND(Avg_Daily_Demand_Value * COALESCE(Lead_Time, 180) * Lead_Time_Factor * Variability_Factor, 2) as Safety_Stock_Value,
            ROUND(Avg_Daily_Demand_Qty * COALESCE(Lead_Time, 180) * Lead_Time_Factor * Variability_Factor + Avg_Daily_Demand_Qty * COALESCE(Lead_Time, 180), 0) as Reorder_Point_Qty,
            ROUND(Avg_Daily_Demand_Value * COALESCE(Lead_Time, 180) * Lead_Time_Factor * Variability_Factor + Avg_Daily_Demand_Value * COALESCE(Lead_Time, 180), 2) as Reorder_Point_Value,
            CASE 
                WHEN Primary_Supplier IS NULL OR Primary_Supplier = '' THEN 'No Primary Supplier'
                WHEN Lead_Time_Factor <= 0.5 THEN 'Fast Delivery'
                WHEN Lead_Time_Factor <= 1.0 THEN 'Normal Lead Time'
                WHEN Lead_Time_Factor <= 1.5 THEN 'Extended Lead Time'
                ELSE 'Long Lead Time'
            END as Lead_Time_Category,
            CASE 
                WHEN Demand_Stability_Index > 0.7 THEN 'Stable Demand'
                WHEN Demand_Stability_Index > 0.4 THEN 'Moderate Variability'
                ELSE 'Volatile Demand'
            END as Demand_Category,
            0 as Current_Stock,
            0 as Short_Excess
        FROM lead_time_factor
        ORDER BY Safety_Stock_Qty DESC
    """)
    
    count = conn.execute("SELECT COUNT(*) FROM safety_stock_by_item").fetchone()[0]
    logger.log_table_info("safety_stock_by_item", count)
    
    try:
        conn.execute("""
            UPDATE safety_stock_by_item
            SET 
                Current_Stock = COALESCE(
                    (SELECT SUM(Stock_Qty) 
                     FROM stock_unpivoted 
                     WHERE Item_Number = safety_stock_by_item.Item_Code
                     AND Month_End_Date = (SELECT MAX(Month_End_Date) FROM stock_unpivoted)
                     GROUP BY Item_Number), 0),
                Short_Excess = COALESCE(
                    (SELECT SUM(Stock_Qty) 
                     FROM stock_unpivoted 
                     WHERE Item_Number = safety_stock_by_item.Item_Code
                     AND Month_End_Date = (SELECT MAX(Month_End_Date) FROM stock_unpivoted)
                     GROUP BY Item_Number), 0) - Safety_Stock_Qty
        """)
        logger.log("  └─ Updated safety_stock_by_item with current stock data", "SUCCESS")
    except Exception as e:
        logger.log(f"  └─ Could not update current stock: {e}", "WARNING")
    
    conn.execute("DROP TABLE IF EXISTS safety_stock_summary")
    conn.execute("""
        CREATE TABLE safety_stock_summary AS
        SELECT 
            'Overall' as Category,
            COUNT(*) as Total_Items,
            SUM(Safety_Stock_Qty) as Total_Safety_Stock_Qty,
            SUM(Safety_Stock_Value) as Total_Safety_Stock_Value,
            AVG(Safety_Stock_Qty) as Avg_Safety_Stock_Qty,
            AVG(Safety_Stock_Value) as Avg_Safety_Stock_Value,
            AVG(Lead_Time) as Avg_Lead_Time
        FROM safety_stock_by_item
        UNION ALL
        SELECT 
            Product_Group as Category,
            COUNT(*) as Total_Items,
            SUM(Safety_Stock_Qty) as Total_Safety_Stock_Qty,
            SUM(Safety_Stock_Value) as Total_Safety_Stock_Value,
            AVG(Safety_Stock_Qty) as Avg_Safety_Stock_Qty,
            AVG(Safety_Stock_Value) as Avg_Safety_Stock_Value,
            AVG(Lead_Time) as Avg_Lead_Time
        FROM safety_stock_by_item
        GROUP BY Product_Group
        UNION ALL
        SELECT 
            Lead_Time_Category as Category,
            COUNT(*) as Total_Items,
            SUM(Safety_Stock_Qty) as Total_Safety_Stock_Qty,
            SUM(Safety_Stock_Value) as Total_Safety_Stock_Value,
            AVG(Safety_Stock_Qty) as Avg_Safety_Stock_Qty,
            AVG(Safety_Stock_Value) as Avg_Safety_Stock_Value,
            AVG(Lead_Time) as Avg_Lead_Time
        FROM safety_stock_by_item
        GROUP BY Lead_Time_Category
    """)
    
    count = conn.execute("SELECT COUNT(*) FROM safety_stock_summary").fetchone()[0]
    logger.log_table_info("safety_stock_summary", count)

# ============================================================================
# FOC TABLES (unchanged)
# ============================================================================
def create_foc_tables(conn):
    logger.log("🎯 Creating FOC tables...", "PROGRESS")
    
    conn.execute("DROP TABLE IF EXISTS foc_sales_summary")
    conn.execute("""
        CREATE TABLE foc_sales_summary AS
        SELECT 
            s.Item_Code,
            im.Item_Name,
            im.Product_Group,
            im.Division,
            s.Branch,
            lm.Location,
            SUM(s.Quantity) as Total_Qty_Sold,
            SUM(s.Free_Qty) as Total_FOC_Qty,
            SUM(s.Amount_USD) as Total_Revenue,
            COUNT(DISTINCT s.Invoice_No) as Total_Transactions,
            COUNT(DISTINCT CASE WHEN s.Free_Qty > 0 THEN s.Invoice_No END) as FOC_Transactions,
            AVG(CASE WHEN s.Free_Qty > 0 THEN s.Free_Qty END) as Avg_FOC_Per_Transaction,
            SUM(s.Quantity) - SUM(s.Free_Qty) as Paid_Qty,
            ROUND(SUM(s.Free_Qty) / NULLIF(SUM(s.Quantity), 0) * 100, 2) as FOC_Percentage
        FROM sales_raw s
        LEFT JOIN item_master im ON s.Item_Code = im.Item_Code
        LEFT JOIN location_master lm ON s.Branch = lm.Branch
        WHERE s.Quantity > 0 AND s.Free_Qty >= 0
        GROUP BY s.Item_Code, im.Item_Name, im.Product_Group, im.Division, s.Branch, lm.Location
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_sales_summary").fetchone()[0]
    logger.log_table_info("foc_sales_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_sales_monthly")
    conn.execute("""
        CREATE TABLE foc_sales_monthly AS
        SELECT 
            DATE_TRUNC('month', Sale_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Sale_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Sale_Date) as Year,
            EXTRACT(MONTH FROM Sale_Date) as Month_Num,
            EXTRACT(QUARTER FROM Sale_Date) as Quarter,
            SUM(Quantity) as Total_Qty,
            SUM(Free_Qty) as Total_FOC_Qty,
            SUM(Quantity) - SUM(Free_Qty) as Paid_Qty,
            SUM(Amount_USD) as Total_Revenue,
            SUM(Free_Qty * Price) as FOC_Revenue_Value,
            COUNT(DISTINCT Invoice_No) as Total_Transactions,
            COUNT(DISTINCT CASE WHEN Free_Qty > 0 THEN Invoice_No END) as FOC_Transactions,
            ROUND(SUM(Free_Qty) / NULLIF(SUM(Quantity), 0) * 100, 2) as FOC_Pct,
            ROUND(SUM(Free_Qty * Price) / NULLIF(SUM(Amount_USD), 0) * 100, 2) as FOC_Value_Pct
        FROM sales_raw
        WHERE Quantity > 0 AND Free_Qty >= 0
        GROUP BY DATE_TRUNC('month', Sale_Date), 
                 STRFTIME(DATE_TRUNC('month', Sale_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Sale_Date),
                 EXTRACT(MONTH FROM Sale_Date),
                 EXTRACT(QUARTER FROM Sale_Date)
        ORDER BY Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_sales_monthly").fetchone()[0]
    logger.log_table_info("foc_sales_monthly", count)
    
    conn.execute("DROP VIEW IF EXISTS foc_adjusted_demand")
    conn.execute("""
        CREATE VIEW foc_adjusted_demand AS
        SELECT 
            STRFTIME(Sale_Date, '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Sale_Date) as Year,
            EXTRACT(MONTH FROM Sale_Date) as Month_Num,
            EXTRACT(QUARTER FROM Sale_Date) as Quarter,
            Item_Code,
            Branch,
            SUM(Quantity) as Total_Demand_Qty,
            SUM(Free_Qty) as FOC_Qty,
            SUM(Quantity) - SUM(Free_Qty) as Paid_Qty,
            SUM(Amount_USD) as Revenue
        FROM sales_raw
        WHERE Quantity > 0 AND Free_Qty >= 0
        GROUP BY STRFTIME(Sale_Date, '%Y-%m'), 
                 EXTRACT(YEAR FROM Sale_Date),
                 EXTRACT(MONTH FROM Sale_Date),
                 EXTRACT(QUARTER FROM Sale_Date),
                 Item_Code, Branch
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_adjusted_demand").fetchone()[0]
    logger.log_table_info("foc_adjusted_demand (view)", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_purchase_summary")
    conn.execute("""
        CREATE TABLE foc_purchase_summary AS
        SELECT 
            'Local' as Purchase_Type,
            lp.Branch,
            lp.Vendor,
            lp.Item_Code,
            lp.Item_Name,
            im.Product_Group,
            im.Division,
            SUM(lp.Qty) as Total_Purchase_Qty,
            SUM(lp.FOC_Qty) as Total_FOC_Qty,
            SUM(lp.Amount_USD) as Total_Amount,
            COUNT(DISTINCT lp.Doc_ID) as Total_Transactions,
            COUNT(DISTINCT CASE WHEN lp.FOC_Qty > 0 THEN lp.Doc_ID END) as FOC_Transactions,
            AVG(CASE WHEN lp.FOC_Qty > 0 THEN lp.FOC_Qty END) as Avg_FOC_Per_Transaction,
            ROUND(SUM(lp.FOC_Qty) / NULLIF(SUM(lp.Qty), 0) * 100, 2) as FOC_Percentage
        FROM local_purchase lp
        LEFT JOIN item_master im ON lp.Item_Code = im.Item_Code
        WHERE lp.Qty >= 0 AND lp.FOC_Qty >= 0
        GROUP BY lp.Branch, lp.Vendor, lp.Item_Code, lp.Item_Name, im.Product_Group, im.Division
        UNION ALL
        SELECT 
            'Import' as Purchase_Type,
            ip.Location as Branch,
            ip.Vendor,
            ip.Item_Code,
            ip.Item_Name,
            im.Product_Group,
            im.Division,
            SUM(ip.Qty) as Total_Purchase_Qty,
            SUM(ip.FOC_Qty) as Total_FOC_Qty,
            SUM(ip.Amount_USD) as Total_Amount,
            COUNT(DISTINCT ip.GRN_No) as Total_Transactions,
            COUNT(DISTINCT CASE WHEN ip.FOC_Qty > 0 THEN ip.GRN_No END) as FOC_Transactions,
            AVG(CASE WHEN ip.FOC_Qty > 0 THEN ip.FOC_Qty END) as Avg_FOC_Per_Transaction,
            ROUND(SUM(ip.FOC_Qty) / NULLIF(SUM(ip.Qty), 0) * 100, 2) as FOC_Percentage
        FROM import_purchase ip
        LEFT JOIN item_master im ON ip.Item_Code = im.Item_Code
        WHERE ip.Qty >= 0 AND ip.FOC_Qty >= 0
        GROUP BY ip.Location, ip.Vendor, ip.Item_Code, ip.Item_Name, im.Product_Group, im.Division
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_purchase_summary").fetchone()[0]
    logger.log_table_info("foc_purchase_summary", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_purchase_monthly")
    conn.execute("""
        CREATE TABLE foc_purchase_monthly AS
        SELECT 
            'Local' as Purchase_Type,
            DATE_TRUNC('month', Purchase_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Purchase_Date) as Year,
            EXTRACT(MONTH FROM Purchase_Date) as Month_Num,
            EXTRACT(QUARTER FROM Purchase_Date) as Quarter,
            SUM(Qty) as Total_Qty,
            SUM(FOC_Qty) as Total_FOC_Qty,
            SUM(Amount_USD) as Total_Amount,
            COUNT(DISTINCT Doc_ID) as Transactions,
            COUNT(DISTINCT CASE WHEN FOC_Qty > 0 THEN Doc_ID END) as FOC_Transactions,
            ROUND(SUM(FOC_Qty) / NULLIF(SUM(Qty), 0) * 100, 2) as FOC_Percentage
        FROM local_purchase
        WHERE Qty >= 0 AND FOC_Qty >= 0
        GROUP BY DATE_TRUNC('month', Purchase_Date),
                 STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Purchase_Date),
                 EXTRACT(MONTH FROM Purchase_Date),
                 EXTRACT(QUARTER FROM Purchase_Date)
        UNION ALL
        SELECT 
            'Import' as Purchase_Type,
            DATE_TRUNC('month', Purchase_Date) as Month,
            STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Purchase_Date) as Year,
            EXTRACT(MONTH FROM Purchase_Date) as Month_Num,
            EXTRACT(QUARTER FROM Purchase_Date) as Quarter,
            SUM(Qty) as Total_Qty,
            SUM(FOC_Qty) as Total_FOC_Qty,
            SUM(Amount_USD) as Total_Amount,
            COUNT(DISTINCT GRN_No) as Transactions,
            COUNT(DISTINCT CASE WHEN FOC_Qty > 0 THEN GRN_No END) as FOC_Transactions,
            ROUND(SUM(FOC_Qty) / NULLIF(SUM(Qty), 0) * 100, 2) as FOC_Percentage
        FROM import_purchase
        WHERE Qty >= 0 AND FOC_Qty >= 0
        GROUP BY DATE_TRUNC('month', Purchase_Date),
                 STRFTIME(DATE_TRUNC('month', Purchase_Date), '%Y-%m'),
                 EXTRACT(YEAR FROM Purchase_Date),
                 EXTRACT(MONTH FROM Purchase_Date),
                 EXTRACT(QUARTER FROM Purchase_Date)
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_purchase_monthly").fetchone()[0]
    logger.log_table_info("foc_purchase_monthly", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_sales_outliers")
    conn.execute("""
        CREATE TABLE foc_sales_outliers AS
        WITH foc_stats AS (
            SELECT 
                AVG(Free_Qty) as avg_foc,
                STDDEV(Free_Qty) as std_foc
            FROM sales_raw
            WHERE Free_Qty > 0
        )
        SELECT 
            Sale_Date,
            Branch,
            s.Item_Code,
            im.Item_Name,
            Quantity,
            Free_Qty,
            Amount_USD,
            CASE 
                WHEN Free_Qty > (SELECT avg_foc + 3 * std_foc FROM foc_stats) THEN 'Large FOC'
                WHEN Free_Qty > Quantity THEN 'FOC > Quantity'
                ELSE 'Outlier'
            END as anomaly_type
        FROM sales_raw s
        LEFT JOIN item_master im ON s.Item_Code = im.Item_Code
        CROSS JOIN foc_stats
        WHERE Free_Qty > 0
        AND (Free_Qty > (SELECT avg_foc + 3 * std_foc FROM foc_stats) 
             OR Free_Qty > Quantity)
        ORDER BY Free_Qty DESC
        LIMIT 100
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_sales_outliers").fetchone()[0]
    logger.log_table_info("foc_sales_outliers", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_purchase_outliers")
    conn.execute("""
        CREATE TABLE foc_purchase_outliers AS
        WITH foc_stats AS (
            SELECT 
                AVG(FOC_Qty) as avg_foc,
                STDDEV(FOC_Qty) as std_foc
            FROM local_purchase
            WHERE FOC_Qty > 0
        )
        SELECT 
            Purchase_Date,
            Branch,
            Vendor,
            Item_Code,
            Item_Name,
            Qty,
            FOC_Qty,
            Amount_USD,
            Cost_Rate,
            CASE 
                WHEN FOC_Qty > (SELECT avg_foc + 3 * std_foc FROM foc_stats) THEN 'Large FOC'
                WHEN FOC_Qty > Qty THEN 'FOC > Qty'
                ELSE 'Outlier'
            END as anomaly_type
        FROM local_purchase
        CROSS JOIN foc_stats
        WHERE FOC_Qty > 0
        AND (FOC_Qty > (SELECT avg_foc + 3 * std_foc FROM foc_stats) 
             OR FOC_Qty > Qty)
        ORDER BY FOC_Qty DESC
        LIMIT 100
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_purchase_outliers").fetchone()[0]
    logger.log_table_info("foc_purchase_outliers", count)
    
    conn.execute("DROP VIEW IF EXISTS foc_recommendations")
    conn.execute("""
        CREATE VIEW foc_recommendations AS
        SELECT 
            'SALES' as Data_Type,
            Item_Code,
            Item_Name,
            Product_Group,
            Branch,
            Total_Qty_Sold as Total_Qty,
            Total_FOC_Qty,
            FOC_Percentage as FOC_Pct,
            CASE 
                WHEN FOC_Percentage > 20 THEN 'CRITICAL - Review Pricing'
                WHEN FOC_Percentage > 10 THEN 'HIGH - Monitor Closely'
                WHEN FOC_Percentage > 5 THEN 'MEDIUM - Track Trends'
                ELSE 'LOW - Normal'
            END as FOC_Severity,
            'Consider adjusting FOC strategy' as Recommendation
        FROM foc_sales_summary
        WHERE Total_FOC_Qty > 0
        UNION ALL
        SELECT 
            'PURCHASE' as Data_Type,
            Item_Code,
            Item_Name,
            Product_Group,
            Branch,
            Total_Purchase_Qty as Total_Qty,
            Total_FOC_Qty,
            FOC_Percentage as FOC_Pct,
            CASE 
                WHEN FOC_Percentage > 5 THEN 'HIGH - Review Supplier'
                WHEN FOC_Percentage > 2 THEN 'MEDIUM - Track Trends'
                ELSE 'LOW - Normal'
            END as FOC_Severity,
            'Consider negotiating FOC terms with supplier' as Recommendation
        FROM foc_purchase_summary
        WHERE Total_FOC_Qty > 0
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_recommendations").fetchone()[0]
    logger.log_table_info("foc_recommendations (view)", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_demand_impact")
    conn.execute("""
        CREATE TABLE foc_demand_impact AS
        SELECT 
            sm.Month_Label,
            sm.Year,
            sm.Month_Num,
            sm.Quarter,
            sm.Total_Qty,
            COALESCE(fm.Total_FOC_Qty, 0) as FOC_Qty,
            sm.Total_Qty - COALESCE(fm.Total_FOC_Qty, 0) as Paid_Qty,
            COALESCE(fm.FOC_Pct, 0) as FOC_Pct,
            sm.Total_Sales as Total_Revenue,
            COALESCE(fm.FOC_Revenue_Value, 0) as FOC_Revenue,
            COALESCE(fm.FOC_Value_Pct, 0) as FOC_Value_Pct,
            AVG(COALESCE(fm.FOC_Pct, 0)) OVER (ORDER BY sm.Year, sm.Month_Num ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as FOC_MA_3,
            AVG(COALESCE(fm.FOC_Pct, 0)) OVER (ORDER BY sm.Year, sm.Month_Num ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as FOC_MA_6
        FROM monthly_summary sm
        LEFT JOIN foc_sales_monthly fm 
            ON sm.Month_Label = fm.Month_Label
        ORDER BY sm.Year, sm.Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_demand_impact").fetchone()[0]
    logger.log_table_info("foc_demand_impact", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_sales_by_branch")
    conn.execute("""
        CREATE TABLE foc_sales_by_branch AS
        SELECT 
            sr.Branch,
            lm.Location,
            COUNT(DISTINCT sr.Item_Code) as Unique_Products_With_FOC,
            SUM(sr.Quantity) as Total_Qty_Sold,
            SUM(sr.Free_Qty) as Total_FOC_Qty,
            SUM(sr.Quantity) - SUM(sr.Free_Qty) as Paid_Qty,
            COUNT(DISTINCT sr.Invoice_No) as Total_Transactions,
            COUNT(DISTINCT CASE WHEN sr.Free_Qty > 0 THEN sr.Invoice_No END) as FOC_Transactions,
            ROUND(SUM(sr.Free_Qty) / NULLIF(SUM(sr.Quantity), 0) * 100, 2) as Overall_FOC_Pct,
            AVG(CASE WHEN sr.Free_Qty > 0 THEN sr.Free_Qty END) as Avg_FOC_When_Present
        FROM sales_raw sr
        LEFT JOIN location_master lm ON sr.Branch = lm.Branch
        WHERE sr.Quantity > 0 AND sr.Free_Qty >= 0
        GROUP BY sr.Branch, lm.Location
        ORDER BY Total_FOC_Qty DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_sales_by_branch").fetchone()[0]
    logger.log_table_info("foc_sales_by_branch", count)
    
    conn.execute("DROP TABLE IF EXISTS foc_sales_by_group")
    conn.execute("""
        CREATE TABLE foc_sales_by_group AS
        SELECT 
            im.Product_Group,
            SUM(s.Quantity) as Total_Qty_Sold,
            SUM(s.Free_Qty) as Total_FOC_Qty,
            SUM(s.Quantity) - SUM(s.Free_Qty) as Paid_Qty,
            COUNT(DISTINCT s.Invoice_No) as Total_Transactions,
            COUNT(DISTINCT CASE WHEN s.Free_Qty > 0 THEN s.Invoice_No END) as FOC_Transactions,
            ROUND(SUM(s.Free_Qty) / NULLIF(SUM(s.Quantity), 0) * 100, 2) as FOC_Percentage,
            SUM(s.Amount_USD) as Total_Revenue,
            SUM(s.Free_Qty * s.Price) as FOC_Revenue_Value,
            ROUND(SUM(s.Free_Qty * s.Price) / NULLIF(SUM(s.Amount_USD), 0) * 100, 2) as FOC_Value_Pct
        FROM sales_raw s
        LEFT JOIN item_master im ON s.Item_Code = im.Item_Code
        WHERE s.Quantity > 0 AND s.Free_Qty >= 0
        GROUP BY im.Product_Group
        ORDER BY Total_FOC_Qty DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM foc_sales_by_group").fetchone()[0]
    logger.log_table_info("foc_sales_by_group", count)
    
    logger.log("✅ FOC tables created successfully!", "SUCCESS")

# ============================================================================
# SUPPLIER-ENRICHED TABLES (unchanged)
# ============================================================================
def create_supplier_enriched_tables(conn):
    logger.log("🏢 Creating SUPPLIER-ENRICHED tables...", "PROGRESS")
    
    logger.log("  └─ Creating supplier_product_mapping...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_product_mapping")
    conn.execute("""
        CREATE TABLE supplier_product_mapping AS
        WITH item_suppliers AS (
            SELECT 
                Item_Code,
                Item_Name,
                Product_Group,
                Division,
                Brand_Name,
                unnest(All_Suppliers) as Supplier
            FROM item_master
            WHERE All_Suppliers IS NOT NULL
        ),
        purchase_suppliers AS (
            SELECT DISTINCT
                Item_Code,
                Vendor as Supplier,
                'purchase' as Source
            FROM purchase_all_clean
            WHERE Vendor IS NOT NULL AND Vendor != ''
        ),
        combined AS (
            SELECT 
                Item_Code,
                Item_Name,
                Product_Group,
                Division,
                Brand_Name,
                Supplier,
                'item_master' as Source,
                1 as Is_Primary
            FROM item_suppliers
            WHERE Supplier IS NOT NULL AND Supplier != ''
            UNION ALL
            SELECT 
                p.Item_Code,
                im.Item_Name,
                im.Product_Group,
                im.Division,
                im.Brand_Name,
                p.Supplier,
                'purchase_data' as Source,
                0 as Is_Primary
            FROM purchase_suppliers p
            LEFT JOIN item_master im ON p.Item_Code = im.Item_Code
            WHERE p.Supplier IS NOT NULL AND p.Supplier != ''
        )
        SELECT 
            Item_Code,
            Item_Name,
            Product_Group,
            Division,
            Brand_Name,
            Supplier,
            MAX(Is_Primary) as Is_Primary_Supplier,
            STRING_AGG(DISTINCT Source, ', ') as Sources
        FROM combined
        GROUP BY Item_Code, Item_Name, Product_Group, Division, Brand_Name, Supplier
        ORDER BY Item_Code, Supplier
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_product_mapping").fetchone()[0]
    logger.log_table_info("supplier_product_mapping", count)
    
    logger.log("  └─ Creating item_supplier_summary...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS item_supplier_summary")
    conn.execute("""
        CREATE TABLE item_supplier_summary AS
        SELECT 
            Item_Code,
            Item_Name,
            Product_Group,
            Division,
            Brand_Name,
            COUNT(DISTINCT Supplier) as Total_Suppliers,
            STRING_AGG(DISTINCT Supplier, ', ') as All_Supplier_Names,
            SUM(CASE WHEN Is_Primary_Supplier = 1 THEN 1 ELSE 0 END) as Has_Primary,
            CASE 
                WHEN COUNT(DISTINCT Supplier) = 0 THEN 'No Supplier'
                WHEN COUNT(DISTINCT Supplier) = 1 THEN 'Single Supplier'
                WHEN COUNT(DISTINCT Supplier) >= 3 THEN 'Multiple Suppliers (3+)'
                ELSE 'Multiple Suppliers'
            END as Supplier_Diversity
        FROM supplier_product_mapping
        GROUP BY Item_Code, Item_Name, Product_Group, Division, Brand_Name
        ORDER BY Total_Suppliers DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM item_supplier_summary").fetchone()[0]
    logger.log_table_info("item_supplier_summary", count)
    
    logger.log("  └─ Creating supplier_product_performance...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_product_performance")
    conn.execute("""
        CREATE TABLE supplier_product_performance AS
        SELECT 
            spm.Supplier,
            spm.Item_Code,
            spm.Item_Name,
            spm.Product_Group,
            spm.Division,
            spm.Is_Primary_Supplier,
            COALESCE(dd.Total_Sales, 0) as Total_Sales,
            COALESCE(dd.Total_Qty, 0) as Total_Qty,
            COALESCE(dd.Total_Transactions, 0) as Total_Transactions,
            COALESCE(pb.Total_Spend, 0) as Purchase_Spend,
            COALESCE(pb.Total_Qty, 0) as Purchase_Qty,
            COALESCE(pb.Purchase_Count, 0) as Purchase_Count,
            CASE 
                WHEN COALESCE(pb.Total_Qty, 0) > 0 
                THEN COALESCE(pb.Total_Spend, 0) / NULLIF(pb.Total_Qty, 0)
                ELSE NULL
            END as Avg_Purchase_Price
        FROM supplier_product_mapping spm
        LEFT JOIN item_total_summary dd ON spm.Item_Code = dd.Item_Code
        LEFT JOIN purchase_by_item pb ON spm.Item_Code = pb.Item_Code
        ORDER BY spm.Supplier, Total_Sales DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_product_performance").fetchone()[0]
    logger.log_table_info("supplier_product_performance", count)
    
    logger.log("  └─ Creating supplier_summary...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_summary")
    conn.execute("""
        CREATE TABLE supplier_summary AS
        SELECT 
            Supplier,
            COUNT(DISTINCT Item_Code) as Unique_Products,
            SUM(Total_Sales) as Total_Sales,
            SUM(Total_Qty) as Total_Qty,
            SUM(Total_Transactions) as Total_Transactions,
            SUM(Purchase_Spend) as Total_Purchase_Spend,
            SUM(Purchase_Qty) as Total_Purchase_Qty,
            SUM(Purchase_Count) as Total_Purchase_Transactions,
            COUNT(CASE WHEN Is_Primary_Supplier = 1 THEN 1 END) as Primary_Products,
            AVG(Avg_Purchase_Price) as Avg_Purchase_Price,
            COUNT(DISTINCT Product_Group) as Product_Groups
        FROM supplier_product_performance
        GROUP BY Supplier
        ORDER BY Total_Purchase_Spend DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_summary").fetchone()[0]
    logger.log_table_info("supplier_summary", count)
    
    logger.log("  └─ Creating supplier_purchase_detail...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_purchase_detail")
    conn.execute("""
        CREATE TABLE supplier_purchase_detail AS
        SELECT 
            p.Vendor as Supplier,
            p.Item_Code,
            p.Item_Name,
            p.Purchase_Type,
            p.Purchase_Date,
            p.Qty as Purchase_Qty,
            p.Amount_USD as Purchase_Amount,
            p.Supplier_Rate as Unit_Cost,
            p.Country,
            p.Unit,
            p.FOC_Qty,
            im.Product_Group,
            im.Division,
            im.Brand_Name
        FROM purchase_all_clean p
        LEFT JOIN item_master im ON UPPER(p.Item_Code) = UPPER(im.Item_Code)
        ORDER BY p.Vendor, p.Purchase_Date DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_purchase_detail").fetchone()[0]
    logger.log_table_info("supplier_purchase_detail", count)
    
    logger.log("  └─ Creating supplier_purchase_summary...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_purchase_summary")
    conn.execute("""
        CREATE TABLE supplier_purchase_summary AS
        SELECT 
            Supplier,
            COUNT(DISTINCT Item_Code) as Total_Products_Purchased,
            SUM(Purchase_Qty) as Total_Purchase_Qty,
            SUM(Purchase_Amount) as Total_Purchase_Amount,
            COUNT(*) as Total_Transactions,
            AVG(Unit_Cost) as Avg_Unit_Cost,
            MIN(Purchase_Date) as First_Purchase_Date,
            MAX(Purchase_Date) as Last_Purchase_Date,
            COUNT(DISTINCT Purchase_Type) as Purchase_Types,
            COUNT(DISTINCT Country) as Countries
        FROM supplier_purchase_detail
        GROUP BY Supplier
        ORDER BY Total_Purchase_Amount DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_purchase_summary").fetchone()[0]
    logger.log_table_info("supplier_purchase_summary", count)
    
    logger.log("  └─ Creating supplier_purchase_by_item...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_purchase_by_item")
    conn.execute("""
        CREATE TABLE supplier_purchase_by_item AS
        SELECT 
            Supplier,
            Item_Code,
            Item_Name,
            Product_Group,
            Division,
            Brand_Name,
            SUM(Purchase_Qty) as Total_Purchase_Qty,
            SUM(Purchase_Amount) as Total_Purchase_Amount,
            COUNT(*) as Transaction_Count,
            AVG(Unit_Cost) as Avg_Unit_Cost,
            MIN(Purchase_Date) as First_Purchase,
            MAX(Purchase_Date) as Last_Purchase,
            COUNT(DISTINCT Country) as Countries_Sourced
        FROM supplier_purchase_detail
        GROUP BY Supplier, Item_Code, Item_Name, Product_Group, Division, Brand_Name
        ORDER BY Supplier, Total_Purchase_Amount DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_purchase_by_item").fetchone()[0]
    logger.log_table_info("supplier_purchase_by_item", count)
    
    logger.log("  └─ Creating supplier_purchase_monthly...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_purchase_monthly")
    conn.execute("""
        CREATE TABLE supplier_purchase_monthly AS
        SELECT 
            Supplier,
            STRFTIME(Purchase_Date, '%Y-%m') as Month_Label,
            EXTRACT(YEAR FROM Purchase_Date) as Year,
            EXTRACT(MONTH FROM Purchase_Date) as Month_Num,
            SUM(Purchase_Qty) as Monthly_Purchase_Qty,
            SUM(Purchase_Amount) as Monthly_Purchase_Amount,
            COUNT(*) as Transaction_Count,
            COUNT(DISTINCT Item_Code) as Unique_Items_Purchased
        FROM supplier_purchase_detail
        GROUP BY Supplier, STRFTIME(Purchase_Date, '%Y-%m'), EXTRACT(YEAR FROM Purchase_Date), EXTRACT(MONTH FROM Purchase_Date)
        ORDER BY Supplier, Year, Month_Num
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_purchase_monthly").fetchone()[0]
    logger.log_table_info("supplier_purchase_monthly", count)
    
    logger.log("  └─ Creating supplier_purchase_top_items...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_purchase_top_items")
    conn.execute("""
        CREATE TABLE supplier_purchase_top_items AS
        SELECT 
            Supplier,
            Item_Code,
            Item_Name,
            Product_Group,
            Total_Purchase_Qty,
            Total_Purchase_Amount,
            Avg_Unit_Cost,
            Transaction_Count,
            RANK() OVER (PARTITION BY Supplier ORDER BY Total_Purchase_Amount DESC) as Rank_By_Amount,
            RANK() OVER (PARTITION BY Supplier ORDER BY Total_Purchase_Qty DESC) as Rank_By_Qty
        FROM supplier_purchase_by_item
        ORDER BY Supplier, Rank_By_Amount
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_purchase_top_items").fetchone()[0]
    logger.log_table_info("supplier_purchase_top_items", count)
    
    logger.log("  └─ Creating demand_plan_with_suppliers...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS demand_plan_with_suppliers")
    conn.execute("""
        CREATE TABLE demand_plan_with_suppliers AS
        SELECT 
            d.Item_Code,
            d.Item_Name,
            d.Product_Group,
            d.Total_Revenue,
            d.Total_Qty,
            d.Avg_Revenue,
            d.Revenue_StdDev,
            d.Active_Months,
            d.Last_Sale_Month,
            d.First_Sale_Month,
            d.Demand_Stability_Index,
            im.Division,
            im.Brand_Name,
            COALESCE(iss.Total_Suppliers, 0) as Total_Suppliers,
            COALESCE(iss.All_Supplier_Names, 'No Supplier') as All_Supplier_Names,
            COALESCE(iss.Supplier_Diversity, 'No Supplier') as Supplier_Diversity,
            COALESCE(iss.Has_Primary, 0) as Has_Primary,
            im.Primary_Supplier,
            CASE 
                WHEN im.Primary_Supplier IS NOT NULL AND im.Primary_Supplier != '' THEN im.Primary_Supplier
                WHEN iss.Total_Suppliers > 0 THEN (SELECT Supplier FROM supplier_product_mapping WHERE Item_Code = d.Item_Code LIMIT 1)
                ELSE 'No Supplier'
            END as Main_Supplier,
            s.Total_Sales as Supplier_Total_Sales,
            s.Unique_Products as Supplier_Product_Count,
            s.Primary_Products as Supplier_Primary_Product_Count,
            s.Product_Groups as Supplier_Product_Groups,
            CASE 
                WHEN s.Unique_Products IS NOT NULL AND s.Unique_Products > 0 
                THEN s.Total_Sales / NULLIF(s.Unique_Products, 0)
                ELSE NULL
            END as Supplier_Avg_Product_Sales,
            s.Avg_Purchase_Price as Supplier_Avg_Purchase_Price
        FROM item_demand d
        LEFT JOIN item_supplier_summary iss ON d.Item_Code = iss.Item_Code
        LEFT JOIN item_master im ON d.Item_Code = im.Item_Code
        LEFT JOIN supplier_summary s ON COALESCE(im.Primary_Supplier, 
            (SELECT Supplier FROM supplier_product_mapping WHERE Item_Code = d.Item_Code LIMIT 1)) = s.Supplier
        ORDER BY d.Total_Revenue DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM demand_plan_with_suppliers").fetchone()[0]
    logger.log_table_info("demand_plan_with_suppliers", count)
    
    logger.log("  └─ Creating supplier_demand_forecast...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_demand_forecast")
    conn.execute("""
        CREATE TABLE supplier_demand_forecast AS
        SELECT 
            spp.Supplier,
            COUNT(DISTINCT spp.Item_Code) as Total_Items,
            SUM(COALESCE(d.Total_Revenue, 0)) as Total_Revenue,
            SUM(COALESCE(d.Total_Qty, 0)) as Total_Qty,
            AVG(d.Demand_Stability_Index) as Avg_Stability,
            SUM(CASE WHEN d.Demand_Stability_Index > 0.5 THEN 1 ELSE 0 END) as Stable_Items,
            SUM(CASE WHEN d.Demand_Stability_Index <= 0.5 AND d.Demand_Stability_Index > 0 THEN 1 ELSE 0 END) as Variable_Items,
            SUM(CASE WHEN d.Demand_Stability_Index IS NULL THEN 1 ELSE 0 END) as Unknown_Stability,
            SUM(spp.Purchase_Spend) as Supplier_Total_Purchase,
            SUM(spp.Purchase_Qty) as Supplier_Total_Qty_Purchased,
            SUM(CASE WHEN spp.Is_Primary_Supplier = 1 THEN 1 ELSE 0 END) as Primary_Products,
            AVG(spp.Avg_Purchase_Price) as Avg_Purchase_Price,
            COUNT(DISTINCT spp.Product_Group) as Product_Groups
        FROM supplier_product_performance spp
        LEFT JOIN item_demand d ON spp.Item_Code = d.Item_Code
        GROUP BY spp.Supplier
        ORDER BY Supplier_Total_Purchase DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_demand_forecast").fetchone()[0]
    logger.log_table_info("supplier_demand_forecast", count)
    
    logger.log("  └─ Creating supplier_risk_analysis...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_risk_analysis")
    conn.execute("""
        CREATE TABLE supplier_risk_analysis AS
        WITH supplier_metrics AS (
            SELECT 
                spm.Supplier,
                COUNT(DISTINCT spm.Item_Code) as Product_Count,
                SUM(COALESCE(spp.Purchase_Spend, 0)) as Total_Purchase_Spend,
                SUM(COALESCE(spp.Purchase_Qty, 0)) as Total_Purchase_Qty,
                SUM(COALESCE(d.Total_Revenue, 0)) as Total_Revenue,
                SUM(COALESCE(d.Total_Qty, 0)) as Total_Qty,
                COUNT(DISTINCT spm.Product_Group) as Product_Groups,
                SUM(CASE WHEN spm.Is_Primary_Supplier = 1 THEN 1 ELSE 0 END) as Primary_Product_Count,
                COUNT(DISTINCT CASE WHEN d.Demand_Stability_Index <= 0.3 THEN spm.Item_Code END) as High_Risk_Products,
                COUNT(DISTINCT CASE WHEN d.Demand_Stability_Index BETWEEN 0.3 AND 0.7 THEN spm.Item_Code END) as Medium_Risk_Products,
                COUNT(DISTINCT CASE WHEN d.Demand_Stability_Index > 0.7 THEN spm.Item_Code END) as Low_Risk_Products,
                SUM(CASE WHEN d.Total_Qty > 0 AND spm.Is_Primary_Supplier = 1 THEN 1 ELSE 0 END) as Primary_Active_Products
            FROM supplier_product_mapping spm
            LEFT JOIN supplier_product_performance spp ON spm.Item_Code = spp.Item_Code AND spm.Supplier = spp.Supplier
            LEFT JOIN item_demand d ON spm.Item_Code = d.Item_Code
            GROUP BY spm.Supplier
        )
        SELECT 
            Supplier,
            Product_Count,
            Total_Revenue,
            Total_Qty,
            Product_Groups,
            Primary_Product_Count,
            Primary_Active_Products,
            High_Risk_Products,
            Medium_Risk_Products,
            Low_Risk_Products,
            Total_Purchase_Spend,
            Total_Purchase_Qty,
            CASE 
                WHEN Total_Purchase_Spend > (SELECT AVG(Total_Purchase_Spend) FROM supplier_metrics WHERE Total_Purchase_Spend > 0) * 2 THEN 'HIGH_SPEND'
                WHEN Total_Purchase_Spend > (SELECT AVG(Total_Purchase_Spend) FROM supplier_metrics WHERE Total_Purchase_Spend > 0) THEN 'MEDIUM_SPEND'
                ELSE 'LOW_SPEND'
            END as Spend_Category,
            CASE 
                WHEN High_Risk_Products > Product_Count * 0.3 THEN 'HIGH_RISK'
                WHEN High_Risk_Products > Product_Count * 0.15 THEN 'MEDIUM_RISK'
                ELSE 'LOW_RISK'
            END as Risk_Level,
            CASE 
                WHEN Primary_Product_Count = 0 THEN 'No_Primary'
                WHEN Primary_Product_Count = Product_Count THEN 'All_Primary'
                WHEN Primary_Product_Count > Product_Count * 0.5 THEN 'Mostly_Primary'
                ELSE 'Few_Primary'
            END as Primary_Supplier_Status
        FROM supplier_metrics
        ORDER BY Total_Purchase_Spend DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_risk_analysis").fetchone()[0]
    logger.log_table_info("supplier_risk_analysis", count)

    logger.log("  └─ Creating supplier_product_demand...", "PROGRESS")
    conn.execute("DROP TABLE IF EXISTS supplier_product_demand")
    conn.execute("""
        CREATE TABLE supplier_product_demand AS
        SELECT 
            spm.Supplier,
            spm.Item_Code,
            spm.Item_Name,
            spm.Product_Group,
            spm.Division,
            spm.Is_Primary_Supplier,
            d.Total_Revenue,
            d.Total_Qty,
            d.Avg_Revenue,
            d.Revenue_StdDev,
            d.Active_Months,
            d.Demand_Stability_Index,
            CASE 
                WHEN d.Demand_Stability_Index > 0.5 THEN 'STABLE'
                WHEN d.Demand_Stability_Index > 0.2 THEN 'VARIABLE'
                ELSE 'VOLATILE'
            END as Demand_Stability,
            CASE 
                WHEN d.Total_Revenue > (SELECT AVG(Total_Revenue) FROM item_demand) 
                     AND d.Demand_Stability_Index > 0.5 THEN 'HIGH_VALUE_STABLE'
                WHEN d.Total_Revenue > (SELECT AVG(Total_Revenue) FROM item_demand) 
                     AND d.Demand_Stability_Index <= 0.5 THEN 'HIGH_VALUE_VARIABLE'
                WHEN d.Total_Revenue <= (SELECT AVG(Total_Revenue) FROM item_demand) 
                     AND d.Demand_Stability_Index > 0.5 THEN 'LOW_VALUE_STABLE'
                ELSE 'LOW_VALUE_VARIABLE'
            END as Demand_Classification,
            COALESCE(pb.Total_Spend, 0) as Purchase_Spend,
            COALESCE(pb.Total_Qty, 0) as Purchase_Qty
        FROM supplier_product_mapping spm
        LEFT JOIN item_demand d ON spm.Item_Code = d.Item_Code
        LEFT JOIN purchase_by_item pb ON spm.Item_Code = pb.Item_Code
        ORDER BY spm.Supplier, d.Total_Revenue DESC
    """)
    count = conn.execute("SELECT COUNT(*) FROM supplier_product_demand").fetchone()[0]
    logger.log_table_info("supplier_product_demand", count)

    coverage_summary = conn.execute("""
        SELECT 
            COUNT(DISTINCT Supplier) as total_suppliers,
            COUNT(DISTINCT Item_Code) as total_products,
            SUM(CASE WHEN Is_Primary_Supplier = 1 THEN 1 ELSE 0 END) as primary_supplier_relationships
        FROM supplier_product_mapping
    """).fetchone()
    
    logger.log(f"  └─ Supplier Coverage Summary:", "DATA")
    logger.log(f"     - Total Suppliers: {coverage_summary[0]:,}", "DATA")
    logger.log(f"     - Total Product-Supplier Relationships: {coverage_summary[1]:,}", "DATA")
    logger.log(f"     - Primary Supplier Relationships: {coverage_summary[2]:,}", "DATA")

    diversity_summary = conn.execute("""
        SELECT 
            Supplier_Diversity,
            COUNT(*) as item_count
        FROM item_supplier_summary
        GROUP BY Supplier_Diversity
        ORDER BY item_count DESC
    """).df()
    
    logger.log(f"  └─ Supplier Diversity Summary:", "DATA")
    for _, row in diversity_summary.iterrows():
        logger.log(f"     - {row['Supplier_Diversity']}: {row['item_count']:,} items", "DATA")

# ============================================================================
# VALIDATION
# ============================================================================
def validate_data():
    logger.log("="*80, "INFO", False)
    logger.log("🔍 VALIDATING DATA INTEGRITY", "PROGRESS")
    logger.log("="*80, "INFO", False)
    conn = duckdb.connect(DB_PATH)
    try:
        tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name").df()
        logger.log("📋 ALL TABLES:", "DATA")
        for _, row in tables.iterrows():
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {row['table_name']}").fetchone()[0]
                logger.log(f"  ✅ {row['table_name']}: {count:,} records", "INFO", False)
            except:
                logger.log(f"  ❌ {row['table_name']}: Error", "WARNING", False)
        
        foc_tables = ['foc_sales_summary', 'foc_sales_monthly', 'foc_purchase_summary', 
                      'foc_purchase_monthly', 'foc_sales_outliers', 'foc_purchase_outliers',
                      'foc_demand_impact', 'foc_sales_by_branch', 'foc_sales_by_group']
        logger.log("🎯 FOC TABLES:", "DATA")
        for table in foc_tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                logger.log(f"  ✅ {table}: {count:,} records", "INFO", False)
            except:
                logger.log(f"  ❌ {table}: Not found", "WARNING", False)
        
        safety_tables = ['safety_stock_by_supplier', 'safety_stock_by_item', 'safety_stock_summary']
        logger.log("🛡️ SAFETY STOCK TABLES:", "DATA")
        for table in safety_tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                logger.log(f"  ✅ {table}: {count:,} records", "INFO", False)
            except:
                logger.log(f"  ❌ {table}: Not found", "WARNING", False)
        
        try:
            count = conn.execute("SELECT COUNT(*) FROM supplier_master").fetchone()[0]
            logger.log(f"  ✅ supplier_master: {count:,} records", "INFO", False)
        except:
            logger.log(f"  ❌ supplier_master: Not found", "WARNING", False)
                
    except Exception as e:
        logger.log(f"Validation error: {e}", "ERROR")
        traceback.print_exc()
    conn.close()
    logger.log("✅ Validation complete", "SUCCESS")

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("\n" + "="*80)
    print("💊 PHARMA BI - COMPLETE MIGRATION (FIXED)")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print(f"Log file: {logger.log_file}")
    print("="*80 + "\n")
    
    try:
        logger.log("📊 PROCESSING SALES FILES...", "PROGRESS")
        sales_processor = IncrementalFileProcessor()
        sales_processor.process_sales_files()
        
        logger.log("🔄 PROCESSING RETURNS FILES...", "PROGRESS")
        sales_processor.process_returns_file()
        
        logger.log("📦 PROCESSING STOCK FILES...", "PROGRESS")
        stock_processor = StockFileProcessor()
        stock_df = stock_processor.process_stock_files()
        
        logger.log("🛒 PROCESSING LOCAL PURCHASE FILES (CLEAN)...", "PROGRESS")
        local_processor = LocalPurchaseProcessor()
        local_df = local_processor.process_files()
        
        logger.log("🔄 EXTRACTING PURCHASE RETURNS...", "PROGRESS")
        returns_processor = PurchaseReturnProcessor()
        returns_df = returns_processor.process_returns_from_files()
        
        logger.log("🛒 PROCESSING IMPORT PURCHASE FILES...", "PROGRESS")
        import_processor = ImportPurchaseProcessor()
        import_df = import_processor.process_files()
        
        logger.log("📄 PROCESSING PRF/PO FILE...", "PROGRESS")
        prf_processor = PRFPOProcessor()
        prf_df = prf_processor.process_file()
        
        logger.log("🏢 PROCESSING SUPPLIER MASTER FILE...", "PROGRESS")
        supplier_processor = SupplierMasterProcessor()
        supplier_df = supplier_processor.process_file()
        
        logger.log("🏗️ BUILDING DATABASE TABLES...", "PROGRESS")
        conn = duckdb.connect(DB_PATH)
        conn.execute("PRAGMA memory_limit='4GB'")
        
        create_master_tables(conn)
        rebuild_aggregated_tables(conn)
        create_pre_aggregated_summaries(conn)
        create_instant_filter_tables(conn)
        create_branch_item_monthly_summary(conn)
        create_decision_support_tables(conn)
        create_all_pivot_tables(conn)
        create_demand_planning_tables(conn)
        create_stock_tables(conn, stock_df)
        create_stock_health_dashboard(conn)
        create_branch_item_monthly_analysis(conn)
        create_current_stock_recommendations(conn)
        create_stock_status_summary(conn)
        create_monthly_stock(conn)
        create_purchase_tables(conn, local_df, import_df, returns_df)
        create_prf_po_tables(conn, prf_df)
        create_foc_tables(conn)
        create_supplier_enriched_tables(conn)
        create_supplier_master_tables(conn, supplier_df)
        create_safety_stock_tables(conn)
        
        conn.close()
        validate_data()
        logger.save_summary()
        
        print("\n" + "="*80)
        print(f"✅ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        print(f"📄 Log file: {logger.log_file}")
        print("\n📌 Now run your dashboard: streamlit run app.py")
        print("="*80)
        
    except Exception as e:
        logger.log(f"❌ Migration failed: {e}", "ERROR")
        traceback.print_exc()
        logger.save_summary()
