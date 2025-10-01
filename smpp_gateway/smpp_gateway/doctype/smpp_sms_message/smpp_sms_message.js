// Copyright (c) 2025, aakvatech and contributors
// For license information, please see license.txt

// frappe.ui.form.on("SMPP SMS Message", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('SMPP SMS Message', {
    refresh: function (frm) {
        if (frm.doc.status === 'Draft') {
            frm.add_custom_button(__('Send Now'), function () {
                send_sms_now(frm);
            }, __('Actions'));

            frm.add_custom_button(__('Queue for Sending'), function () {
                queue_sms(frm);
            }, __('Actions'));
        }

        if (frm.doc.status === 'Sent' && frm.doc.registered_delivery) {
            frm.add_custom_button(__('Check Delivery Status'), function () {
                check_delivery_status(frm);
            }, __('Actions'));
        }

        if (frm.doc.message_id) {
            frm.add_custom_button(__('View Delivery Receipt'), function () {
                frappe.route_options = { "original_message": frm.doc.name };
                frappe.set_route("List", "SMPP Delivery Receipt");
            }, __('View'));
        }

        add_message_preview(frm);

        if (frm.doc.status === 'Queued' || frm.doc.status === 'Sent') {
            setup_status_refresh(frm);
        }
    },

    message_text: function (frm) {
        validate_message_content(frm);
    },

    recipient_number: function (frm) {
        validate_phone_number(frm);
    }
});

function send_sms_now(frm) {
    frappe.confirm(
        __('Are you sure you want to send this SMS immediately?'),
        function () {
            frappe.call({
                method: 'smpp_gateway.smpp_gateway.api.sms_api.send_sms',
                args: {
                    recipient_number: frm.doc.recipient_number,
                    message_text: frm.doc.message_text,
                    sender_id: frm.doc.sender_id,
                    priority: frm.doc.priority,
                    smpp_config: frm.doc.smpp_configuration
                },
                callback: function (r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(__('SMS sent successfully'));
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Failed to send SMS: ') + (r.message.message || 'Unknown error'));
                    }
                }
            });
        }
    );
}

function validate_message_content(frm) {
    if (!frm.doc.message_text) return;

    const message_text = frm.doc.message_text;
    const char_count = message_text.length;

    const is_unicode = /[^\x00-\x7F]/.test(message_text);
    const encoding = is_unicode ? 'Unicode (UCS2)' : 'GSM 7-bit';

    const single_limit = is_unicode ? 70 : 160;
    const multi_limit = is_unicode ? 67 : 153;

    let sms_parts = 1;
    if (char_count > single_limit) {
        sms_parts = Math.ceil(char_count / multi_limit);
    }

    const info_html = `
        <div class="alert alert-info">
            <strong>Message Info:</strong><br>
            Characters: ${char_count}<br>
            Encoding: ${encoding}<br>
            SMS Parts: ${sms_parts}<br>
            ${sms_parts > 5 ? '<span class="text-danger">Warning: Too many SMS parts!</span>' : ''}
        </div>
    `;

    frm.dashboard.add_comment(info_html, 'blue', true);
}

function validate_phone_number(frm) {
    if (!frm.doc.recipient_number) return;

    const phone = frm.doc.recipient_number;
    const phone_regex = /^\+?[1-9]\d{1,14}$/;

    if (!phone_regex.test(phone.replace(/[^\d+]/g, ''))) {
        frappe.msgprint({
            title: __('Invalid Phone Number'),
            message: __('Please enter a valid phone number'),
            indicator: 'red'
        });
    }
}

function add_message_preview(frm) {
    if (frm.doc.message_text && frm.doc.message_text.length > 0) {
        const preview_html = `
            <div class="form-message blue">
                <div><strong>Message Preview:</strong></div>
                <div style="border: 1px solid #ccc; padding: 10px; margin-top: 5px; background: #f9f9f9;">
                    ${frm.doc.message_text.replace(/\n/g, '<br>')}
                </div>
            </div>
        `;
        frm.dashboard.add_comment(preview_html, 'blue', true);
    }
}

