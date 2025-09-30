# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now

class SMPPConnectionLog(Document):
    def validate(self):
        if not self.event_time:
            self.event_time = now()
    
    def before_insert(self):
        log_count = frappe.db.count("SMPP Connection Log", {
            "connection_name": self.connection_name
        })
        
        if log_count >= 1000:
            old_logs = frappe.db.sql("""
                SELECT name FROM `tabSMPP Connection Log`
                WHERE connection_name = %s
                ORDER BY event_time ASC
                LIMIT 100
            """, self.connection_name, as_list=True)
            
            for log_name in old_logs:
                frappe.delete_doc("SMPP Connection Log", log_name[0], ignore_permissions=True)