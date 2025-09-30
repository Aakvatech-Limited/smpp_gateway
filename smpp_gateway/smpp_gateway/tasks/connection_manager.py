from __future__ import unicode_literals
import frappe



def check_smpp_connections():
    """Check SMPP connections health - called by scheduler every minute"""
    try:
        if not frappe.db:
            return
            
        # Get all active SMPP configurations
        configs = frappe.get_all("SMPP Configuration",
                               filters={"is_active": 1},
                               fields=["name"])
        
        for config in configs:
            try:
                _check_connection_health(config["name"])
            except Exception as e:
                frappe.log_error(f"Connection check error for {config['name']}: {str(e)}", 
                               "SMPP Connection Manager")
                
    except Exception as e:
        frappe.log_error(f"Connection manager error: {str(e)}", "SMPP Connection Manager")

def _check_connection_health(config_name):
    """Check health of specific SMPP connection"""
    try:
        client = get_smpp_client(config_name)
        
        # Check if connection is alive
        if client.connected:
            # Try to send enquire_link
            try:
                if client.client:
                    client.client.enquire_link()
                    # Log successful health check
                    _log_health_check(config_name, True, "Connection healthy")
            except Exception as e:
                # Connection lost, try to reconnect
                client.connected = False
                _log_health_check(config_name, False, f"Connection lost: {str(e)}")
                
                # Attempt reconnection
                try:
                    client.connect()
                    _log_health_check(config_name, True, "Reconnected successfully")
                except Exception as reconnect_error:
                    _log_health_check(config_name, False, f"Reconnection failed: {str(reconnect_error)}")
        else:
            # Connection not established, try to connect
            try:
                client.connect()
                _log_health_check(config_name, True, "Connection established")
            except Exception as connect_error:
                _log_health_check(config_name, False, f"Connection failed: {str(connect_error)}")
                
    except Exception as e:
        _log_health_check(config_name, False, f"Health check error: {str(e)}")

def _log_health_check(config_name, success, message):
    """Log connection health check result"""
    try:
        event_type = "health_check_success" if success else "health_check_failed"
        
        frappe.get_doc({
            "doctype": "SMPP Connection Log",
            "connection_name": config_name,
            "event_type": event_type,
            "event_time": now(),
            "event_details": message
        }).insert(ignore_permissions=True)
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Health check logging error: {str(e)}", "SMPP Connection Manager")

# Background cleanup task
def cleanup_old_logs():
    """Clean up old connection logs and delivery receipts"""
    try:
        # Delete connection logs older than 30 days
        thirty_days_ago = add_to_date(now(), days=-30)
        
        frappe.db.sql("""
            DELETE FROM `tabSMPP Connection Log`
            WHERE creation < %s
        """, [thirty_days_ago])
        
        # Delete delivery receipts older than 90 days  
        ninety_days_ago = add_to_date(now(), days=-90)
        
        frappe.db.sql("""
            DELETE FROM `tabSMPP Delivery Receipt`
            WHERE creation < %s
        """, [ninety_days_ago])
        
        # Delete completed queue items older than 7 days
        seven_days_ago = add_to_date(now(), days=-7)
        
        frappe.db.sql("""
            DELETE FROM `tabSMPP SMS Queue`
            WHERE status = 'Completed' AND creation < %s
        """, [seven_days_ago])
        
        frappe.db.commit()
        
        frappe.logger().info("SMS Gateway cleanup completed")
        
    except Exception as e:
        frappe.log_error(f"Cleanup task error: {str(e)}", "SMS Gateway Cleanup")