function check_delivery_status(frm) {
    // Show loading indicator
    frappe.show_alert({
        message: __('Querying delivery status from SMSC...'),
        indicator: 'blue'
    }, 3);

    frappe.call({
        method: 'smpp_gateway.smpp_gateway.api.sms_api.query_sms_delivery_status',
        args: {
            sms_id: frm.doc.name
        },
        callback: function (r) {
            if (r.message && r.message.success) {
                const status_html = `
                    <table class="table table-bordered">
                        <tr><th>Message ID</th><td>${r.message.message_id || 'N/A'}</td></tr>
                        <tr><th>Status</th><td><span class="indicator ${get_status_indicator(r.message.status)}">${r.message.status}</span></td></tr>
                        <tr><th>SMPP Status</th><td><span class="badge badge-${get_smpp_status_color(r.message.smpp_status)}">${r.message.smpp_status || 'N/A'}</span></td></tr>
                        <tr><th>Recipient</th><td>${r.message.recipient_number || 'N/A'}</td></tr>
                        <tr><th>Sender ID</th><td>${r.message.sender_id || 'N/A'}</td></tr>
                        <tr><th>Sent Time</th><td>${r.message.sent_time || 'N/A'}</td></tr>
                        <tr><th>Delivered Time</th><td>${r.message.delivered_time || 'N/A'}</td></tr>
                        ${r.message.final_date ? `<tr><th>Final Date</th><td>${r.message.final_date}</td></tr>` : ''}
                        ${r.message.error_code ? `<tr><th>Error Code</th><td>${r.message.error_code}</td></tr>` : ''}
                    </table>
                    <div class="mt-3">
                        <small class="text-muted">Status queried directly from SMSC using query_sm PDU</small>
                    </div>
                `;

                frappe.msgprint({
                    title: __('SMS Delivery Status'),
                    message: status_html,
                    indicator: get_status_indicator(r.message.status)
                });

                // Refresh the form to show updated status
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Query Failed'),
                    message: r.message ? r.message.message : 'Failed to query delivery status',
                    indicator: 'red'
                });
            }
        },
        error: function (r) {
            frappe.msgprint({
                title: __('Error'),
                message: 'Failed to query delivery status. Please check your SMPP connection.',
                indicator: 'red'
            });
        }
    });
}

function get_status_indicator(status) {
    const indicators = {
        'Draft': 'grey',
        'Queued': 'orange',
        'Sent': 'blue',
        'Delivered': 'green',
        'Failed': 'red',
        'Expired': 'red',
        'Rejected': 'red'
    };
    return indicators[status] || 'grey';
}

function get_smpp_status_color(smpp_status) {
    const colors = {
        'DELIVERED': 'success',
        'ENROUTE': 'info',
        'EXPIRED': 'danger',
        'UNDELIVERABLE': 'danger',
        'DELETED': 'danger',
        'ACCEPTED': 'success',
        'REJECTED': 'danger',
        'UNKNOWN': 'warning'
    };
    return colors[smpp_status] || 'secondary';
}

function setup_status_refresh(frm) {
    const refresh_interval = setInterval(function () {
        if (frm.doc.status === 'Delivered' || frm.doc.status === 'Failed') {
            clearInterval(refresh_interval);
            return;
        }

        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'SMPP SMS Message',
                filters: { name: frm.doc.name },
                fieldname: ['status', 'smpp_status', 'delivered_time', 'error_message']
            },
            callback: function (r) {
                if (r.message && (r.message.status !== frm.doc.status)) {
                    frm.reload_doc();
                }
            }
        });
    }, 30000);
}

function queue_sms(frm) {
    frappe.call({
        method: 'frappe.client.save',
        args: {
            doc: frm.doc
        },
        callback: function (r) {
            if (r.message) {
                frappe.msgprint(__('SMS queued for sending'));
                frm.reload_doc();
            }
        }
    });
}