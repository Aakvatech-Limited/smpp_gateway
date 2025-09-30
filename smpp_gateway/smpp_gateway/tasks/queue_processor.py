import threading
import time
from frappe.utils import now, get_datetime, cint
from smpp_gateway.api.smpp_client import get_smpp_client

def process_sms_queue():
    """Process SMS queue - called by scheduler every 5 minutes"""
    try:
        if not frappe.db:
            return
            
        # Get pending queue items
        queue_items = frappe.get_all("SMPP SMS Queue",
                                   filters={
                                       "status": ["in", ["Pending", "Retrying"]],
                                       "scheduled_for": ["<=", now()],
                                       "attempts": ["<", "max_attempts"]
                                   },
                                   fields=["name", "sms_message", "priority", "attempts", 
                                          "max_attempts", "retry_interval"],
                                   order_by="priority asc, creation asc",
                                   limit=100)
        
        if not queue_items:
            return
        
        processed_count = 0
        failed_count = 0
        
        for item in queue_items:
            try:
                # Process queue item
                success = _process_queue_item(item)
                
                if success:
                    processed_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                frappe.log_error(f"Queue processing error for {item.name}: {str(e)}", 
                               "SMS Queue Processor")
                failed_count += 1
        
        if processed_count > 0 or failed_count > 0:
            frappe.logger().info(f"SMS Queue processed: {processed_count} success, {failed_count} failed")
            
    except Exception as e:
        frappe.log_error(f"SMS Queue processor error: {str(e)}", "SMS Queue Processor")

def _process_queue_item(queue_item):
    """Process individual queue item"""
    try:
        # Get SMS message
        sms_doc = frappe.get_doc("SMPP SMS Message", queue_item["sms_message"])
        
        # Skip if message is already sent
        if sms_doc.status in ["Sent", "Delivered"]:
            _update_queue_status(queue_item["name"], "Completed", "Message already sent")
            return True
        
        # Get SMPP client
        client = get_smpp_client(sms_doc.smpp_configuration)
        
        # Update queue status to Processing
        _update_queue_status(queue_item["name"], "Processing", f"Attempt {queue_item['attempts'] + 1}")
        
        # Send SMS
        result = client.send_sms(sms_doc)
        
        if result["success"]:
            # Mark queue item as completed
            _update_queue_status(queue_item["name"], "Completed", "SMS sent successfully")
            return True
        else:
            # Handle failure
            return _handle_queue_failure(queue_item, result["error"])
            
    except Exception as e:
        return _handle_queue_failure(queue_item, str(e))

def _handle_queue_failure(queue_item, error_message):
    """Handle queue item failure with retry logic"""
    try:
        attempts = queue_item["attempts"] + 1
        max_attempts = queue_item["max_attempts"]
        
        if attempts >= max_attempts:
            # Max attempts reached, mark as failed
            _update_queue_status(queue_item["name"], "Failed", 
                               f"Max attempts reached. Last error: {error_message}")
            return False
        else:
            # Schedule retry
            retry_interval = queue_item.get("retry_interval", 300)  # 5 minutes default
            next_retry = add_to_date(now(), seconds=retry_interval)
            
            frappe.db.set_value("SMS Queue", queue_item["name"], {
                "status": "Retrying",
                "attempts": attempts,
                "last_attempt": now(),
                "next_retry": next_retry,
                "error_log": f"Attempt {attempts}: {error_message}\n" + 
                           (frappe.db.get_value("SMPP SMS Queue", queue_item["name"], "error_log") or "")
            })
            frappe.db.commit()
            
            return False
            
    except Exception as e:
        frappe.log_error(f"Queue failure handling error: {str(e)}", "SMS Queue Processor")
        return False

def _update_queue_status(queue_name, status, notes=None):
    """Update queue item status"""
    try:
        update_data = {
            "status": status,
            "last_attempt": now()
        }
        
        if notes:
            existing_notes = frappe.db.get_value("SMPP SMS Queue", queue_name, "processing_notes") or ""
            update_data["processing_notes"] = f"{now()}: {notes}\n{existing_notes}"
        
        frappe.db.set_value("SMPP SMS Queue", queue_name, update_data)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Queue status update error: {str(e)}", "SMS Queue Processor")

