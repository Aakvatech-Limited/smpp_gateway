# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import frappe
import smpplib.gsm
import smpplib.client
import smpplib.consts
import smpplib.exceptions
import threading
import time
import logging
from frappe.utils import now, add_to_date, get_datetime, cstr
from datetime import datetime
import json

class SMPPClient:
    def __init__(self, config_name=None):
        self.config = self._get_config(config_name)
        self.client = None
        self.connected = False
        self.lock = threading.Lock()
        self.logger = self._setup_logger()
        
    def _get_config(self, config_name=None):
        """Get SMPP configuration"""
        if config_name:
            config = frappe.get_doc("SMPP Configuration", config_name)
        else:
            # Get default configuration
            config = frappe.get_doc("SMPP Configuration", 
                                  {"is_default": 1})
        
        if not config.is_active:
            frappe.throw(f"SMPP Configuration {config.name} is not active")
            
        return config
    
    def _setup_logger(self):
        """Setup logging for SMPP operations"""
        logger = logging.getLogger(f'smpp_client_{self.config.name}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def connect(self):
        """Establish SMPP connection"""
        try:
            with self.lock:
                if self.connected:
                    return True
                
                # Create client
                self.client = smpplib.client.Client(
                    self.config.smsc_host,
                    int(self.config.smsc_port),
                    timeout=int(self.config.connection_timeout)
                )
                
                # Connect to SMSC
                self.client.connect()
                
                # Determine bind type and perform bind
                bind_type = self.config.bind_type.lower()
                
                if bind_type == "transmitter":
                    self.client.bind_transmitter(
                        system_id=self.config.system_id,
                        password=self.config.password,
                        system_type=self.config.system_type or "",
                        interface_version=int(self.config.interface_version.replace('0x', ''), 16),
                        addr_ton=int(self.config.addr_ton),
                        addr_npi=int(self.config.addr_npi),
                        address_range=self.config.address_range or ""
                    )
                elif bind_type == "receiver":
                    self.client.bind_receiver(
                        system_id=self.config.system_id,
                        password=self.config.password,
                        system_type=self.config.system_type or "",
                        interface_version=int(self.config.interface_version.replace('0x', ''), 16),
                        addr_ton=int(self.config.addr_ton),
                        addr_npi=int(self.config.addr_npi),
                        address_range=self.config.address_range or ""
                    )
                else:  # transceiver
                    self.client.bind_transceiver(
                        system_id=self.config.system_id,
                        password=self.config.password,
                        system_type=self.config.system_type or "",
                        interface_version=int(self.config.interface_version.replace('0x', ''), 16),
                        addr_ton=int(self.config.addr_ton),
                        addr_npi=int(self.config.addr_npi),
                        address_range=self.config.address_range or ""
                    )
                
                self.connected = True
                self._log_connection_event("bind_success", "Successfully connected to SMSC")
                
                # Start enquire link thread
                self._start_enquire_link()
                
                return True
                
        except Exception as e:
            error_msg = f"Failed to connect to SMSC: {str(e)}"
            self.logger.error(error_msg)
            self._log_connection_event("bind_failed", error_msg, str(e))
            raise frappe.ValidationError(error_msg)
    
    def disconnect(self):
        """Disconnect from SMSC"""
        try:
            with self.lock:
                if self.client and self.connected:
                    self.client.unbind()
                    self.client.disconnect()
                    self.connected = False
                    self._log_connection_event("disconnect", "Disconnected from SMSC")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {str(e)}")
    
    def _start_enquire_link(self):
        """Start enquire link thread to keep connection alive"""
        def enquire_link_worker():
            while self.connected:
                try:
                    if self.client:
                        self.client.enquire_link()
                        self._log_connection_event("enquire_link", "Enquire link sent")
                    time.sleep(int(self.config.enquire_link_timer))
                except Exception as e:
                    self.logger.error(f"Enquire link failed: {str(e)}")
                    self._log_connection_event("error", f"Enquire link failed: {str(e)}")
                    break
        
        enquire_thread = threading.Thread(target=enquire_link_worker, daemon=True)
        enquire_thread.start()
    
    def send_sms(self, sms_doc):
        """Send SMS message via SMPP"""
        try:
            if not self.connected:
                self.connect()
            
            # Prepare message parameters
            source_addr = sms_doc.sender_id or ""
            dest_addr = sms_doc.recipient_number
            message_text = sms_doc.message_text
            
            # Handle message encoding
            data_coding = int(sms_doc.data_coding or 0)
            if data_coding == 8:  # UCS2
                message_bytes = message_text.encode('utf-16be')
            else:  # GSM 7-bit or ASCII
                message_bytes = message_text.encode('utf-8')
            
            # Prepare submit_sm parameters
            submit_params = {
                'source_addr_ton': int(self.config.addr_ton),
                'source_addr_npi': int(self.config.addr_npi),
                'source_addr': source_addr,
                'dest_addr_ton': int(self.config.addr_ton),
                'dest_addr_npi': int(self.config.addr_npi),
                'destination_addr': dest_addr,
                'esm_class': self._build_esm_class(sms_doc),
                'protocol_id': 0,
                'priority_flag': int(sms_doc.priority or 0),
                'schedule_delivery_time': self._format_time(sms_doc.scheduled_time),
                'validity_period': self._format_time(sms_doc.validity_period),
                'registered_delivery': 1 if sms_doc.registered_delivery else 0,
                'replace_if_present_flag': 1 if sms_doc.replace_if_present else 0,
                'data_coding': data_coding,
                'sm_default_msg_id': 0,
                'short_message': message_bytes
            }
            
            # Add service type if specified
            if sms_doc.service_type:
                submit_params['service_type'] = sms_doc.service_type
            
            # Send message
            pdu = self.client.send_message(**submit_params)
            
            # Update SMS document with SMSC response
            message_id = pdu.receipted_message_id if hasattr(pdu, 'receipted_message_id') else str(pdu.sequence)
            
            frappe.db.set_value("SMPP SMS Message", sms_doc.name, {
                "message_id": message_id,
                "status": "Sent",
                "sent_time": now(),
                "error_code": None,
                "error_message": None
            })
            
            frappe.db.commit()
            
            self.logger.info(f"SMS sent successfully: {sms_doc.name} -> {dest_addr}")
            self._log_connection_event("send_message", 
                                     f"Message sent to {dest_addr}", 
                                     f"Message ID: {message_id}")
            
            return {
                "success": True,
                "message_id": message_id,
                "status": "Sent"
            }
            
        except smpplib.exceptions.PDUError as e:
            error_msg = f"SMPP PDU Error: {str(e)}"
            self._handle_send_error(sms_doc, str(e.code), error_msg)
            return {"success": False, "error": error_msg}
            
        except Exception as e:
            error_msg = f"Send SMS failed: {str(e)}"
            self._handle_send_error(sms_doc, "SYSTEM_ERROR", error_msg)
            return {"success": False, "error": error_msg}
    
    def _build_esm_class(self, sms_doc):
        """Build ESM class byte based on message type"""
        esm_class = 0
        
        # Message mode (bits 1-0)
        esm_class |= 0  # Default SMSC mode
        
        # Message type (bits 5-2) 
        if sms_doc.message_type == "flash":
            esm_class |= (1 << 2)  # Set bit 2 for flash SMS
        
        return esm_class
    
    def _format_time(self, dt):
        """Format datetime for SMPP time fields"""
        if not dt:
            return ""
        
        if isinstance(dt, str):
            dt = get_datetime(dt)
        
        return dt.strftime("%y%m%d%H%M%S000+")
    
    def _handle_send_error(self, sms_doc, error_code, error_message):
        """Handle SMS sending errors"""
        self.logger.error(f"SMS send error for {sms_doc.name}: {error_message}")
        
        # Update SMS document
        frappe.db.set_value("SMPP SMS Message", sms_doc.name, {
            "status": "Failed",
            "error_code": error_code,
            "error_message": error_message,
            "retry_count": (sms_doc.retry_count or 0) + 1
        })
        
        frappe.db.commit()
        
        # Log error
        self._log_connection_event("error", error_message, error_code)
    
    def _log_connection_event(self, event_type, details, error_code=None):
        """Log SMPP connection events"""
        try:
            log_doc = frappe.get_doc({
                "doctype": "SMPP Connection Log",
                "connection_name": self.config.name,
                "event_type": event_type,
                "event_time": now(),
                "event_details": details,
                "error_code": error_code,
                "session_id": getattr(self.client, 'sequence', None) if self.client else None
            })
            log_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            self.logger.error(f"Failed to log event: {str(e)}")
    
    def process_delivery_receipts(self):
        """Process incoming delivery receipts"""
        try:
            if not self.connected:
                return
            
            # Listen for delivery receipts
            pdus = self.client.read_once()
            for pdu in pdus:
                if pdu.command_id == smpplib.consts.SMPP_DELIVER_SM:
                    self._process_delivery_receipt(pdu)
                    
        except Exception as e:
            self.logger.error(f"Error processing delivery receipts: {str(e)}")
    
    def _process_delivery_receipt(self, pdu):
        """Process individual delivery receipt"""
        try:
            # Parse delivery receipt from short_message
            receipt_data = pdu.short_message.decode('utf-8')
            
            # Extract receipt information (format may vary by provider)
            # Standard format: id:XXXXXXXXXX sub:001 dlvrd:001 submit date:... done date:... stat:DELIVRD err:000
            receipt_info = self._parse_delivery_receipt(receipt_data)
            
            if receipt_info and receipt_info.get('id'):
                # Find original SMS message
                sms_message = frappe.db.get_value("SMPP SMS Message", 
                                                {"message_id": receipt_info['id']}, 
                                                "name")
                
                if sms_message:
                    # Create delivery receipt record
                    receipt_doc = frappe.get_doc({
                        "doctype": "SMPP Delivery Receipt",
                        "original_message": sms_message,
                        "receipted_message_id": receipt_info['id'],
                        "recipient_number": pdu.source_addr,
                        "final_status": receipt_info.get('stat', 'UNKNOWN'),
                        "submit_date": receipt_info.get('submit_date'),
                        "done_date": receipt_info.get('done_date'),
                        "error_code": receipt_info.get('err'),
                        "raw_receipt_data": receipt_data
                    })
                    receipt_doc.insert(ignore_permissions=True)
                    
                    # Update original SMS status
                    new_status = self._map_receipt_status(receipt_info.get('stat'))
                    frappe.db.set_value("SMPP SMS Message", sms_message, {
                        "smpp_status": receipt_info.get('stat'),
                        "status": new_status,
                        "delivered_time": receipt_info.get('done_date') if new_status == "Delivered" else None
                    })
                    
                    frappe.db.commit()
                    
                    self._log_connection_event("receive_receipt", 
                                             f"Receipt processed for message {receipt_info['id']}")
        
        except Exception as e:
            self.logger.error(f"Error processing delivery receipt: {str(e)}")
    
    def _parse_delivery_receipt(self, receipt_text):
        """Parse delivery receipt text"""
        try:
            receipt_info = {}
            parts = receipt_text.split(' ')
            
            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    receipt_info[key] = value
            
            return receipt_info
        except Exception:
            return None
    
    def _map_receipt_status(self, smpp_status):
        """Map SMPP status to SMS Message status"""
        status_map = {
            'DELIVRD': 'Delivered',
            'EXPIRED': 'Expired', 
            'DELETED': 'Failed',
            'UNDELIV': 'Failed',
            'ACCEPTD': 'Delivered',
            'UNKNOWN': 'Failed',
            'REJECTD': 'Rejected'
        }
        return status_map.get(smpp_status, 'Failed')

# Global connection pool
_connection_pool = {}

def get_smpp_client(config_name=None):
    """Get or create SMPP client instance"""
    key = config_name or "default"
    
    if key not in _connection_pool:
        _connection_pool[key] = SMPPClient(config_name)
    
    return _connection_pool[key]

def cleanup_connections():
    """Clean up all SMPP connections"""
    for client in _connection_pool.values():
        try:
            client.disconnect()
        except Exception:
            pass
    _connection_pool.clear()

# Register cleanup on app shutdown
import atexit
atexit.register(cleanup_connections)