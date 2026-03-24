
import frappe
from frappe.utils.file_manager import get_file
from frappe.utils import getdate, cstr
import openpyxl
import os
import csv

@frappe.whitelist()
def import_bank_statement_from_excel(bank_reconciliation, attached_file_name):
    """
    Import bank statement data from attached Excel or CSV file to bank_statement table
    Args:
        bank_reconciliation: Name of the Bank Reconciliation document
        attached_file_name: Name of the attached Excel or CSV file
    """
    try:
        # Get the attached file
        file_data = get_file(attached_file_name)
        file_path = file_data[1]
        ext = os.path.splitext(file_path)[1].lower()

        # Read data from file
        data_rows = []
        headers = []

        if ext in [".xlsx", ".xlsm", ".xltx", ".xltm"]:
            workbook = openpyxl.load_workbook(file_path)
            sheet = workbook.active

            headers = [cstr(cell.value).strip().lower().replace(" ", "_") for cell in sheet[1]]

            for row in sheet.iter_rows(min_row=2):
                row_data = {}
                for idx, cell in enumerate(row):
                    if idx < len(headers):
                        row_data[headers[idx]] = cell.value
                if any(row_data.values()):
                    data_rows.append(row_data)

        elif ext == ".csv":
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                headers = [cstr(h).strip().lower().replace(" ", "_") for h in reader.fieldnames]
                for row in reader:
                    normalized_row = {}
                    for key, value in row.items():
                        normalized_key = cstr(key).strip().lower().replace(" ", "_")
                        normalized_row[normalized_key] = value
                    if any(normalized_row.values()):
                        data_rows.append(normalized_row)

        else:
            frappe.throw("Unsupported file format. Please upload a .xlsx, .xlsm, or .csv file.")

        # Validate required columns
        required_columns = ['posting_date', 'party', 'debit_amount', 'credit_amount', 'voucher_no', 'cheque_no']
        for col in required_columns:
            if col not in headers:
                frappe.throw(f"Required column '{col}' not found in the file.")

        # Preprocess data
        for row in data_rows:
            if 'posting_date' in row and row['posting_date']:
                row['posting_date'] = getdate(row['posting_date'])

            if 'debit_amount' in row:
                row['debit_amount'] = float(row['debit_amount'] or 0)

            if 'credit_amount' in row:
                row['credit_amount'] = float(row['credit_amount'] or 0)

        # Add to Bank Reconciliation
        doc = frappe.get_doc("Bank Reconciliation", bank_reconciliation)
        for row in data_rows:
            doc.append("bank_statement", {
                "posting_date": row.get("posting_date"),
                "party": row.get("party"),
                "debit_amount": row.get("debit_amount", 0),
                "credit_amount": row.get("credit_amount", 0),
                "voucher_no": row.get("voucher_no"),
                "cheque_no": row.get("cheque_no")
            })

        doc.save()
        frappe.db.commit()

        return {
            "success": True,
            "message": f"Successfully imported {len(data_rows)} records from the file."
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Bank Reconciliation Import Error")
        return {
            "success": False,
            "message": f"Error importing data: {str(e)}"
        }
