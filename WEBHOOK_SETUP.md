# Email Tracking Setup Guide

## How Email Delivery and Open Tracking Works

Resend automatically tracks email delivery and opens through webhooks. When an email is:
- **Delivered**: Resend sends a `email.delivered` webhook
- **Opened**: Resend sends a `email.opened` webhook  
- **Clicked**: Resend sends a `email.clicked` webhook
- **Bounced**: Resend sends a `email.bounced` webhook

## Current Implementation

Your application already has:
1. ✅ Webhook endpoint at `/api/v1/webhooks/resend`
2. ✅ Event tracking in `email_events` table
3. ✅ Campaign lead status updates (opened, clicked, bounced flags)
4. ✅ Analytics service that queries these events

## Setup Steps

### 1. Get Your Webhook URL

Your webhook endpoint is:
```
https://your-domain.com/api/v1/webhooks/resend
```

**For local development**, you'll need to expose your local server:
- Use **ngrok**: `ngrok http 8000`
- Or use **localtunnel**: `npx localtunnel --port 8000`
- Copy the public URL (e.g., `https://abc123.ngrok.io/api/v1/webhooks/resend`)

### 2. Configure Webhook in Resend Dashboard

1. Go to [Resend Webhooks](https://resend.com/webhooks)
2. Click **"Add Webhook"**
3. Enter your webhook URL:
   - Production: `https://your-domain.com/api/v1/webhooks/resend`
   - Development: `https://your-ngrok-url.ngrok.io/api/v1/webhooks/resend`
4. Select the events you want to track:
   - ✅ `email.sent` (optional - you already track this when sending)
   - ✅ `email.delivered` (required for delivery tracking)
   - ✅ `email.opened` (required for open tracking)
   - ✅ `email.clicked` (required for click tracking)
   - ✅ `email.bounced` (required for bounce tracking)
   - ✅ `email.complained` (optional - spam complaints)
5. Click **"Add"** to save

### 3. Verify Webhook is Working

After setting up, test by:
1. Sending a test email through your application
2. Check your backend logs for webhook events
3. Check the `email_events` table in your database
4. Check the campaign detail page - tracking should update

### 4. Enable Open Tracking (Already Enabled by Default)

Resend automatically tracks opens by default. No additional configuration needed in your code.

However, if you want to explicitly enable it, you can add tracking parameters when sending:

```python
params = {
    "from": from_email,
    "to": to_email,
    "subject": subject,
    "html": html_body,
    "track_opens": True,  # Explicitly enable (default: True)
    "track_clicks": True,  # Explicitly enable (default: True)
}
```

## How It Works

### Flow Diagram

```
1. Send Email
   └─> Resend API
       └─> Returns email_id
           └─> Store in campaign_lead.resend_message_id

2. Email Delivered
   └─> Resend sends webhook: email.delivered
       └─> POST /api/v1/webhooks/resend
           └─> Find campaign_lead by resend_message_id
               └─> Create EmailEvent (type: DELIVERED)
                   └─> Analytics updates

3. Email Opened
   └─> Resend sends webhook: email.opened
       └─> POST /api/v1/webhooks/resend
           └─> Find campaign_lead by resend_message_id
               └─> Create EmailEvent (type: OPENED)
                   └─> Update campaign_lead.opened = True
                       └─> Analytics updates

4. Link Clicked
   └─> Resend sends webhook: email.clicked
       └─> POST /api/v1/webhooks/resend
           └─> Find campaign_lead by resend_message_id
               └─> Create EmailEvent (type: CLICKED)
                   └─> Update campaign_lead.clicked = True
                       └─> Analytics updates
```

## Troubleshooting

### Webhooks Not Received

1. **Check webhook URL is accessible:**
   ```bash
   curl -X POST https://your-domain.com/api/v1/webhooks/resend \
     -H "Content-Type: application/json" \
     -d '{"type": "email.delivered", "data": {"email_id": "test"}}'
   ```

2. **Check Resend dashboard:**
   - Go to Webhooks → Your webhook
   - Check "Recent Events" tab
   - Look for failed deliveries

3. **Check backend logs:**
   - Look for webhook processing errors
   - Check if `email_id` is being found in `campaign_leads`

### Events Not Showing in Analytics

1. **Verify webhook is processing:**
   - Check `email_events` table for new records
   - Check backend logs for webhook processing

2. **Verify email_id matching:**
   - Ensure `campaign_lead.resend_message_id` matches Resend's `email_id`
   - Check webhook payload in Resend dashboard

3. **Check analytics query:**
   - Verify `EmailEvent` records exist
   - Check `campaign_lead` flags are being updated

### Open Tracking Not Working

1. **Verify opens are enabled:**
   - Check Resend account settings
   - Opens are tracked by default

2. **Check email client:**
   - Some email clients block tracking pixels
   - Gmail, Outlook may not always fire open events

3. **Check webhook events:**
   - Verify `email.opened` events are being received
   - Check Resend dashboard for open events

## Testing Locally

### Using ngrok:

1. Install ngrok: `brew install ngrok` (Mac) or download from ngrok.com
2. Start your backend: `cd backend && uv run python run_server.py`
3. Start ngrok: `ngrok http 8000`
4. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
5. Configure webhook in Resend: `https://abc123.ngrok.io/api/v1/webhooks/resend`
6. Send a test email and watch for webhook events

### Testing Webhook Manually:

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/resend \
  -H "Content-Type: application/json" \
  -d '{
    "type": "email.delivered",
    "data": {
      "email_id": "your-email-id-here",
      "to": "test@example.com",
      "from": "sender@example.com"
    }
  }'
```

## Production Checklist

- [ ] Webhook URL is publicly accessible (HTTPS)
- [ ] Webhook is configured in Resend dashboard
- [ ] All required events are selected (delivered, opened, clicked, bounced)
- [ ] Webhook signature verification (optional but recommended)
- [ ] Monitoring/alerting for webhook failures
- [ ] Database indexes on `resend_message_id` for fast lookups

## Additional Notes

- **Open tracking** uses a 1x1 pixel image embedded in emails
- **Click tracking** rewrites links in emails to go through Resend first
- Some email clients may block tracking pixels (privacy features)
- Delivery tracking is more reliable than open tracking
- Webhooks are sent in real-time (usually within seconds)
