
import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    """
    Add SMPP SMS to Notification channel options
    """
    try:
        
        # Create new Property Setter
        make_property_setter(
            doctype="Notification",
            fieldname="channel",
            property="options",
            value="Email\nSlack\nSystem Notification\nSMS\nSMPP SMS",
            property_type="Text",
            for_doctype=False
        )
            

    except Exception as e:
        print(f"❌ Error in patch: {str(e)}")
        raise

