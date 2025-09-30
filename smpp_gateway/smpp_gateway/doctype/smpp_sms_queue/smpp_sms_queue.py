# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now, add_to_date

class SMPPSMSQueue(Document):
    def validate(self):
        self.validate_sms_message()
        self.set_defaults()
    
    def validate_sms_message(self):
        """Validate that SMS message exists"""
        if not self.sms_message:
            frappe.throw("SMS Message is required")
        
        if not frappe.db.exists("SMPP SMS Message", self.sms_message):
            frappe.throw(f"SMPP SMS Message {self.sms_message} does not exist")
    
    def set_defaults(self):
        """Set default values"""
        if not self.created_time:
            self.created_time = now()
        
        if not self.scheduled_for:
            self.scheduled_for = now()
        
        if not self.max_attempts:
            self.max_attempts = 3
        
        if not self.retry_interval:
            self.retry_interval = 300
        
        if not self.timeout_seconds:
            self.timeout_seconds = 30