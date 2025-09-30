/**
 * SMPP Gateway - Notification Form Enhancement
 * 
 * This script enhances the Notification form to support SMPP SMS channel:
 * - Filters recipient fields to show only Phone fields when SMPP SMS is selected
 * - Provides helpful descriptions and validation
 * - Maintains compatibility with other channels
 */

frappe.ui.form.on('Notification', {
	refresh: function(frm) {
		// Add help text for SMPP SMS channel
		if (frm.doc.channel === 'SMPP SMS') {
			add_smpp_help_text(frm);
		}
		
		// Setup field filtering for recipients
		setup_recipient_field_filtering(frm);
	},
	
	channel: function(frm) {
		// Update help text when channel changes
		if (frm.doc.channel === 'SMPP SMS') {
			add_smpp_help_text(frm);
		} else {
			remove_smpp_help_text(frm);
		}
		
		// Re-setup field filtering
		setup_recipient_field_filtering(frm);
		
		// Clear recipients if switching to SMPP SMS (they need to select phone fields)
		if (frm.doc.channel === 'SMPP SMS' && frm.doc.recipients) {
			frappe.msgprint({
				title: __('Channel Changed to SMPP SMS'),
				message: __('Please configure recipients with phone number fields for SMPP SMS notifications.'),
				indicator: 'blue'
			});
		}
	},
	
	document_type: function(frm) {
		// When document type changes, update recipient field options
		if (frm.doc.channel === 'SMPP SMS') {
			setup_recipient_field_filtering(frm);
			
			// Clear existing recipients as document type changed
			if (frm.doc.recipients && frm.doc.recipients.length > 0) {
				frappe.msgprint({
					title: __('Document Type Changed'),
					message: __('Please reconfigure recipients for the new document type.'),
					indicator: 'orange'
				});
			}
		}
	}
});


// Child table: Notification Recipient
frappe.ui.form.on('Notification Recipient', {
	recipients_add: function(frm, cdt, cdn) {
		// When a new recipient row is added
		if (frm.doc.channel === 'SMPP SMS') {
			setup_phone_field_filter(frm, cdt, cdn);
		}
	},
	
	receiver_by_document_field: function(frm, cdt, cdn) {
		// When recipient field is selected
		let row = locals[cdt][cdn];
		
		if (frm.doc.channel === 'SMPP SMS' && row.receiver_by_document_field) {
			// Validate that selected field is a phone field
			validate_phone_field(frm, row);
		}
	}
});


/**
 * Setup recipient field filtering for SMPP SMS
 */
function setup_recipient_field_filtering(frm) {
	if (frm.doc.channel !== 'SMPP SMS' || !frm.doc.document_type) {
		return;
	}
	
	// Get phone fields from the selected document type
	get_phone_fields(frm.doc.document_type).then(phone_fields => {
		if (phone_fields.length === 0) {
			frappe.msgprint({
				title: __('No Phone Fields Found'),
				message: __('The selected Document Type "{0}" does not have any Phone fields. Please add a Phone field to the DocType or select a different Document Type.', [frm.doc.document_type]),
				indicator: 'orange'
			});
			return;
		}
		
		// Store phone fields for later use
		frm._smpp_phone_fields = phone_fields;
		
		// Apply filter to existing recipient rows
		if (frm.doc.recipients) {
			frm.doc.recipients.forEach((row, idx) => {
				setup_phone_field_filter(frm, row.doctype, row.name);
			});
		}
	});
}


/**
 * Setup phone field filter for a specific recipient row
 */
function setup_phone_field_filter(frm, cdt, cdn) {
	if (frm.doc.channel !== 'SMPP SMS') {
		return;
	}
	
	// Get the grid row
	let grid_row = frm.fields_dict.recipients.grid.grid_rows_by_docname[cdn];
	
	if (!grid_row) {
		return;
	}
	
	// Get the receiver_by_document_field field
	let field = grid_row.get_field('receiver_by_document_field');
	
	if (!field) {
		return;
	}
	
	// If we already have phone fields cached, use them
	if (frm._smpp_phone_fields) {
		update_field_options(field, frm._smpp_phone_fields);
	} else if (frm.doc.document_type) {
		// Otherwise, fetch phone fields
		get_phone_fields(frm.doc.document_type).then(phone_fields => {
			frm._smpp_phone_fields = phone_fields;
			update_field_options(field, phone_fields);
		});
	}
}


/**
 * Get phone fields from a doctype
 */
function get_phone_fields(doctype) {
	return new Promise((resolve, reject) => {
		frappe.model.with_doctype(doctype, () => {
			let meta = frappe.get_meta(doctype);
			let phone_fields = [];
			
			// Get direct phone fields
			meta.fields.forEach(df => {
				if (df.fieldtype === 'Phone') {
					phone_fields.push({
						label: df.label,
						value: df.fieldname,
						description: `Phone field: ${df.label}`
					});
				}
				
				// Also check Link fields for common phone fields
				if (df.fieldtype === 'Link' && df.options) {
					// Add linked doctype phone fields (e.g., customer.mobile_no)
					let linked_meta = frappe.get_meta(df.options);
					if (linked_meta) {
						linked_meta.fields.forEach(linked_df => {
							if (linked_df.fieldtype === 'Phone') {
								phone_fields.push({
									label: `${df.label} → ${linked_df.label}`,
									value: `${df.fieldname}.${linked_df.fieldname}`,
									description: `Phone field from ${df.label}: ${linked_df.label}`
								});
							}
						});
					}
				}
			});
			
			resolve(phone_fields);
		});
	});
}


/**
 * Update field options with phone fields
 */
function update_field_options(field, phone_fields) {
	if (!field || !phone_fields || phone_fields.length === 0) {
		return;
	}
	
	// Create options string
	let options = phone_fields.map(f => f.value).join('\n');
	
	// Update field options
	field.df.options = options;
	field.refresh();
	
	// Add description
	if (field.df.description !== 'Select a phone number field from the document') {
		field.df.description = 'Select a phone number field from the document';
		field.refresh();
	}
}


/**
 * Validate that selected field is a phone field
 */
function validate_phone_field(frm, row) {
	if (!frm._smpp_phone_fields) {
		return;
	}
	
	let is_valid = frm._smpp_phone_fields.some(f => f.value === row.receiver_by_document_field);
	
	if (!is_valid) {
		frappe.msgprint({
			title: __('Invalid Field'),
			message: __('Please select a valid phone number field for SMPP SMS notifications.'),
			indicator: 'red'
		});
		
		// Clear the invalid field
		frappe.model.set_value(row.doctype, row.name, 'receiver_by_document_field', '');
	}
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

