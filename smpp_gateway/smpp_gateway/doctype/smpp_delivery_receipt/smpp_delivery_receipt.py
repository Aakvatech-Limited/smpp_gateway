# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now

class SMPPDeliveryReceipt(Document):
    def validate(self):
        self.validate_original_message()
        self.set_processed_time()
    
    def on_update(self):
        self.update_original_message_status()
    
    def validate_original_message(self):
        """Validate that original message exists"""
        if not self.original_message:
            frappe.throw("Original message reference is required")
        
        if not frappe.db.exists("SMPP SMS Message", self.original_message):
            frappe.throw(f"SMPP SMS Message {self.original_message} does not exist")
    
    def set_processed_time(self):
        """Set processed time if not already set"""
        if not self.processed_time:
            self.processed_time = now()
    
    def update_original_message_status(self):
        """Update original SMS message status based on delivery receipt"""
        if not self.original_message or not self.final_status:
            return
        
        status_mapping = {
            'DELIVRD': 'Delivered',
            'EXPIRED': 'Expired',
            'DELETED': 'Failed',
            'UNDELIV': 'Failed',
            'ACCEPTD': 'Delivered',
            'UNKNOWN': 'Failed',
            'REJECTD': 'Rejected'
        }
        
        new_status = status_mapping.get(self.final_status, 'Failed')
        
        frappe.db.set_value("SMPP SMS Message", self.original_message, {
            "smpp_status": self.final_status,
            "status": new_status,
            "delivered_time": self.done_date if new_status == "Delivered" else None
        })
        
        frappe.db.commit()