# -*- coding: utf-8 -*-
"""
Notification Override for SMPP SMS Channel
Extends Frappe's Notification doctype to support SMPP SMS channel
"""

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.email.doctype.notification.notification import Notification, get_context
import json


class SMPPNotification(Notification):
    """
    Extended Notification class with SMPP SMS support
    """
    
    def send(self, doc):
        """
        Override send method to handle SMPP SMS channel
        """
        context = get_context(doc)
        context = {"doc": doc, "alert": self, "comments": None}
        
        if doc.get("_comments"):
            context["comments"] = json.loads(doc.get("_comments"))
        
        if self.is_standard:
            self.load_standard_properties(context)
        
        try:
            # Handle SMPP SMS channel
            if self.channel == "SMPP SMS":
                self.send_smpp_sms(doc, context)
            else:
                # Call parent method for other channels (Email, Slack, SMS, System Notification)
                super(SMPPNotification, self).send(doc)
        
        except Exception as e:
            self.log_error(f"Failed to send Notification: {str(e)}")
    
    
    def send_smpp_sms(self, doc, context):
        """
        Send SMS via SMPP Gateway
        
        Args:
            doc: Document that triggered the notification
            context: Jinja context for template rendering
        """
        from smpp_gateway.smpp_gateway.api.sms_api import send_notification_sms
        
        try:
            # Get recipients
            receiver_list = self.get_receiver_list(doc, context)
            
            if not receiver_list:
                frappe.log_error(
                    f"No recipients found for SMPP SMS notification: {self.name}",
                    "SMPP Notification - No Recipients"
                )
                return
            
            # Render message template
            message = frappe.render_template(self.message, context)
            
            # Get SMPP configuration (if specified in notification)
            smpp_config = self.get("smpp_configuration") if hasattr(self, "smpp_configuration") else None
            
            # Get sender ID (if specified)
            sender_id = self.get("sender_id") if hasattr(self, "sender_id") else None
            
            # Get priority (if specified)
            priority = self.get("sms_priority") if hasattr(self, "sms_priority") else "Normal"
            
            # Send SMS via SMPP
            result = send_notification_sms(
                receiver_list=receiver_list,
                message=message,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
                smpp_config=smpp_config,
                sender_id=sender_id,
                priority=priority
            )
            
            # Log result
            if result.get("success"):
                frappe.logger().info(
                    f"SMPP SMS sent successfully: {result.get('sent_count')} recipients"
                )
            else:
                frappe.log_error(
                    f"SMPP SMS failed: {result.get('failed_count')} recipients",
                    "SMPP Notification Failed"
                )
        
        except Exception as e:
            frappe.log_error(
                f"SMPP SMS notification error: {str(e)}",
                "SMPP Notification Error"
            )
            raise
    
    
    def get_receiver_list(self, doc, context):
        """
        Get list of phone numbers from recipients
        
        Args:
            doc: Document object
            context: Jinja context
        
        Returns:
            list: List of phone numbers
        """
        from smpp_gateway.smpp_gateway.api.sms_api import get_phone_number_from_field
        
        receiver_list = []
        
        # Get recipients from Notification Recipients table
        for recipient in self.recipients:
            # Check if recipient has a condition
            if recipient.condition:
                if not frappe.safe_eval(recipient.condition, None, context):
                    continue
            
            # Get phone number from document field
            if recipient.receiver_by_document_field:
                phone = get_phone_number_from_field(doc, recipient.receiver_by_document_field)
                if phone:
                    receiver_list.append(phone)
            
            # Get phone numbers from users with specific role
            elif recipient.receiver_by_role:
                users = frappe.get_all(
                    "Has Role",
                    filters={"role": recipient.receiver_by_role, "parenttype": "User"},
                    fields=["parent"]
                )
                
                for user in users:
                    user_doc = frappe.get_cached_doc("User", user.parent)
                    if user_doc.mobile_no:
                        receiver_list.append(user_doc.mobile_no)
                    elif user_doc.phone:
                        receiver_list.append(user_doc.phone)
        
        # Remove duplicates
        receiver_list = list(set(receiver_list))
        
        return receiver_list


def validate_smpp_channel(doc, method=None):
    """
    Validate SMPP SMS channel configuration
    Called on before_insert and on_update
    
    Args:
        doc: Notification document
        method: Hook method name
    """
    if doc.channel == "SMPP SMS":
        # Check if SMPP is configured
        smpp_configs = frappe.get_all(
            "SMPP Configuration",
            filters={"is_active": 1},
            limit=1
        )
        
        if not smpp_configs:
            frappe.msgprint(
                _("No active SMPP Configuration found. Please configure SMPP Gateway before using SMPP SMS notifications."),
                indicator="orange",
                alert=True
            )
        
        # Validate recipients have phone number fields
        if not doc.recipients:
            frappe.throw(_("Please add recipients for SMPP SMS notification"))
        
        # Check if recipients have valid phone number fields
        has_valid_recipient = False
        for recipient in doc.recipients:
            if recipient.receiver_by_document_field or recipient.receiver_by_role:
                has_valid_recipient = True
                break
        
        if not has_valid_recipient:
            frappe.throw(
                _("Please configure recipients with phone number fields or roles for SMPP SMS notification")
            )


def get_notification_class():
    """
    Return the custom notification class
    Used by Frappe to override the default Notification class
    """
    return SMPPNotification

