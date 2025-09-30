# -*- coding: utf-8 -*-
"""
SMPP SMS API
Handles sending SMS via SMPP Gateway for Notifications and other integrations
"""

from __future__ import unicode_literals
import frappe
from frappe import _
import json
import re


# SMPP Priority Mapping (SMPP v3.4 spec)
# priority_flag must be 0-3 (numeric)
PRIORITY_MAP = {
    "Low": 0,
    "Normal": 0,
    "Medium": 1,
    "High": 2,
    "Urgent": 3,
    "Very High": 3,
    # Numeric values (for backward compatibility)
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
}


def normalize_priority(priority):
    """
    Convert human-readable priority to SMPP numeric priority (0-3)

    According to SMPP v3.4 specification:
    - 0: Level 0 (lowest priority / normal)
    - 1: Level 1 priority (medium)
    - 2: Level 2 priority (high)
    - 3: Level 3 (highest priority / urgent)

    Args:
        priority: String priority ("Normal", "High", etc.) or numeric string/int

    Returns:
        int: SMPP priority flag (0-3)

    Examples:
        >>> normalize_priority("Normal")
        0
        >>> normalize_priority("High")
        2
        >>> normalize_priority("Urgent")
        3
        >>> normalize_priority(1)
        1
    """
    if priority is None:
        return 0

    # If already numeric, validate and return
    if isinstance(priority, int):
        return max(0, min(3, priority))  # Clamp to 0-3

    # Convert string to title case for mapping
    priority_str = str(priority).strip().title()

    # Try to get from map
    if priority_str in PRIORITY_MAP:
        return PRIORITY_MAP[priority_str]

    # Try to parse as integer
    try:
        priority_int = int(priority)
        return max(0, min(3, priority_int))  # Clamp to 0-3
    except (ValueError, TypeError):
        # Default to normal priority
        frappe.log_error(
            f"Invalid priority value: {priority}. Using default (0).",
            "SMPP Priority Mapping"
        )
        return 0


@frappe.whitelist()
def get_priority_options():
    """
    Get available priority options for UI

    Returns:
        dict: Priority mapping with descriptions
    """
    return {
        "options": [
            {"value": "0", "label": "Normal (0)", "description": "Lowest priority"},
            {"value": "1", "label": "Medium (1)", "description": "Level 1 priority"},
            {"value": "2", "label": "High (2)", "description": "Level 2 priority"},
            {"value": "3", "label": "Urgent (3)", "description": "Highest priority"}
        ],
        "mapping": PRIORITY_MAP,
        "default": "0"
    }


@frappe.whitelist()
def send_notification_sms(receiver_list, message, reference_doctype=None, reference_name=None,
                         smpp_config=None, priority="Normal", sender_id=None):
    """
    Send SMS via SMPP Gateway from Notification system

    Args:
        receiver_list: List of phone numbers or JSON string
        message: SMS message text (can contain Jinja)
        reference_doctype: Source doctype (e.g., "Sales Order")
        reference_name: Source document name
        smpp_config: SMPP Configuration name (optional, uses default if not provided)
        priority: Message priority (High/Normal/Low)
        sender_id: Sender ID (optional)

    Returns:
        dict: {
            "success": True/False,
            "sent_count": int,
            "failed_count": int,
            "sms_messages": [list of created SMPP SMS Message names]
        }
    """
    from smpp_gateway.smpp_gateway.api.smpp_client import get_smpp_client

    try:
        # Normalize receiver list
        if isinstance(receiver_list, str):
            try:
                receiver_list = json.loads(receiver_list)
            except:
                # If not JSON, treat as comma-separated
                receiver_list = [r.strip() for r in receiver_list.split(',')]

        if not isinstance(receiver_list, list):
            receiver_list = [receiver_list]

        # Remove empty values
        receiver_list = [r for r in receiver_list if r]

        if not receiver_list:
            frappe.throw(_("No recipients provided"))

        # Validate message
        if not message:
            frappe.throw(_("Message text is required"))

        # Get SMPP configuration
        if not smpp_config:
            smpp_config = frappe.db.get_value("SMPP Configuration",
                                             {"is_default": 1, "is_active": 1},
                                             "name")

        if not smpp_config:
            frappe.throw(_("No active SMPP Configuration found. Please configure SMPP Gateway."))

        # Get SMPP client
        client = get_smpp_client(smpp_config)

        # Normalize priority to SMPP numeric format (0-3)
        numeric_priority = normalize_priority(priority)

        # Track results
        success_list = []
        failed_list = []
        sms_message_names = []

        # Send to each recipient
        for phone_number in receiver_list:
            try:
                # Clean phone number
                phone_number = clean_phone_number(phone_number)

                if not phone_number:
                    frappe.log_error(f"Invalid phone number: {phone_number}", "SMPP Notification")
                    failed_list.append(phone_number)
                    continue

                # Create SMPP SMS Message with numeric priority
                sms_doc = frappe.get_doc({
                    "doctype": "SMPP SMS Message",
                    "recipient_number": phone_number,
                    "message_text": message,
                    "smpp_configuration": smpp_config,
                    "priority": str(numeric_priority),  # Convert to string for Select field
                    "sender_id": sender_id,
                    "reference_doctype": reference_doctype or "Notification",
                    "reference_name": reference_name or "Auto-sent",
                    "status": "Draft"
                })
                sms_doc.insert(ignore_permissions=True)
                sms_message_names.append(sms_doc.name)

                # Send via SMPP - pass the document object, not individual parameters
                result = client.send_sms(sms_doc)

                if result.get('success'):
                    success_list.append(phone_number)
                    # Status is already updated by client.send_sms()
                else:
                    failed_list.append(phone_number)
                    # Error is already logged by client.send_sms()

                # Reload document to get updated status
                sms_doc.reload()

            except Exception as e:
                error_msg = str(e)
                frappe.log_error(f"SMPP send failed for {phone_number}: {error_msg}",
                               "SMPP Notification Error")
                failed_list.append(phone_number)

        # Return results
        result = {
            "success": len(success_list) > 0,
            "sent_count": len(success_list),
            "failed_count": len(failed_list),
            "sms_messages": sms_message_names,
            "success_list": success_list,
            "failed_list": failed_list
        }

        # Show message to user
        if len(success_list) > 0:
            frappe.msgprint(
                _("SMS sent successfully to {0} recipient(s) via SMPP").format(len(success_list)),
                indicator="green"
            )

        if len(failed_list) > 0:
            frappe.msgprint(
                _("Failed to send SMS to {0} recipient(s)").format(len(failed_list)),
                indicator="red"
            )

        return result

    except Exception as e:
        frappe.log_error(f"SMPP Notification error: {str(e)}", "SMPP Notification Error")
        frappe.throw(_("Failed to send SMS via SMPP Gateway: {0}").format(str(e)))


