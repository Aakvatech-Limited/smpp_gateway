# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import re

class SMPPSMSTemplate(Document):
    def validate(self):
        self.extract_template_variables()
        self.calculate_template_stats()
        self.generate_sample_output()
    
    def extract_template_variables(self):
        """Extract variables from template text"""
        if not self.message_template:
            return
        
        variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', self.message_template)
        unique_vars = list(set(variables))
        
        existing_vars = [d.variable_name for d in self.variables] if self.variables else []
        
        for var in unique_vars:
            if var not in existing_vars:
                self.append("variables", {
                    "variable_name": var,
                    "variable_type": "text",
                    "is_required": 0
                })
        
        self.variables = [d for d in self.variables if d.variable_name in unique_vars]
    
    def calculate_template_stats(self):
        """Calculate template statistics"""
        if not self.message_template:
            return
        
        base_length = len(self.message_template)
        var_count = len(self.variables) if self.variables else 0
        estimated_length = base_length + (var_count * 10)
        
        is_unicode = any(ord(char) > 127 for char in self.message_template)
        
        if is_unicode:
            sms_parts = 1 if estimated_length <= 70 else (estimated_length - 1) // 67 + 1
        else:
            sms_parts = 1 if estimated_length <= 160 else (estimated_length - 1) // 153 + 1
        
        self.character_count = base_length
        self.sms_parts = sms_parts
    
    def generate_sample_output(self):
        """Generate sample output with placeholder values"""
        if not self.message_template:
            return
        
        sample_message = self.message_template
        
        if self.variables:
            for var in self.variables:
                pattern = r'\{\{\s*' + re.escape(var.variable_name) + r'\s*\}\}'
                
                if var.default_value:
                    replacement = var.default_value
                else:
                    if var.variable_type == "number":
                        replacement = "123"
                    elif var.variable_type == "date":
                        replacement = "2024-01-01"
                    elif var.variable_type == "datetime":
                        replacement = "2024-01-01 12:00:00"
                    elif var.variable_type == "currency":
                        replacement = "100.00"
                    else:
                        replacement = f"[{var.variable_name}]"
                
                sample_message = re.sub(pattern, replacement, sample_message)
        
        self.sample_output = sample_messagess