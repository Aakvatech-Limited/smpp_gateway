// Copyright (c) 2025, aakvatech and contributors
// For license information, please see license.txt

// frappe.ui.form.on("SMPP SMS Template", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('SMPP SMS Template', {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Test Template'), function() {
                test_template(frm);
            });
            
            frm.add_custom_button(__('Send SMS'), function() {
                send_template_sms(frm);
            });
        }
        
        if (frm.doc.message_template) {
            add_template_preview(frm);
        }
    },
    
    message_template: function(frm) {
        calculate_template_stats(frm);
        add_template_preview(frm);
    }
});

function test_template(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Test Template'),
        fields: []
    });
    
    if (frm.doc.variables) {
        frm.doc.variables.forEach(function(variable) {
            d.fields_list.push({
                fieldtype: variable.variable_type === 'number' ? 'Int' : 'Data',
                fieldname: variable.variable_name,
                label: variable.variable_name,
                reqd: variable.is_required,
                default: variable.default_value
            });
        });
    }
    
    d.fields_list.push({
        fieldtype: 'Section Break',
        label: __('Preview')
    });
    
    d.fields_list.push({
        fieldtype: 'Long Text',
        fieldname: 'preview',
        label: __('Message Preview'),
        read_only: 1
    });
    
    d.set_primary_action(__('Generate Preview'), function() {
        const values = d.get_values();
        generate_template_preview(frm, values, d);
    });
    
    d.show();
}

function generate_template_preview(frm, values, dialog) {
    let preview = frm.doc.message_template;
    
    for (let key in values) {
        if (key !== 'preview') {
            const regex = new RegExp('\\{\\{\\s*' + key + '\\s*\\}\\}', 'g');
            preview = preview.replace(regex, values[key]);
        }
    }
    
    dialog.set_value('preview', preview);
}

function calculate_template_stats(frm) {
    if (!frm.doc.message_template) return;
    
    const template = frm.doc.message_template;
    const char_count = template.length;
    
    const estimated_length = char_count + (frm.doc.variables ? frm.doc.variables.length * 10 : 0);
    const sms_parts = estimated_length > 160 ? Math.ceil(estimated_length / 153) : 1;
    
    frm.set_value('character_count', char_count);
    frm.set_value('sms_parts', sms_parts);
}

function add_template_preview(frm) {
    if (!frm.doc.message_template) return;
    
    let preview = frm.doc.message_template;
    
    if (frm.doc.variables) {
        frm.doc.variables.forEach(function(variable) {
            const pattern = new RegExp('\\{\\{\\s*' + variable.variable_name + '\\s*\\}\\}', 'g');
            const sample_value = variable.default_value || `[${variable.variable_name}]`;
            preview = preview.replace(pattern, sample_value);
        });
    }
    
    frm.set_value('sample_output', preview);
}

function send_template_sms(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Send Template SMS'),
        fields: [
            {
                fieldtype: 'Long Text',
                fieldname: 'recipients',
                label: __('Recipients (one phone number per line)'),
                reqd: 1
            },
            {
                fieldtype: 'Section Break',
                label: __('Template Data (JSON format)')
            },
            {
                fieldtype: 'Code',
                fieldname: 'template_data',
                label: __('Template Data'),
                options: 'JSON'
            }
        ]
    });
    
    d.set_primary_action(__('Send SMS'), function() {
        const values = d.get_values();
        const recipients = values.recipients.split('\n').filter(r => r.trim());
        
        let template_data = {};
        try {
            template_data = JSON.parse(values.template_data || '{}');
        } catch (e) {
            frappe.msgprint(__('Invalid JSON in template data'));
            return;
        }
        
        frappe.call({
            method: 'smpp_gateway.api.sms_api.send_template_sms',
            args: {
                template_name: frm.doc.name,
                recipients: recipients,
                template_data: template_data
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint(__('SMS sent successfully'));
                    d.hide();
                } else {
                    frappe.msgprint(__('Failed to send SMS'));
                }
            }
        });
    });
    
    d.show();
}
