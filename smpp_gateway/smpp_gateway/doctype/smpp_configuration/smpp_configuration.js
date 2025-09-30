// Copyright (c) 2025, aakvatech and contributors
// For license information, please see license.txt

// frappe.ui.form.on("SMPP Configuration", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('SMPP Configuration', {
    refresh: function (frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Test Connection'), function () {
                test_smpp_connection(frm);
            });

            frm.add_custom_button(__('View Connection Logs'), function () {
                frappe.route_options = { "connection_name": frm.doc.name };
                frappe.set_route("List", "SMPP Connection Log");
            });
        }

        add_connection_status(frm);
    },

    is_default: function (frm) {
        if (frm.doc.is_default) {
            frappe.msgprint(__('This will be set as the default SMPP configuration'));
        }
    }
});

function test_smpp_connection(frm) {
    frappe.show_alert({
        message: __('Testing SMPP connection...'),
        indicator: 'blue'
    });

    frappe.call({
        method: 'smpp_gateway.smpp_gateway.api.sms_api.test_smpp_connection',
        args: {
            config_name: frm.doc.name
        },
        callback: function (r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Connection test successful'),
                    indicator: 'green'
                });
            } else {
                frappe.show_alert({
                    message: __('Connection test failed: ') + (r.message.message || 'Unknown error'),
                    indicator: 'red'
                });
            }
        }
    });
}

function add_connection_status(frm) {
    frappe.call({
        method: 'smpp_gateway.smpp_gateway.api.sms_api.get_smpp_connection_status',
        args: {
            config_name: frm.doc.name
        },
        callback: function (r) {
            if (r.message && r.message.success) {
                const status = r.message.connected ? 'Connected' : 'Disconnected';
                const indicator = r.message.connected ? 'green' : 'red';

                const status_html = `
                    <div class="alert alert-${r.message.connected ? 'success' : 'warning'}">
                        <strong>Connection Status:</strong> ${status}<br>
                        <strong>Host:</strong> ${r.message.host}:${r.message.port}<br>
                        <strong>System ID:</strong> ${r.message.system_id}
                    </div>
                `;

                frm.dashboard.add_comment(status_html, indicator, true);
            }
        }
    });
}