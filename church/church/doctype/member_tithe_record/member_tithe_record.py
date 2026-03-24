# Copyright (c) 2026, kunle and contributors
# For license information, please see license.txt



from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, nowdate, get_datetime


class MemberTitheRecord(Document):
    """
    Manages tithe payment records for church members.
    Automatically syncs with Receipt entries and calculates totals.
    """
    
    def validate(self):
        """Validation before saving"""
        self.validate_member()
        self.sync_tithe_payments()
        self.calculate_totals()
        self.update_currency()
    
    def validate_member(self):
        """Ensure member exists and fetch details"""
        if not self.member_id:
            frappe.throw(_("Member ID is required"))
        
        # Auto-fetch member details if not present
        if not self.full_name or not self.salutation:
            member = frappe.get_doc("Member", self.member_id)
            self.full_name = member.full_name
            self.salutation = member.salutation
            if not self.branch:
                self.branch = member.branch
    
    def sync_tithe_payments(self):
        """
        Automatically sync tithe payments from Receipts.
        Only adds new receipts that aren't already in the schedule.
        """
        if not self.member_id:
            return
        
        # Get existing receipt numbers for quick lookup
        existing_receipts = {row.receipt_no for row in self.tithe_payment_schedule if row.receipt_no}
        
        # Fetch all Member Tithe receipts for this member
        receipts = frappe.get_all(
            "Receipts",
            filters={
                "member_id": self.member_id,
                "transaction_type": "Member Tithe",
                "docstatus": ["<", 2]  # Include draft and submitted, exclude cancelled
            },
            fields=[
                "name", "transaction_date", "member_full_name", 
                "remittance_bank", "branch", "receipt_currency", 
                "exchange_rate", "amount_paid", "amount_paid_in_fc"
            ],
            order_by="transaction_date asc"
        )
        
        # Add new receipts to the schedule
        new_count = 0
        for receipt in receipts:
            if receipt.name not in existing_receipts:
                self.add_tithe_payment(receipt)
                new_count += 1
        
        if new_count > 0:
            frappe.msgprint(_("{0} new tithe payment(s) added").format(new_count))
    
    def add_tithe_payment(self, receipt):
        """Add a single tithe payment to the schedule"""
        currency = receipt.receipt_currency or "NGN"
        exchange_rate = flt(receipt.exchange_rate, 2) or 1.0
        
        # Determine amount based on currency
        if currency == "NGN":
            amount_paid = flt(receipt.amount_paid, 2)
        else:
            amount_paid = flt(receipt.amount_paid_in_fc, 2)
        
        # Calculate amount in local currency
        amount_in_lc = flt(amount_paid * exchange_rate, 2)
        
        # Append to child table
        self.append("tithe_payment_schedule", {
            "date": receipt.transaction_date,
            "full_name": receipt.member_full_name,
            "receipt_no": receipt.name,
            "designated_bank_acct": receipt.remittance_bank,
            "branch": receipt.branch,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "amount_paid": amount_paid,
            "amount_in_lc": amount_in_lc
        })
    
    def calculate_totals(self):
        """Calculate total amount paid from all payment schedules"""
        total = 0
        
        for row in self.tithe_payment_schedule:
            # Recalculate amount_in_lc if exchange rate changed
            if row.amount_paid and row.exchange_rate:
                row.amount_in_lc = flt(row.amount_paid * row.exchange_rate, 2)
                total += row.amount_in_lc
        
        self.amount_paid = flt(total, 2)
    
    def update_currency(self):
        """Set default currency if not specified"""
        if not self.currency:
            self.currency = frappe.db.get_single_value("Company", "default_currency") or "NGN"


# ========================================
# WHITELISTED API METHODS
# ========================================

