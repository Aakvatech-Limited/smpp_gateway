/**
 * SMPP Gateway - Notification Form Enhancement
 *
 * This script enhances the Notification form to support SMPP SMS channel:
 * - Filters recipient fields to show only Phone fields when SMPP SMS is selected
 * - Provides helpful descriptions and validation
 * - Maintains compatibility with other channels
 */

frappe.ui.form.on('Notification', {
	refresh: function (frm) {
		// Add help text for SMPP SMS channel
		if (frm.doc.channel === 'SMPP SMS') {
			add_smpp_help_text(frm);
		}

		// Setup field filtering for recipients
		setup_recipient_field_filtering(frm);
	},

	channel: function (frm) {
		// Update help text when channel changes
		if (frm.doc.channel === 'SMPP SMS') {
			add_smpp_help_text(frm);
		} else {
			remove_smpp_help_text(frm);
		}

		// Re-setup field filtering
		setup_recipient_field_filtering(frm);

		// Clear recipients if switching to SMPP SMS (they need to select phone fields)
		if (frm.doc.channel === 'SMPP SMS' && frm.doc.recipients && frm.doc.recipients.length > 0) {
			frappe.msgprint({
				title: __('Channel Changed to SMPP SMS'),
				message: __('Please configure recipients with phone number fields for SMPP SMS notifications.'),
				indicator: 'blue'
			});
		}
	},

	document_type: function (frm) {
		// When document type changes, update recipient field options
		setup_recipient_field_filtering(frm);
	}
});


/**
 * Setup recipient field filtering for SMPP SMS
 * Uses Frappe's standard grid.update_docfield_property method
 */
function setup_recipient_field_filtering(frm) {
	if (!frm.doc.document_type) {
		return;
	}

	// Only filter for SMPP SMS channel
	if (frm.doc.channel !== 'SMPP SMS') {
		return;
	}

	// Get phone fields from the selected document type
	frappe.model.with_doctype(frm.doc.document_type, () => {
		let phone_fields = [];

		// Helper function to create select options
		let get_select_options = function (df, parent_field) {
			// Append parent_field name along with fieldname for child table fields
			let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;

			return {
				value: select_value,
				label: df.fieldname + " (" + __(df.label, null, df.parent) + ")"
			};
		};

		// Get all fields from the doctype
		let fields = frappe.meta.get_docfields(frm.doc.document_type);

		// Filter for Phone fields only
		phone_fields = $.map(fields, function (d) {
			return d.fieldtype == "Phone" ? get_select_options(d) : null;
		});

		// Also check Link fields for phone fields in linked doctypes
		fields.forEach(df => {
			if (df.fieldtype === 'Link' && df.options) {
				try {
					let linked_meta = frappe.get_meta(df.options);
					if (linked_meta) {
						linked_meta.fields.forEach(linked_df => {
							if (linked_df.fieldtype === 'Phone') {
								phone_fields.push({
									value: df.fieldname + "." + linked_df.fieldname,
									label: df.fieldname + "." + linked_df.fieldname + " (" + __(df.label) + " → " + __(linked_df.label) + ")"
								});
							}
						});
					}
				} catch (e) {
					// Linked doctype might not be loaded, skip it
					console.log('Could not load linked doctype:', df.options);
				}
			}
		});

		// Check if any phone fields found
		if (phone_fields.length === 0) {
			frappe.msgprint({
				title: __('No Phone Fields Found'),
				message: __('The selected Document Type "{0}" does not have any Phone fields. Please add a Phone field to the DocType or select a different Document Type.', [frm.doc.document_type]),
				indicator: 'orange'
			});
		}

		// Update the receiver_by_document_field options using Frappe's standard method
		// This is the same method used in core notification.js
		frm.fields_dict.recipients.grid.update_docfield_property(
			"receiver_by_document_field",
			"options",
			[""].concat(phone_fields)
		);

		// Store phone fields for validation
		frm._smpp_phone_fields = phone_fields;
	});
}


/**
 * Add help text for SMPP SMS channel
 */
function add_smpp_help_text(frm) {
	if (frm._smpp_help_added) {
		return;
	}

	// Add help section
	let help_html = `
		<div class="alert alert-info" style="margin-top: 10px;">
			<h5><i class="fa fa-mobile"></i> SMPP SMS Channel</h5>
			<p>SMS will be sent via SMPP Gateway (faster, more reliable than HTTP SMS).</p>
			<ul>
				<li><strong>Recipients:</strong> Select phone number fields from the document</li>
				<li><strong>Message:</strong> Use Jinja templates for dynamic content (e.g., {{ doc.customer_name }})</li>
				<li><strong>Tracking:</strong> All SMS will be tracked in SMPP SMS Message doctype</li>
			</ul>
			<p class="text-muted">
				<small>
					<i class="fa fa-info-circle"></i> 
					Make sure you have configured an active SMPP Configuration before using this channel.
				</small>
			</p>
		</div>
	`;

	// Insert after channel field
	frm.fields_dict.channel.$wrapper.after(help_html);
	frm._smpp_help_added = true;
}


/**
 * Remove help text when switching away from SMPP SMS
 */
function remove_smpp_help_text(frm) {
	if (frm._smpp_help_added) {
		frm.fields_dict.channel.$wrapper.next('.alert-info').remove();
		frm._smpp_help_added = false;
	}
}