def clean_phone_number(phone):
    """
    Clean and validate phone number

    Args:
        phone: Phone number string

    Returns:
        str: Cleaned phone number or None if invalid
    """
    if not phone:
        return None

    # Remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', str(phone))

    # Basic validation - must have at least 7 digits
    if len(re.sub(r'[^\d]', '', phone)) < 7:
        return None

    return phone


def get_phone_number_from_field(doc, fieldname):
    """
    Extract phone number from document field

    Args:
        doc: Document object
        fieldname: Field name to extract from

    Returns:
        str: Phone number or None
    """
    if not doc or not fieldname:
        return None

    # Handle nested fields (e.g., "customer.mobile_no")
    if "." in fieldname:
        parts = fieldname.split(".")
        value = doc
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return clean_phone_number(value)

    # Direct field access
    value = doc.get(fieldname)
    return clean_phone_number(value)


@frappe.whitelist()
def send_sms(recipient_number, message_text, smpp_config=None, sender_id=None, priority="Normal"):
    """
    Simple API to send single SMS via SMPP

    Args:
        recipient_number: Phone number
        message_text: Message content
        smpp_config: SMPP Configuration name (optional)
        sender_id: Sender ID (optional)
        priority: Message priority

    Returns:
        dict: Result with success status and message details
    """
    return send_notification_sms(
        receiver_list=[recipient_number],
        message=message_text,
        smpp_config=smpp_config,
        sender_id=sender_id,
        priority=priority
    )


@frappe.whitelist()
def send_template_sms(template_name, recipients, template_data=None):
    """
    Send SMS using SMPP SMS Template

    Args:
        template_name: Name of SMPP SMS Template
        recipients: List of phone numbers
        template_data: Dict of template variables

    Returns:
        dict: Result with success status
    """
    try:
        # Get template
        template = frappe.get_doc("SMPP SMS Template", template_name)

        if not template.is_active:
            frappe.throw(_("Template {0} is not active").format(template_name))

        # Parse template data
        if isinstance(template_data, str):
            template_data = json.loads(template_data)

        if not template_data:
            template_data = {}

        # Render template
        message = frappe.render_template(template.message_template, template_data)

        # Send SMS
        return send_notification_sms(
            receiver_list=recipients,
            message=message,
            smpp_config=template.get("default_smpp_configuration"),
            sender_id=template.get("default_sender_id"),
            priority=template.get("default_priority", "Normal")
        )

    except Exception as e:
        frappe.log_error(f"Template SMS error: {str(e)}", "SMPP Template SMS Error")
        frappe.throw(_("Failed to send template SMS: {0}").format(str(e)))
