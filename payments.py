"""
Destined — Paid Reading Module
Stripe payments + Anthropic AI reading generation
"""
import os, json, http.client, ssl, urllib.parse, base64

STRIPE_SECRET_KEY   = os.environ.get('STRIPE_SECRET_KEY', '')
ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')
READING_PRICE_CENTS = 999  # $9.99

def generate_ai_reading(user):
    if not ANTHROPIC_API_KEY:
        return None, "Anthropic API key not configured"
    try:
        chart    = json.loads(user.get('chart_json', '{}'))
        planets  = {p['key']: p for p in chart.get('planets', [])}
        houses   = {h['house']: h for h in chart.get('houses', [])}
        def ps(key):
            p = planets.get(key, {})
            h = f" in House {p.get('house','')}" if p.get('house') else ''
            r = ' (retrograde)' if p.get('retrograde') else ''
            return f"{p.get('sign','Unknown')}{h}{r}" if p else 'Unknown'
        h5  = houses.get(5,  {}).get('sign', '?')
        h7  = houses.get(7,  {}).get('sign', '?')
        h11 = houses.get(11, {}).get('sign', '?')
        prompt = f"""You are a professional Western astrologer writing a deep, personalized natal chart reading.
Write in a warm, insightful, poetic but grounded tone. Be specific to the placements — not generic.
Speak directly and personally to {user.get('name','this person')}.

Born: {user.get('birth_month')}/{user.get('birth_day')}/{user.get('birth_year')} in {user.get('birth_city','their birth city')}.

Natal chart:
- Sun: {ps('sun')}
- Moon: {ps('moon')}
- Ascendant: {ps('asc')}
- Mercury: {ps('mercury')}
- Venus: {ps('venus')}
- Mars: {ps('mars')}
- Jupiter: {ps('jupiter')}
- Saturn: {ps('saturn')}
- Uranus: {ps('uranus')}
- Neptune: {ps('neptune')}
- Pluto: {ps('pluto')}
- North Node: {ps('northNode')}
- 5th House (Romance): {h5}
- 7th House (Partnership): {h7}
- 11th House (Community): {h11}

Write a complete natal chart reading with these 5 sections (2-3 rich paragraphs each):

1. YOUR SOUL BLUEPRINT — Sun, Moon and Rising: who you are at your core, your emotional world, how others first experience you

2. YOUR MIND & VOICE — Mercury: how you think, communicate and make decisions

3. LOVE, BEAUTY & DESIRE — Venus, Mars, 5th and 7th houses: how you love, what you need in a partner, your romantic style

4. YOUR DESTINY & PURPOSE — North Node, Jupiter, Saturn: your soul mission, where you are growing, your gifts and challenges

5. YOUR DESTINED PARTNER — Based on all placements, describe the astrological profile of the person most destined for them: their likely Sun, Moon, Rising signs, their qualities, how they will meet

End with YOUR COSMIC MESSAGE — one powerful personal message from the stars.

Write beautifully. Be specific. Make them feel truly seen."""

        payload = json.dumps({
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages":   [{"role": "user", "content": prompt}]
        }).encode('utf-8')
        headers = {
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
            "User-Agent":        "Destined-App/1.0",
        }
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.anthropic.com", context=ctx, timeout=60)
        conn.request("POST", "/v1/messages", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        if resp.status == 200:
            return json.loads(body)['content'][0]['text'], None
        else:
            return None, f"Anthropic {resp.status}: {body}"
    except Exception as e:
        return None, str(e)


def send_reading_email(to_email, name, reading_text, user_id, resend_key):
    matches_url = f"https://destined.cuartoastral.com/destined-matches.html?userId={user_id}"
    paras = ''
    for section in reading_text.split('\n\n'):
        s = section.strip()
        if not s: continue
        if any(s.startswith(x) for x in ('1.','2.','3.','4.','5.','YOUR ')):
            paras += f'<h2 style="font-family:Georgia,serif;font-size:13px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:32px 0 12px;">{s}</h2>'
        else:
            paras += f'<p style="font-size:15px;color:#c8c8e0;line-height:1.9;margin:0 0 16px;">{s}</p>'

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#06060f;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#06060f;padding:40px 20px;">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="text-align:center;padding:40px 40px 32px;border-bottom:1px solid rgba(201,168,76,.2);">
  <div style="font-size:11px;letter-spacing:6px;color:#c9a84c;text-transform:uppercase;margin-bottom:8px;">DESTINED</div>
  <div style="font-size:11px;letter-spacing:3px;color:rgba(168,168,192,.5);text-transform:uppercase;">Your Complete Natal Reading</div>
</td></tr>
<tr><td style="background:#0d0b1e;padding:48px 40px;">
  <p style="font-size:13px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:0 0 12px;">A reading for {name}</p>
  <h1 style="font-size:28px;font-weight:300;color:#f0eefc;line-height:1.3;margin:0 0 32px;">Your stars have<br><em style="color:#e8c96d;">spoken.</em></h1>
  {paras}
  <div style="text-align:center;margin-top:40px;">
    <a href="{matches_url}" style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8721e);color:#06060f;padding:16px 40px;font-size:12px;letter-spacing:3px;text-decoration:none;text-transform:uppercase;">View Your Matches →</a>
  </div>
</td></tr>
<tr><td style="padding:24px;text-align:center;">
  <p style="font-size:11px;color:rgba(168,168,192,.3);letter-spacing:2px;text-transform:uppercase;margin:0;">DESTINED · destined.cuartoastral.com</p>
</td></tr>
</table></td></tr></table></body></html>"""

    try:
        payload = json.dumps({
            "from":    "Destined <info@cuartoastral.com>",
            "to":      [to_email],
            "subject": f"✨ {name}, your complete natal reading is here",
            "html":    html,
        }).encode('utf-8')
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "User-Agent":    "Destined-App/1.0 Python/3.11",
        }
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.resend.com", context=ctx, timeout=15)
        conn.request("POST", "/emails", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp.status in (200, 201), body
    except Exception as e:
        return False, str(e)


def create_stripe_session(user, base_url):
    if not STRIPE_SECRET_KEY:
        return None, "Stripe not configured"
    try:
        user_id = user['id']
        payload = urllib.parse.urlencode({
            'payment_method_types[]':                             'card',
            'line_items[0][price_data][currency]':                'usd',
            'line_items[0][price_data][unit_amount]':             str(READING_PRICE_CENTS),
            'line_items[0][price_data][product_data][name]':      f"Complete Natal Reading for {user['name']}",
            'line_items[0][price_data][product_data][description]': 'Personalized AI natal chart reading delivered to your email',
            'line_items[0][quantity]':                            '1',
            'mode':                                               'payment',
            'success_url': f"{base_url}/destined-chart.html?reading=success&userId={user_id}",
            'cancel_url':  f"{base_url}/destined-chart.html?reading=cancelled",
            'customer_email': user.get('email',''),
            'metadata[user_id]':    user_id,
            'metadata[user_email]': user.get('email',''),
            'metadata[user_name]':  user.get('name',''),
        }).encode('utf-8')
        auth = base64.b64encode(f"{STRIPE_SECRET_KEY}:".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type':  'application/x-www-form-urlencoded',
            'User-Agent':    'Destined-App/1.0',
        }
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.stripe.com", context=ctx, timeout=15)
        conn.request("POST", "/v1/checkout/sessions", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        result = json.loads(body)
        if resp.status == 200:
            return result, None
        else:
            return None, f"Stripe {resp.status}: {body}"
    except Exception as e:
        return None, str(e)