@frappe.whitelist()
def sync_tithe_payments(member_tithe_record_name):
    """
    Manually sync tithe payments for a specific record.
    Called from the "Update Tithe Record" button.
    """
    try:
        doc = frappe.get_doc("Member Tithe Record", member_tithe_record_name)
        doc.sync_tithe_payments()
        doc.calculate_totals()
        doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        return {
            "success": True,
            "message": _("Tithe record updated successfully"),
            "total_amount": doc.amount_paid
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sync Tithe Payments Error")
        frappe.throw(_("Error updating tithe record: {0}").format(str(e)))


@frappe.whitelist()
def get_member_tithe_summary(member_id):
    """Get summary of member's tithe payments"""
    if not member_id:
        return {}
    
    record = frappe.db.get_value(
        "Member Tithe Record",
        {"member_id": member_id},
        ["name", "amount_paid", "currency"],
        as_dict=True
    )
    
    if not record:
        return {
            "exists": False,
            "total_paid": 0
        }
    
    # Get payment count
    payment_count = frappe.db.count(
        "Tithe Payment Schedule",
        {"parent": record.name}
    )
    
    return {
        "exists": True,
        "record_name": record.name,
        "total_paid": record.amount_paid,
        "currency": record.currency,
        "payment_count": payment_count
    }


# ========================================
# SCHEDULED JOBS
# ========================================

def sync_all_tithe_records():
    """
    Scheduled job to sync all member tithe records.
    Run daily or after bulk receipt creation.
    Configured in hooks.py
    """
    try:
        # Get all Member Tithe Records
        records = frappe.get_all("Member Tithe Record", fields=["name", "member_id"])
        
        success_count = 0
        error_count = 0
        
        for record_info in records:
            try:
                doc = frappe.get_doc("Member Tithe Record", record_info.name)
                
                # Store current count
                old_count = len(doc.tithe_payment_schedule)
                
                # Sync and save
                doc.sync_tithe_payments()
                doc.calculate_totals()
                doc.save(ignore_permissions=True)
                
                # Check if any new records added
                new_count = len(doc.tithe_payment_schedule)
                if new_count > old_count:
                    success_count += 1
                
            except Exception as e:
                error_count += 1
                frappe.log_error(
                    f"Error syncing Member ID {record_info.member_id}: {str(e)}",
                    "Tithe Sync Error"
                )
        
        # Commit all changes
        frappe.db.commit()
        
        # Log summary
        message = f"Tithe sync completed. Updated: {success_count}, Errors: {error_count}"
        frappe.logger().info(message)
        
        return {
            "success": True,
            "updated": success_count,
            "errors": error_count
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sync All Tithe Records Failed")
        return {
            "success": False,
            "error": str(e)
        }


def create_missing_tithe_records():
    """
    Create Member Tithe Records for members who have tithe receipts but no record.
    Run weekly to ensure all members with tithes have a record.
    """
    try:
        # Get all members who have tithe receipts but no tithe record
        members_with_tithes = frappe.db.sql("""
            SELECT DISTINCT r.member_id, m.full_name, m.salutation, m.branch
            FROM `tabReceipts` r
            INNER JOIN `tabMember` m ON r.member_id = m.name
            LEFT JOIN `tabMember Tithe Record` mtr ON r.member_id = mtr.member_id
            WHERE r.transaction_type = 'Member Tithe'
            AND r.docstatus < 2
            AND mtr.name IS NULL
        """, as_dict=True)
        
        created_count = 0
        
        for member in members_with_tithes:
            try:
                # Create new tithe record
                new_record = frappe.get_doc({
                    "doctype": "Member Tithe Record",
                    "member_id": member.member_id,
                    "full_name": member.full_name,
                    "salutation": member.salutation,
                    "branch": member.branch
                })
                
                new_record.insert(ignore_permissions=True)
                created_count += 1
                
            except Exception as e:
                frappe.log_error(
                    f"Error creating tithe record for {member.member_id}: {str(e)}",
                    "Create Tithe Record Error"
                )
        
        frappe.db.commit()
        
        message = f"Created {created_count} missing tithe records"
        frappe.logger().info(message)
        
        return {
            "success": True,
            "created": created_count
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Missing Tithe Records Failed")
        return {
            "success": False,
            "error": str(e)
        }


# ========================================
# RECEIPT CREATION FROM TITHE BATCH
# ========================================

def create_receipts_from_batch(batch_doc):
    """
    Create individual receipts from Tithe Batch Update.
    This is called from Tithe Batch Update's server script.
    """
    if not batch_doc.tithe_transaction_entry:
        frappe.msgprint(_("No tithe transactions to process"))
        return
    
    created_receipts = []
    skipped_receipts = []
    
    for row in batch_doc.tithe_transaction_entry:
        # Check if receipt already exists
        if frappe.db.exists("Receipts", {"referenced_document_no": row.name}):
            skipped_receipts.append(row.name)
            continue
        
        try:
            # Determine currency and amounts
            currency = row.currency or batch_doc.currency or "NGN"
            is_local_currency = currency == "NGN"
            exchange_rate = 1.0 if is_local_currency else flt(row.exchange_rate, 2)
            
            # Create receipt
            receipt = frappe.get_doc({
                "doctype": "Receipts",
                "naming_series": "REC #-",
                "transaction_date": row.date or nowdate(),
                "transaction_type": "Member Tithe",
                "member_id": row.member_id,
                "branch": row.branch or batch_doc.branch,
                "create_accounting_entries": 1,
                "source": row.type,
                "transaction_purposes": f"Member's Tithe - {row.type}",
                "receipt_currency": currency,
                "exchange_rate": exchange_rate,
                "amount_paid": flt(row.amount_paid, 2) if is_local_currency else 0,
                "amount_paid_in_fc": flt(row.amount_paid, 2) if not is_local_currency else 0,
                "mode_of_payment": "Wire Transfer",
                "reference_no": row.name.upper(),
                "referenced_document_no": row.name.upper(),
                "remittance_bank": batch_doc.designated_bank_acct
            })
            
            receipt.insert(ignore_permissions=True)
            created_receipts.append(receipt.name)
            
        except Exception as e:
            frappe.log_error(
                f"Error creating receipt for {row.name}: {str(e)}",
                "Batch Receipt Creation Error"
            )
    
    # Summary message
    if created_receipts:
        frappe.msgprint(
            _("{0} receipt(s) created successfully").format(len(created_receipts)),
            indicator="green"
        )
    
    if skipped_receipts:
        frappe.msgprint(
            _("{0} receipt(s) skipped (already exist)").format(len(skipped_receipts)),
            indicator="orange"
        )
    
    return {
        "created": created_receipts,
        "skipped": skipped_receipts
    }
    


def on_receipt_created(doc, method):
    """
    Called when a new Receipt is created.
    Automatically updates the member's tithe record.
    """
    if doc.transaction_type != "Member Tithe":
        return
    
    if not doc.member_id:
        return
    
    try:
        # Create tithe record if it doesn't exist
        if not frappe.db.exists("Member Tithe Record", {"member_id": doc.member_id}):
            create_tithe_record_for_member(doc.member_id)
        
        # Sync the tithe record
        sync_member_tithe_record(doc.member_id)
        
    except Exception as e:
        frappe.log_error(
            f"Error in on_receipt_created for {doc.name}: {str(e)}",
            "Tithe Record Event Error"
        )


def on_receipt_updated(doc, method):
    """
    Called when a Receipt is updated.
    Updates the corresponding tithe record entry.
    """
    if doc.transaction_type != "Member Tithe":
        return
    
    if not doc.member_id:
        return
    
    try:
        sync_member_tithe_record(doc.member_id)
    except Exception as e:
        frappe.log_error(
            f"Error in on_receipt_updated for {doc.name}: {str(e)}",
            "Tithe Record Event Error"
        )


def on_receipt_submitted(doc, method):
    """Called when a Receipt is submitted"""
    on_receipt_updated(doc, method)


def on_receipt_cancelled(doc, method):
    """
    Called when a Receipt is cancelled.
    Removes the entry from tithe record.
    """
    if doc.transaction_type != "Member Tithe":
        return
    
    if not doc.member_id:
        return
    
    try:
        # Find and remove the cancelled receipt from tithe record
        tithe_record_name = frappe.db.get_value(
            "Member Tithe Record",
            {"member_id": doc.member_id},
            "name"
        )
        
        if tithe_record_name:
            tithe_record = frappe.get_doc("Member Tithe Record", tithe_record_name)
            
            # Remove the cancelled receipt
            tithe_record.tithe_payment_schedule = [
                row for row in tithe_record.tithe_payment_schedule 
                if row.receipt_no != doc.name
            ]
            
            # Recalculate totals
            tithe_record.calculate_totals()
            tithe_record.save(ignore_permissions=True)
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(
            f"Error in on_receipt_cancelled for {doc.name}: {str(e)}",
            "Tithe Record Event Error"
        )


def sync_member_tithe_record(member_id):
    """Helper function to sync a single member's tithe record"""
    tithe_record_name = frappe.db.get_value(
        "Member Tithe Record",
        {"member_id": member_id},
        "name"
    )
    
    if tithe_record_name:
        doc = frappe.get_doc("Member Tithe Record", tithe_record_name)
        doc.sync_tithe_payments()
        doc.calculate_totals()
        doc.save(ignore_permissions=True)
        frappe.db.commit()


def create_tithe_record_for_member(member_id):
    """Helper function to create a tithe record for a member"""
    member = frappe.get_doc("Member", member_id)
    
    new_record = frappe.get_doc({
        "doctype": "Member Tithe Record",
        "member_id": member_id,
        "full_name": member.full_name,
        "salutation": member.salutation,
        "branch": member.branch
    })
    
    new_record.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return new_record.name