from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now, validate_phone_number
import re

class SMPPSMSMessage(Document):
    pass