# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class SMPPConfiguration(Document):
    def validate(self):
        self.validate_default_config()
        self.validate_connection_params()
    
    def validate_default_config(self):
        """Ensure only one default configuration exists"""
        if self.is_default:
            existing_default = frappe.db.sql("""
                SELECT name FROM `tabSMPP Configuration`
                WHERE is_default = 1 AND name != %s
            """, self.name)
            
            if existing_default:
                frappe.db.set_value("SMPP Configuration", existing_default[0][0], "is_default", 0)
                frappe.msgprint(f"Removed default status from {existing_default[0][0]}")
    
    def validate_connection_params(self):
        """Validate SMPP connection parameters"""
        if not self.smsc_host:
            frappe.throw("SMSC Host is required")
        
        if not self.system_id:
            frappe.throw("System ID is required")
        
        if not self.password:
            frappe.throw("Password is required")
        
        if self.smsc_port and (self.smsc_port < 1 or self.smsc_port > 65535):
            frappe.throw("SMSC Port must be between 1 and 65535")
        
        if self.connection_timeout and self.connection_timeout < 5:
            frappe.throw("Connection timeout must be at least 5 seconds")
        
        if self.enquire_link_timer and self.enquire_link_timer < 10:
            frappe.throw("Enquire link timer must be at least 10 seconds")