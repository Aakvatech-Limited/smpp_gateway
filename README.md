# SMPP Gateway

SMPP (Short Message Peer-to-Peer) Gateway integration for Frappe/ERPNext that enables SMS messaging through SMPP protocol connections.

## Features

- **SMPP Protocol Support**: Direct integration with SMPP-compatible SMS gateways
- **SMS Settings Integration**: Works with Frappe's standard SMS Settings
- **Queue Management**: Automatic SMS queue processing and retry logic
- **Connection Management**: Persistent SMPP connections with automatic reconnection
- **Delivery Receipts**: Track message delivery status and receipts
- **Template Support**: SMS templates with variable substitution
- **Notification Integration**: Send SMS notifications for document events

## Installation

```bash
# Install the app
bench get-app smpp_gateway
bench --site [site-name] install-app smpp_gateway

# Run migration to set up SMS Settings integration
bench --site [site-name] migrate
```

## Quick Start

1. **Configure SMPP Connection**
   - Go to SMPP Configuration doctype
   - Add your SMPP provider details (host, port, username, password)
   - Set as default and active

2. **Create SMS Notification**
   - Go to Notification doctype
   - Select "SMS" as channel (not "SMPP SMS")
   - Configure recipients and message template
   - SMS will be sent via SMPP Gateway automatically

## What Changed (v2.0)

- **Before**: Used custom "SMPP SMS" channel with notification overrides
- **After**: Uses standard "SMS" channel through SMS Settings integration
- **Migration**: Automatic migration converts existing notifications

## Architecture

```
Frappe Notification (SMS) → SMS Settings → HTTP Bridge → SMPP Client → SMSC
```

The HTTP bridge (`/api/method/smpp_gateway.smpp_gateway.api.http_bridge.send_sms`) translates SMS Settings requests to SMPP calls.

## Requirements

- Frappe Framework v13+
- Python 3.6+
- SMPP provider account
- Network access to SMPP gateway

## License

MIT