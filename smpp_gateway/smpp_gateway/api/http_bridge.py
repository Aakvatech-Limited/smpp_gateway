# -*- coding: utf-8 -*-
"""
SMPP Gateway HTTP Bridge
Provides HTTP-compatible interface for SMS Settings integration
"""

from __future__ import unicode_literals
import frappe
from frappe import _
import json


@frappe.whitelist(allow_guest=False)
def send_sms():
    """
    HTTP Bridge endpoint for SMS Settings integration
    
    Compatible with SMS Settings parameter format:
    - message: SMS content
    - to/receiver: Phone number
    - sender_id: Optional sender ID
    - smpp_config: Optional SMPP configuration name
    
    Returns HTTP status codes for SMS Settings compatibility
    """
    try:
        # Get request data (supports both GET and POST)
        if frappe.request.method == "POST":
            # Handle JSON POST data
            if frappe.request.content_type and "application/json" in frappe.request.content_type:
                data = frappe.request.get_json() or {}
            else:
                # Handle form-encoded POST data
                data = frappe.form_dict
        else:
            # Handle GET parameters
            data = frappe.form_dict
        
        # Extract parameters (flexible parameter names for compatibility)
        message = data.get("message") or data.get("msg") or data.get("text")
        recipient = data.get("to") or data.get("receiver") or data.get("phone") or data.get("number")
        sender_id = data.get("sender_id") or data.get("sender") or data.get("from")
        smpp_config = data.get("smpp_config") or data.get("config")
        priority = data.get("priority", "Normal")
        
        # Validate required parameters
        if not message:
            frappe.response["http_status_code"] = 400
            return {"error": "Missing required parameter: message"}
        
        if not recipient:
            frappe.response["http_status_code"] = 400
            return {"error": "Missing required parameter: recipient phone number"}
        
        # Send SMS via SMPP
        from smpp_gateway.smpp_gateway.api.sms_api import send_notification_sms
        
        result = send_notification_sms(
            receiver_list=[recipient],
            message=message,
            reference_doctype="SMS Settings",
            reference_name="HTTP Bridge",
            smpp_config=smpp_config,
            sender_id=sender_id,
            priority=priority
        )
        
        if result.get("success"):
            frappe.response["http_status_code"] = 200
            return {
                "status": "success",
                "message": "SMS sent successfully",
                "message_id": result.get("message_id"),
                "sent_count": result.get("sent_count", 1)
            }
        else:
            frappe.response["http_status_code"] = 500
            return {
                "status": "error",
                "message": result.get("error", "Failed to send SMS")
            }
    
    except Exception as e:
        frappe.log_error(f"SMPP HTTP Bridge Error: {str(e)}", "SMPP HTTP Bridge")
        frappe.response["http_status_code"] = 500
        return {
            "status": "error",
            "message": str(e)
        }



