# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now
import re

class SMPPSMSMessage(Document):
    def validate(self):
        self.validate_phone_number()
        self.validate_message_content()
        self.set_default_config()
        self.set_default_sender_id()
        self.calculate_message_stats()
    
    def validate_phone_number(self):
        """Validate recipient phone number format"""
        if not self.recipient_number:
            frappe.throw("Recipient number is required")
        
        phone = re.sub(r'[^\d+]', '', self.recipient_number)
        
        if not re.match(r'^\+?[1-9]\d{1,14}$', phone):
            frappe.throw(f"Invalid phone number format: {self.recipient_number}")
        
        self.recipient_number = phone
    
    def validate_message_content(self):
        """Validate SMS message content"""
        if not self.message_text:
            frappe.throw("Message text is required")
        
        if len(self.message_text) > 1600:
            frappe.throw("Message text too long. Maximum 1600 characters allowed.")
    
    def set_default_config(self):
        """Set default SMPP configuration if not specified"""
        if not self.smpp_configuration:
            default_config = frappe.db.get_value("SMPP Configuration",
                                                {"is_default": 1, "is_active": 1}, "name")
            if default_config:
                self.smpp_configuration = default_config
            else:
                frappe.throw("No default SMPP configuration found")

    def set_default_sender_id(self):
        """Set default sender ID from SMPP configuration if not specified"""
        if not self.sender_id and self.smpp_configuration:
            config = frappe.get_doc("SMPP Configuration", self.smpp_configuration)
            # Use default_sender_id from config, or fallback to system_id
            self.sender_id = config.get("default_sender_id") or config.system_id

    def calculate_message_stats(self):
        """Calculate message statistics"""
        if not self.message_text:
            return
        
        message_length = len(self.message_text)
        is_unicode = any(ord(char) > 127 for char in self.message_text)
        
        if is_unicode:
            sms_parts = 1 if message_length <= 70 else (message_length - 1) // 67 + 1
        else:
            sms_parts = 1 if message_length <= 160 else (message_length - 1) // 153 + 1
        
        self.data_coding = "8" if is_unicode else "0"

    def query_delivery_status(self):
        """Query delivery status from SMSC using query_sm PDU"""
        if not self.message_id:
            frappe.throw("Cannot query status: Message ID is missing")

        if self.status not in ["Sent", "Delivered", "Failed", "Expired"]:
            frappe.throw(f"Cannot query status for message in '{self.status}' state")

        try:
            from smpp_gateway.smpp_gateway.api.smpp_client import get_smpp_client

            config_name = self.smpp_configuration
            if not config_name:
                # Get default configuration
                config_name = frappe.db.get_value("SMPP Configuration",
                                                 {"is_default": 1, "is_active": 1},
                                                 "name")

            if not config_name:
                frappe.throw("No active SMPP Configuration found")

            client = get_smpp_client(config_name)

            # Query message status using query_sm PDU
            result = client.query_message_status(
                message_id=self.message_id,
                source_addr=self.sender_id or ""
            )

            if result.get("success"):
                # Update status based on SMSC response
                message_state_text = result.get("message_state_text")

                # Map SMPP message states to our status values
                status_mapping = {
                    "ENROUTE": "Sent",
                    "DELIVERED": "Delivered",
                    "EXPIRED": "Expired",
                    "DELETED": "Failed",
                    "UNDELIVERABLE": "Failed",
                    "ACCEPTED": "Delivered",
                    "UNKNOWN": "Failed",
                    "REJECTED": "Rejected"
                }

                new_status = status_mapping.get(message_state_text, self.status)

                # Update document if status changed
                if new_status != self.status or message_state_text != self.smpp_status:
                    self.status = new_status
                    self.smpp_status = message_state_text

                    # Set delivered time if message was delivered
                    if new_status == "Delivered" and not self.delivered_time:
                        self.delivered_time = now()

                    self.save()

                return result
            else:
                frappe.throw(f"Failed to query status: {result.get('error', 'Unknown error')}")

        except Exception as e:
            frappe.log_error(f"Failed to query SMS delivery status: {str(e)}", "SMPP Query Status Error")
            frappe.throw(f"Query failed: {str(e)}")