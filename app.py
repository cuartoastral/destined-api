"""
Destined Natal Chart API
Swiss Ephemeris + built-in timezone database + Supabase user storage.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe
import math, os, urllib.request, urllib.parse, json, hashlib
from payments import generate_ai_reading, send_reading_email, create_stripe_session

app = Flask(__name__)
CORS(app)
swe.set_ephe_path('')

# ── Supabase connection (set these in Render environment variables) ──
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

def supabase_request(method, table, data=None, params=None, record_id=None):
    """Make a request to Supabase REST API."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None, "Supabase not configured"
    
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if record_id:
        url += f"?id=eq.{record_id}"
    if params:
        separator = '&' if '?' in url else '?'
        url += separator + '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k,v in params.items())
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }
    
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return None, f"HTTP {e.code}: {error_body}"
    except Exception as e:
        return None, str(e)


# ── Timezone database ──
TZ_DB = {
    'America/New_York': -5, 'America/Chicago': -6, 'America/Denver': -7,
    'America/Los_Angeles': -8, 'America/Anchorage': -9, 'America/Honolulu': -10,
    'America/Phoenix': -7, 'America/Detroit': -5, 'America/Indiana/Indianapolis': -5,
    'America/Bogota': -5, 'America/Lima': -5, 'America/Guayaquil': -5,
    'America/Caracas': -4, 'America/La_Paz': -4, 'America/Manaus': -4,
    'America/Halifax': -4, 'America/Santo_Domingo': -4, 'America/Puerto_Rico': -4,
    'America/Sao_Paulo': -3, 'America/Argentina/Buenos_Aires': -3,
    'America/Santiago': -4, 'America/Asuncion': -4, 'America/Montevideo': -3,
    'America/Noronha': -2, 'America/Toronto': -5, 'America/Vancouver': -8,
    'America/Winnipeg': -6, 'America/Edmonton': -7, 'America/St_Johns': -3.5,
    'America/Mexico_City': -6, 'America/Monterrey': -6, 'America/Tijuana': -8,
    'America/Guatemala': -6, 'America/El_Salvador': -6, 'America/Managua': -6,
    'America/Costa_Rica': -6, 'America/Panama': -5, 'America/Havana': -5,
    'America/Jamaica': -5, 'America/Nassau': -5,
    'Europe/London': 0, 'Europe/Dublin': 0, 'Europe/Lisbon': 0,
    'Europe/Paris': 1, 'Europe/Berlin': 1, 'Europe/Madrid': 1,
    'Europe/Rome': 1, 'Europe/Amsterdam': 1, 'Europe/Brussels': 1,
    'Europe/Vienna': 1, 'Europe/Zurich': 1, 'Europe/Stockholm': 1,
    'Europe/Oslo': 1, 'Europe/Copenhagen': 1, 'Europe/Warsaw': 1,
    'Europe/Prague': 1, 'Europe/Budapest': 1, 'Europe/Bratislava': 1,
    'Europe/Ljubljana': 1, 'Europe/Zagreb': 1, 'Europe/Belgrade': 1,
    'Europe/Sofia': 2, 'Europe/Bucharest': 2, 'Europe/Athens': 2,
    'Europe/Helsinki': 2, 'Europe/Tallinn': 2, 'Europe/Riga': 2,
    'Europe/Vilnius': 2, 'Europe/Kiev': 2, 'Europe/Minsk': 3,
    'Europe/Moscow': 3, 'Europe/Istanbul': 3,
    'Asia/Dubai': 4, 'Asia/Kabul': 4.5, 'Asia/Karachi': 5,
    'Asia/Kolkata': 5.5, 'Asia/Kathmandu': 5.75, 'Asia/Dhaka': 6,
    'Asia/Rangoon': 6.5, 'Asia/Bangkok': 7, 'Asia/Jakarta': 7,
    'Asia/Singapore': 8, 'Asia/Hong_Kong': 8, 'Asia/Shanghai': 8,
    'Asia/Taipei': 8, 'Asia/Manila': 8, 'Asia/Seoul': 9,
    'Asia/Tokyo': 9, 'Asia/Adelaide': 9.5, 'Australia/Darwin': 9.5,
    'Australia/Sydney': 10, 'Australia/Melbourne': 10, 'Australia/Brisbane': 10,
    'Australia/Perth': 8, 'Pacific/Auckland': 12, 'Pacific/Fiji': 12,
    'Pacific/Honolulu': -10, 'Pacific/Guam': 10,
    'Africa/Cairo': 2, 'Africa/Johannesburg': 2, 'Africa/Lagos': 1,
    'Africa/Nairobi': 3, 'Africa/Casablanca': 0, 'Africa/Accra': 0,
    'Africa/Addis_Ababa': 3, 'Africa/Khartoum': 3, 'Africa/Dar_es_Salaam': 3,
    'Asia/Jerusalem': 2, 'Asia/Riyadh': 3, 'Asia/Baghdad': 3,
    'Asia/Tehran': 3.5, 'Asia/Beirut': 2, 'Asia/Amman': 2,
}

DST_RULES = {
    'America/New_York': (1,[3,4,5,6,7,8,9,10]),
    'America/Chicago': (1,[3,4,5,6,7,8,9,10]),
    'America/Denver': (1,[3,4,5,6,7,8,9,10]),
    'America/Los_Angeles': (1,[3,4,5,6,7,8,9,10]),
    'America/Anchorage': (1,[3,4,5,6,7,8,9,10]),
    'America/Detroit': (1,[3,4,5,6,7,8,9,10]),
    'America/Indiana/Indianapolis': (1,[3,4,5,6,7,8,9,10]),
    'America/Toronto': (1,[3,4,5,6,7,8,9,10]),
    'America/Vancouver': (1,[3,4,5,6,7,8,9,10]),
    'America/Winnipeg': (1,[3,4,5,6,7,8,9,10]),
    'America/Edmonton': (1,[3,4,5,6,7,8,9,10]),
    'America/Halifax': (1,[3,4,5,6,7,8,9,10]),
    'America/Havana': (1,[3,4,5,6,7,8,9,10]),
    'America/Nassau': (1,[3,4,5,6,7,8,9,10]),
    'America/Sao_Paulo': (1,[10,11,12,1,2]),
    'America/Santiago': (1,[10,11,12,1,2,3]),
    'America/Asuncion': (1,[10,11,12,1,2,3]),
    'Europe/London': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Dublin': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Lisbon': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Paris': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Berlin': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Madrid': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Rome': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Amsterdam': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Stockholm': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Warsaw': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Athens': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Helsinki': (1,[3,4,5,6,7,8,9,10]),
    'Europe/Kiev': (1,[3,4,5,6,7,8,9,10]),
    'Australia/Sydney': (1,[10,11,12,1,2,3]),
    'Australia/Melbourne': (1,[10,11,12,1,2,3]),
    'Australia/Adelaide': (1,[10,11,12,1,2,3]),
    'Pacific/Auckland': (1,[9,10,11,12,1,2,3,4]),
}

GEO_TZ = [
    ((-4,13,-79,-66),'America/Bogota'),
    ((0,13,-73,-59),'America/Caracas'),
    ((-5,2,-82,-75),'America/Guayaquil'),
    ((-18,0,-81,-68),'America/Lima'),
    ((-23,-9,-70,-57),'America/La_Paz'),
    ((-56,-17,-76,-68),'America/Santiago'),
    ((-55,-21,-68,-53),'America/Argentina/Buenos_Aires'),
    ((-28,-19,-62,-54),'America/Asuncion'),
    ((-35,-30,-58,-53),'America/Montevideo'),
    ((-34,5,-74,-34),'America/Sao_Paulo'),
    ((14,33,-118,-86),'America/Mexico_City'),
    ((7,18,-93,-77),'America/Guatemala'),
    ((19,24,-85,-74),'America/Havana'),
    ((24,50,-83,-65),'America/New_York'),
    ((25,50,-104,-83),'America/Chicago'),
    ((31,50,-115,-104),'America/Denver'),
    ((32,50,-125,-115),'America/Los_Angeles'),
    ((54,72,-170,-130),'America/Anchorage'),
    ((18,23,-161,-154),'America/Honolulu'),
    ((48,60,-140,-114),'America/Vancouver'),
    ((49,60,-120,-110),'America/Edmonton'),
    ((49,60,-102,-88),'America/Winnipeg'),
    ((44,60,-64,-52),'America/Halifax'),
    ((49,61,-11,2),'Europe/London'),
    ((36,42,-10,-6),'Europe/Lisbon'),
    ((35,44,-9,5),'Europe/Madrid'),
    ((42,52,-5,8),'Europe/Paris'),
    ((46,55,6,18),'Europe/Berlin'),
    ((36,48,6,19),'Europe/Rome'),
    ((55,71,4,32),'Europe/Stockholm'),
    ((48,55,14,24),'Europe/Warsaw'),
    ((35,48,20,30),'Europe/Athens'),
    ((35,42,26,45),'Europe/Istanbul'),
    ((50,70,27,60),'Europe/Moscow'),
    ((22,32,24,37),'Africa/Cairo'),
    ((-35,-22,16,33),'Africa/Johannesburg'),
    ((4,14,2,15),'Africa/Lagos'),
    ((-5,5,33,42),'Africa/Nairobi'),
    ((29,34,34,36),'Asia/Jerusalem'),
    ((22,27,51,57),'Asia/Dubai'),
    ((16,32,36,56),'Asia/Riyadh'),
    ((25,40,44,64),'Asia/Tehran'),
    ((8,37,68,97),'Asia/Kolkata'),
    ((23,37,61,77),'Asia/Karachi'),
    ((20,27,88,93),'Asia/Dhaka'),
    ((18,53,73,135),'Asia/Shanghai'),
    ((24,46,122,146),'Asia/Tokyo'),
    ((33,38,126,130),'Asia/Seoul'),
    ((5,24,98,110),'Asia/Bangkok'),
    ((-8,7,95,141),'Asia/Singapore'),
    ((4,21,116,127),'Asia/Manila'),
    ((-44,-10,141,154),'Australia/Sydney'),
    ((-38,-26,129,141),'Australia/Adelaide'),
    ((-35,-14,113,129),'Australia/Perth'),
    ((-47,-34,166,178),'Pacific/Auckland'),
]

def geo_to_tz(lat, lon):
    for (lat_min,lat_max,lon_min,lon_max), tz_name in GEO_TZ:
        if lat_min<=lat<=lat_max and lon_min<=lon<=lon_max:
            return tz_name
    return None

def resolve_utc_offset(year, month, day, hour, minute, lat, lon):
    tz_name = geo_to_tz(lat, lon)
    if tz_name and tz_name in TZ_DB:
        base = TZ_DB[tz_name]
        is_dst = False
        extra = 0
        if tz_name in DST_RULES:
            dst_add, dst_months = DST_RULES[tz_name]
            if month in dst_months:
                if not (tz_name == 'America/Sao_Paulo' and year >= 2019):
                    is_dst = True
                    extra = dst_add
        return base + extra, tz_name, is_dst
    offset = round(lon / 15 * 2) / 2
    return offset, f'Estimated ({lon:.1f}°)', False

# ── Astrology constants ──
PLANETS = [
    (swe.SUN,'sun','Sun','☉','#f5c842'),
    (swe.MOON,'moon','Moon','☽','#c8c8e8'),
    (swe.MERCURY,'mercury','Mercury','☿','#90b8d0'),
    (swe.VENUS,'venus','Venus','♀','#e8a0a0'),
    (swe.MARS,'mars','Mars','♂','#e87050'),
    (swe.JUPITER,'jupiter','Jupiter','♃','#d4a860'),
    (swe.SATURN,'saturn','Saturn','♄','#a09070'),
    (swe.URANUS,'uranus','Uranus','♅','#80c8d0'),
    (swe.NEPTUNE,'neptune','Neptune','♆','#8080d0'),
    (swe.PLUTO,'pluto','Pluto','♇','#c080c0'),
    (swe.MEAN_NODE,'northNode','North Node','☊','#90c090'),
    (swe.CHIRON,'chiron','Chiron','⚷','#c8a870'),
]
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
SIGN_GLYPHS = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']
ELEMENTS = {
    'fire':['Aries','Leo','Sagittarius'],
    'earth':['Taurus','Virgo','Capricorn'],
    'air':['Gemini','Libra','Aquarius'],
    'water':['Cancer','Scorpio','Pisces'],
}
MODALITIES = {
    'cardinal':['Aries','Cancer','Libra','Capricorn'],
    'fixed':['Taurus','Leo','Scorpio','Aquarius'],
    'mutable':['Gemini','Virgo','Sagittarius','Pisces'],
}
NODE_MEANINGS = {
    'Aries':('Lead boldly. Your soul is learning independence and self-initiation.','A past of co-dependence and people-pleasing.'),
    'Taurus':('Build security and lasting value. Peace is your destiny.','A past of disruption, transformation, and impermanence.'),
    'Gemini':('Embrace curiosity, flexibility, and open communication.','A past of rigid, singular thinking and fixed beliefs.'),
    'Cancer':('Nurture yourself and others. Emotional safety is your path.','A past of relentless ambition and emotional suppression.'),
    'Leo':('Step into creative self-expression and heartfelt leadership.','A past of group anonymity and self-erasure.'),
    'Virgo':('Master service, discernment, and grounded contribution.','A past of escapism and avoidance of reality.'),
    'Libra':('Learn partnership, fairness, and the art of meeting another.','A past of fierce self-reliance and resistance to others.'),
    'Scorpio':('Embrace transformation, depth, and surrender of control.','A past of material comfort and resistance to change.'),
    'Sagittarius':('Seek truth, adventure, and expansive philosophy.','A past of small-picture thinking and rigid routine.'),
    'Capricorn':('Build mastery, discipline, and lasting legacy.','A past of emotional comfort without structure.'),
    'Aquarius':('Serve humanity, innovate, and find your people.','A past of ego, pride, and performance for approval.'),
    'Pisces':('Surrender to compassion, spirituality, and transcendence.','A past of hyper-criticism and over-analysis.'),
}
SOUL_SUMMARIES = {
    'fire':'A radiant, self-directed soul who leads with passion and needs a partner who can match their fire without smothering it.',
    'earth':'A grounded, loyal soul who builds love slowly and with intention — seeking permanence, not performance.',
    'air':'An intellectually alive soul who falls for minds first. They need a partner who can meet them in thought and in freedom.',
    'water':'A deeply feeling, intuitive soul who loves with their whole being — seeking emotional safety above all else.',
}

def lon_to_sign(lon):
    lon = lon % 360
    idx = int(lon / 30)
    return {'sign':SIGNS[idx],'glyph':SIGN_GLYPHS[idx],'degree':round(lon%30,4),'lon':round(lon,4)}

def get_element(sign):
    for el,signs in ELEMENTS.items():
        if sign in signs: return el
    return 'fire'

def get_modality(sign):
    for mod,signs in MODALITIES.items():
        if sign in signs: return mod
    return 'cardinal'

def get_house_of(planet_lon, cusps):
    planet_lon = planet_lon % 360
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i+1)%12] % 360
        if start < end:
            if start <= planet_lon < end: return i+1
        else:
            if planet_lon >= start or planet_lon < end: return i+1
    return 1

def calc_chart(year, month, day, hour, minute, lat, lon, has_time, utc_offset):
    """Core chart calculation — returns planets, houses, asc, mc."""
    utc_decimal = hour + minute/60.0 - utc_offset
    day_adj = day
    if utc_decimal < 0: utc_decimal += 24; day_adj -= 1
    elif utc_decimal >= 24: utc_decimal -= 24; day_adj += 1

    jd_ut = swe.julday(year, month, day_adj, utc_decimal)

    planets_result = []
    el_counts = {'fire':0,'earth':0,'air':0,'water':0}

    for planet_id, key, display_name, glyph, color in PLANETS:
        try:
            result, _ = swe.calc_ut(jd_ut, planet_id, swe.FLG_SWIEPH)
            planet_lon = result[0]
            is_retrograde = result[3] < 0
            sd = lon_to_sign(planet_lon)
            el = get_element(sd['sign'])
            if key in ['sun','moon','mercury','venus','mars','jupiter','saturn']:
                el_counts[el] += 1
            planets_result.append({
                'key':key,'name':display_name,'glyph':glyph,'color':color,
                'lon':round(planet_lon,4),'sign':sd['sign'],'signGlyph':sd['glyph'],
                'degree':round(sd['degree'],2),'element':el,
                'modality':get_modality(sd['sign']),
                'retrograde':is_retrograde,'house':None,
            })
        except: continue

    # South Node
    nn = next((p for p in planets_result if p['key']=='northNode'), None)
    if nn:
        sn_lon = (nn['lon']+180)%360
        sn_sd = lon_to_sign(sn_lon)
        planets_result.append({
            'key':'southNode','name':'South Node','glyph':'☋','color':'#c09080',
            'lon':round(sn_lon,4),'sign':sn_sd['sign'],'signGlyph':sn_sd['glyph'],
            'degree':round(sn_sd['degree'],2),'element':get_element(sn_sd['sign']),
            'modality':get_modality(sn_sd['sign']),'retrograde':False,'house':None,
        })

    houses_data = None
    asc_data = mc_data = None

    if has_time:
        house_result = swe.houses(jd_ut, lat, lon, b'P')
        if isinstance(house_result[0], (list,tuple)):
            cusps = house_result[0]; ascmc = house_result[1]
        else:
            cusps = house_result[:13]; ascmc = house_result[13:]
        asc_lon = float(ascmc[0]); mc_lon = float(ascmc[1])
        asc_sd = lon_to_sign(asc_lon); mc_sd = lon_to_sign(mc_lon)
        asc_data = {'lon':round(asc_lon,4),'sign':asc_sd['sign'],'signGlyph':asc_sd['glyph'],'degree':round(asc_sd['degree'],2)}
        mc_data  = {'lon':round(mc_lon,4),'sign':mc_sd['sign'],'signGlyph':mc_sd['glyph'],'degree':round(mc_sd['degree'],2)}
        house_cusps = [float(cusps[i]) for i in range(0,12)]
        houses_data = [{'house':i+1,'lon':round(c,4),'sign':lon_to_sign(c)['sign'],
                        'signGlyph':lon_to_sign(c)['glyph'],'degree':round(lon_to_sign(c)['degree'],2)}
                       for i,c in enumerate(house_cusps)]
        for p in planets_result:
            p['house'] = get_house_of(p['lon'], house_cusps)
        planets_result.append({
            'key':'asc','name':'Ascendant','glyph':'AC','color':'#e8c96d',
            'lon':round(asc_lon,4),'sign':asc_sd['sign'],'signGlyph':asc_sd['glyph'],
            'degree':round(asc_sd['degree'],2),'element':get_element(asc_sd['sign']),
            'modality':get_modality(asc_sd['sign']),'retrograde':False,'house':1,
        })
        planets_result.append({
            'key':'mc','name':'Midheaven','glyph':'MC','color':'#c9a84c',
            'lon':round(mc_lon,4),'sign':mc_sd['sign'],'signGlyph':mc_sd['glyph'],
            'degree':round(mc_sd['degree'],2),'element':get_element(mc_sd['sign']),
            'modality':get_modality(mc_sd['sign']),'retrograde':False,'house':10,
        })

    return planets_result, houses_data, asc_data, mc_data, el_counts, jd_ut


# ── SYNASTRY SCORING ──
# Weighted compatibility score between two charts
ASPECT_ORBS = {'conjunction':8,'opposition':8,'trine':7,'square':6,'sextile':5}
ASPECT_ANGLES = {'conjunction':0,'opposition':180,'trine':120,'square':90,'sextile':60}
ASPECT_WEIGHTS = {'conjunction':3,'trine':2,'sextile':1,'opposition':-1,'square':-1.5}

# Which planet pairs matter most for love compatibility
LOVE_PAIRS = [
    ('sun','moon',3.0),('sun','venus',2.5),('moon','venus',2.0),
    ('venus','mars',3.0),('sun','asc',2.0),('moon','asc',1.5),
    ('venus','asc',1.5),('sun','sun',1.0),('moon','moon',1.0),
    ('northNode','sun',1.5),('northNode','moon',1.5),('northNode','venus',2.0),
    ('asc','asc',1.0),('sun','mars',1.5),('moon','mars',1.0),
]

def get_aspect(lon1, lon2):
    diff = abs(lon1 - lon2) % 360
    if diff > 180: diff = 360 - diff
    for name, angle in ASPECT_ANGLES.items():
        orb = ASPECT_ORBS[name]
        if abs(diff - angle) <= orb:
            return name, abs(diff - angle)
    return None, None

def calc_synastry(chart1_planets, chart2_planets):
    """
    Calculate synastry score between two charts.
    Returns score 0-100 and list of significant aspects.
    """
    p1 = {p['key']: p['lon'] for p in chart1_planets}
    p2 = {p['key']: p['lon'] for p in chart2_planets}

    total_score = 0
    max_possible = 0
    aspects_found = []

    for key1, key2, weight in LOVE_PAIRS:
        if key1 not in p1 or key2 not in p2: continue
        max_possible += weight * ASPECT_WEIGHTS['conjunction']  # best case

        aspect, orb = get_aspect(p1[key1], p2[key2])
        if aspect:
            aspect_weight = ASPECT_WEIGHTS[aspect]
            pair_score = weight * aspect_weight
            total_score += pair_score
            aspects_found.append({
                'planet1': key1, 'planet2': key2,
                'aspect': aspect, 'orb': round(orb, 1),
                'score': round(pair_score, 2),
            })
        
        # Also check reverse (chart2 planet1 to chart1 planet2)
        if key2 in p1 and key1 in p2:
            aspect2, orb2 = get_aspect(p1[key2], p2[key1])
            if aspect2 and aspect2 != aspect:
                pair_score2 = weight * ASPECT_WEIGHTS[aspect2]
                total_score += pair_score2 * 0.5  # slightly less weight for reverse
                aspects_found.append({
                    'planet1': key2, 'planet2': key1,
                    'aspect': aspect2, 'orb': round(orb2,1),
                    'score': round(pair_score2*0.5, 2),
                })

    # Normalize to 0-100
    if max_possible > 0:
        normalized = (total_score / (max_possible * 1.2) + 0.5) * 100
    else:
        normalized = 50

    score = max(0, min(100, round(normalized)))
    
    # Sort aspects by importance
    aspects_found.sort(key=lambda x: abs(x['score']), reverse=True)
    
    return score, aspects_found[:10]  # top 10 aspects


# ══════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════


def send_welcome_email(to_email, name, sun_sign, moon_sign, asc_sign, user_id):
    """Send welcome email via Resend."""
    resend_key = os.environ.get('RESEND_API_KEY', '')
    if not resend_key:
        print("No RESEND_API_KEY set — skipping welcome email")
        return False

    matches_url = f"https://destined.cuartoastral.com/destined-matches.html?userId={user_id}"
    
    asc_line = f"↑ {asc_sign} Rising" if asc_sign else ""
    
    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#06060f;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#06060f;padding:40px 20px;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
      
      <!-- Header -->
      <tr><td style="text-align:center;padding:40px 40px 32px;border-bottom:1px solid rgba(201,168,76,.2);">
        <div style="font-family:Georgia,serif;font-size:11px;letter-spacing:6px;color:#c9a84c;text-transform:uppercase;margin-bottom:12px;">DESTINED</div>
        <div style="font-size:11px;letter-spacing:3px;color:rgba(168,168,192,.5);text-transform:uppercase;">Written in the Stars</div>
      </td></tr>

      <!-- Main -->
      <tr><td style="background:#0d0b1e;padding:48px 40px;">
        <p style="font-size:13px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:0 0 16px;">Welcome, {name}</p>
        <h1 style="font-size:32px;font-weight:300;color:#f0eefc;line-height:1.3;margin:0 0 24px;">
          Your chart is<br>
          <em style="color:#e8c96d;font-style:italic;">now in the stars.</em>
        </h1>
        <p style="font-size:15px;color:#a8a8c0;line-height:1.9;margin:0 0 32px;">
          You've joined Destined as a founding member. The universe has recorded your natal blueprint — and we're already searching for the souls whose charts align with yours.
        </p>

        <!-- Placements -->
        <div style="border:1px solid rgba(201,168,76,.2);padding:28px;margin-bottom:32px;background:rgba(201,168,76,.03);">
          <div style="font-size:10px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin-bottom:20px;">Your Key Placements</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05);">
                <span style="font-size:13px;color:#a8a8c0;">☉ Sun</span>
                <span style="font-size:16px;font-style:italic;color:#e8c96d;float:right;">{sun_sign}</span>
              </td>
            </tr>
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05);">
                <span style="font-size:13px;color:#a8a8c0;">☽ Moon</span>
                <span style="font-size:16px;font-style:italic;color:#e8c96d;float:right;">{moon_sign}</span>
              </td>
            </tr>
            {"<tr><td style='padding:10px 0;'><span style='font-size:13px;color:#a8a8c0;'>↑ Rising</span><span style='font-size:16px;font-style:italic;color:#e8c96d;float:right;'>" + asc_sign + "</span></td></tr>" if asc_sign else ""}
          </table>
        </div>

        <!-- Philosophy -->
        <blockquote style="border-left:2px solid rgba(201,168,76,.3);margin:0 0 32px;padding:16px 20px;background:rgba(201,168,76,.03);">
          <p style="font-size:16px;font-style:italic;color:#f0eefc;line-height:1.7;margin:0;">
            "Stop wasting years on the wrong chapter. Your person is already out there — written in the same sky."
          </p>
        </blockquote>

        <!-- CTA -->
        <div style="text-align:center;margin-bottom:32px;">
          <a href="{matches_url}" style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8721e);color:#06060f;padding:16px 40px;font-family:Georgia,serif;font-size:12px;letter-spacing:3px;text-decoration:none;text-transform:uppercase;">
            View My Matches →
          </a>
        </div>

        <p style="font-size:13px;color:rgba(168,168,192,.5);line-height:1.8;margin:0;text-align:center;">
          As new founding members join, you'll be matched by synastry score.<br>
          The universe is patient. So are we.
        </p>
      </td></tr>

      <!-- Footer -->
      <tr><td style="padding:24px 40px;text-align:center;border-top:1px solid rgba(255,255,255,.05);">
        <p style="font-size:11px;color:rgba(168,168,192,.3);letter-spacing:2px;text-transform:uppercase;margin:0;">
          DESTINED · Written in the Stars
        </p>
        <p style="font-size:11px;color:rgba(168,168,192,.2);margin:8px 0 0;">
          You're receiving this because you joined Destined. Your data is never shared or sold.
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

    email_data = {
        "from":    "Destined <info@cuartoastral.com>",
        "to":      [to_email],
        "subject": f"Welcome to Destined, {name} ✨ Your chart is in the stars",
        "html":    html_body,
    }

    try:
        import http.client, ssl
        payload = json.dumps(email_data).encode('utf-8')
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "User-Agent":    "Destined-App/1.0 Python/3.11",
        }
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.resend.com", context=ctx, timeout=15)
        conn.request("POST", "/emails", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        result = json.loads(body)
        if resp.status == 200 or resp.status == 201:
            print(f"Email sent to {to_email}: {result}")
            return True, None
        else:
            print(f"Email API error {resp.status}: {body}")
            return False, f"HTTP {resp.status}: {body}"
    except Exception as e:
        print(f"Email error: {e}")
        return False, str(e)

@app.route('/health', methods=['GET'])
def health():
    db_status     = 'connected'    if SUPABASE_URL                          else 'not configured'
    resend_status = 'configured'   if os.environ.get('RESEND_API_KEY','')   else 'missing — add RESEND_API_KEY to Render'
    return jsonify({
        'status':   'ok',
        'engine':   'Swiss Ephemeris',
        'version':  swe.version,
        'timezone': 'built-in geo database (no extra deps)',
        'database': db_status,
        'resend':   resend_status,
    })



@app.route('/email-debug', methods=['GET'])
def email_debug():
    """Debug email configuration without sending anything."""
    import urllib.request, json
    resend_key = os.environ.get('RESEND_API_KEY', '')
    
    if not resend_key:
        return jsonify({'error': 'RESEND_API_KEY is not set in environment variables'})
    
    # Test the Resend API key by listing domains
    try:
        import http.client, ssl
        headers = {
            'Authorization': f'Bearer {resend_key}',
            'Accept': 'application/json',
            'User-Agent': 'Destined-App/1.0 Python/3.11',
        }
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.resend.com", context=ctx, timeout=15)
        conn.request("GET", "/domains", headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        if resp.status == 200:
            domains = json.loads(body)
            return jsonify({
                'key_works': True,
                'key_prefix': resend_key[:8] + '...',
                'domains': domains,
            })
        else:
            return jsonify({
                'key_works': False,
                'http_error': resp.status,
                'error_body': body,
                'key_prefix': resend_key[:8] + '...',
            })
    except Exception as e:
        return jsonify({'error': str(e), 'key_prefix': resend_key[:8] + '...'})

@app.route('/test-email', methods=['POST'])
def test_email():
    """Send a test welcome email. POST {"email": "you@example.com"}"""
    data = request.get_json() or {}
    to   = data.get('email','')
    if not to: return jsonify({'error':'Provide email'}), 400

    resend_key = os.environ.get('RESEND_API_KEY','')
    if not resend_key:
        return jsonify({'error':'RESEND_API_KEY not set on server — add it in Render environment variables'}), 500

    result = send_welcome_email(
        to_email  = to,
        name      = 'Ingrid',
        sun_sign  = 'Pisces',
        moon_sign = 'Virgo',
        asc_sign  = 'Sagittarius',
        user_id   = 'test-preview',
    )
    success = result[0] if isinstance(result, tuple) else result
    error   = result[1] if isinstance(result, tuple) else 'Unknown error'
    if success:
        return jsonify({'success': True, 'message': f'Test email sent to {to} — check inbox!'})
    else:
        return jsonify({
            'success': False,
            'error': error,
            'from_address': 'info@cuartoastral.com',
            'resend_key_loaded': bool(os.environ.get('RESEND_API_KEY',''))
        })


@app.route('/chart', methods=['POST'])
def calculate_chart():
    """Calculate natal chart (does not save to DB)."""
    try:
        data = request.get_json()
        if not data: return jsonify({'error':'No data'}), 400

        year=int(data['year']); month=int(data['month']); day=int(data['day'])
        hour=int(data.get('hour',12)); minute=int(data.get('minute',0))
        lat=float(data['lat']); lon=float(data['lon'])
        name=str(data.get('name','Chart'))
        has_time=bool(data.get('has_time',True))

        if 'utc_offset' in data and data['utc_offset'] not in (None,''):
            utc_offset=float(data['utc_offset']); tz_name='Manual'; is_dst=False
        else:
            utc_offset,tz_name,is_dst = resolve_utc_offset(year,month,day,hour,minute,lat,lon)

        planets_result,houses_data,asc_data,mc_data,el_counts,jd_ut = calc_chart(
            year,month,day,hour,minute,lat,lon,has_time,utc_offset)

        dominant_element = max(el_counts, key=el_counts.get)
        def ps(key): p=next((x for x in planets_result if x['key']==key),None); return p['sign'] if p else ''
        nn_sign=ps('northNode'); sn_sign=ps('southNode')
        nn_d,sn_d=NODE_MEANINGS.get(nn_sign,('Your destiny.','Your past.'))

        soul_profile = {
            'dominantElement':dominant_element,'elementCounts':el_counts,
            'summary':SOUL_SUMMARIES.get(dominant_element,''),
            'sunSign':ps('sun'),'moonSign':ps('moon'),
            'ascSign':asc_data['sign'] if asc_data else None,
            'venusSign':ps('venus'),'marsSign':ps('mars'),
            'northNodeSign':nn_sign,'southNodeSign':sn_sign,
            'northNodeDestiny':nn_d,'southNodePast':sn_d,
        }

        houses_of_love = None
        if has_time and houses_data:
            def hi(idx,meaning):
                h=houses_data[idx]
                return {'sign':h['sign'],'glyph':h['signGlyph'],'degree':h['degree'],'meaning':meaning}
            houses_of_love = {
                'h5':hi(4,'Romance, flirtation, and the early magic of love.'),
                'h7':hi(6,'Committed partnership and what you seek in a long-term union.'),
                'h11':hi(10,'Friendship, shared vision, and communities where love finds you.'),
            }

        return jsonify({
            'success':True,'name':name,
            'birthData':{'year':year,'month':month,'day':day,'hour':hour,'minute':minute,
                'lat':lat,'lon':lon,'utcOffset':round(utc_offset,2),
                'timezoneName':tz_name,'isDST':is_dst,'hasTime':has_time,'julianDay':round(jd_ut,6)},
            'planets':planets_result,'houses':houses_data,
            'asc':asc_data,'mc':mc_data,
            'soulProfile':soul_profile,'housesOfLove':houses_of_love,
        })

    except KeyError as e: return jsonify({'error':f'Missing: {e}'}), 400
    except Exception as e: return jsonify({'error':str(e),'success':False}), 500


@app.route('/register', methods=['POST'])
def register_user():
    """
    Save a new user + their natal chart to Supabase.
    Called after chart is calculated and user agrees to join.
    """
    try:
        data = request.get_json()

        # Required fields
        required = ['email','name','year','month','day','lat','lon',
                    'gender','seeking','myAgeRange','seekAgeRange']
        for field in required:
            if field not in data:
                return jsonify({'error':f'Missing: {field}'}), 400

        # Age validation (must be 18+)
        from datetime import date
        birth = date(int(data['year']), int(data['month']), int(data['day']))
        today = date.today()
        age = (today - birth).days // 365
        if age < 18:
            return jsonify({'error':'Must be 18 or older'}), 400

        # Check if email already exists
        existing, err = supabase_request('GET', 'users',
            params={'email': f'eq.{data["email"]}', 'select': 'id'})
        if existing and len(existing) > 0:
            return jsonify({'error':'Email already registered','exists':True}), 409

        # Calculate the chart
        year=int(data['year']); month=int(data['month']); day=int(data['day'])
        hour=int(data.get('hour',12)); minute=int(data.get('minute',0))
        lat=float(data['lat']); lon=float(data['lon'])
        has_time=bool(data.get('has_time',True))

        if 'utc_offset' in data and data['utc_offset'] not in (None,''):
            utc_offset=float(data['utc_offset']); tz_name='Manual'
        else:
            utc_offset,tz_name,_ = resolve_utc_offset(year,month,day,hour,minute,lat,lon)

        planets_result,houses_data,asc_data,mc_data,el_counts,jd_ut = calc_chart(
            year,month,day,hour,minute,lat,lon,has_time,utc_offset)

        # Extract key planet longitudes for matching
        planet_lons = {p['key']:p['lon'] for p in planets_result}

        # Build user record
        user_record = {
            'email':       data['email'].lower().strip(),
            'name':        data['name'].strip(),
            'gender':      data['gender'],
            'seeking':     data['seeking'],
            'my_age_range':   data['myAgeRange'],
            'seek_age_range': data['seekAgeRange'],
            'birth_year':  year, 'birth_month': month, 'birth_day': day,
            'birth_hour':  hour, 'birth_minute': minute,
            'birth_lat':   lat,  'birth_lon':    lon,
            'birth_city':  data.get('city',''),
            'has_time':    has_time,
            'utc_offset':  utc_offset,
            'timezone':    tz_name,
            'julian_day':  round(jd_ut,6),
            # Planets
            'sun_lon':         planet_lons.get('sun'),
            'moon_lon':        planet_lons.get('moon'),
            'mercury_lon':     planet_lons.get('mercury'),
            'venus_lon':       planet_lons.get('venus'),
            'mars_lon':        planet_lons.get('mars'),
            'jupiter_lon':     planet_lons.get('jupiter'),
            'saturn_lon':      planet_lons.get('saturn'),
            'uranus_lon':      planet_lons.get('uranus'),
            'neptune_lon':     planet_lons.get('neptune'),
            'pluto_lon':       planet_lons.get('pluto'),
            'north_node_lon':  planet_lons.get('northNode'),
            'asc_lon':         asc_data['lon'] if asc_data else None,
            'mc_lon':          mc_data['lon']  if mc_data  else None,
            # Signs
            'sun_sign':    next((p['sign'] for p in planets_result if p['key']=='sun'),None),
            'moon_sign':   next((p['sign'] for p in planets_result if p['key']=='moon'),None),
            'asc_sign':    asc_data['sign'] if asc_data else None,
            'venus_sign':  next((p['sign'] for p in planets_result if p['key']=='venus'),None),
            'mars_sign':   next((p['sign'] for p in planets_result if p['key']=='mars'),None),
            'dominant_element': max(el_counts, key=el_counts.get),
            # Full chart JSON for display
            'chart_json':  json.dumps({
                'planets':planets_result,'houses':houses_data,
                'asc':asc_data,'mc':mc_data
            }),
        }

        result, err = supabase_request('POST', 'users', user_record)
        if err:
            return jsonify({'error':f'Database error: {err}'}), 500

        user_id = result[0]['id'] if result else None

        # Send welcome email (non-blocking — don't fail registration if email fails)
        try:
            email_result = send_welcome_email(
                to_email  = data['email'].lower().strip(),
                name      = data['name'].strip(),
                sun_sign  = next((p['sign'] for p in planets_result if p['key']=='sun'), ''),
                moon_sign = next((p['sign'] for p in planets_result if p['key']=='moon'), ''),
                asc_sign  = asc_data['sign'] if asc_data else None,
                user_id   = user_id,
            )
            if isinstance(email_result, tuple) and not email_result[0]:
                print(f"Welcome email failed (non-fatal): {email_result[1]}")
        except Exception as email_err:
            print(f"Welcome email failed (non-fatal): {email_err}")

        return jsonify({'success':True,'userId':user_id,'message':'Welcome to Destined!'})

    except Exception as e:
        return jsonify({'error':str(e),'success':False}), 500


@app.route('/matches/<user_id>', methods=['GET'])
def get_matches(user_id):
    """
    Get top compatibility matches for a user.
    Calculates synastry score against all compatible users in DB.
    """
    try:
        # Get the requesting user
        user_data, err = supabase_request('GET', 'users',
            params={'id':'eq.'+user_id, 'select':'*'})
        if err or not user_data:
            return jsonify({'error':'User not found'}), 404
        user = user_data[0]

        # Determine who to match against based on seeking preference
        seeking = user.get('seeking','Everyone')
        if seeking == 'Women':
            gender_filter = 'eq.Woman'
        elif seeking == 'Men':
            gender_filter = 'eq.Man'
        else:
            gender_filter = None  # Everyone

        # Fetch potential matches (exclude self)
        params = {'id': f'neq.{user_id}', 'select': '*', 'limit': '200'}
        if gender_filter:
            params['gender'] = gender_filter

        candidates, err = supabase_request('GET', 'users', params=params)
        if err:
            return jsonify({'error':f'Database error: {err}'}), 500
        if not candidates:
            return jsonify({'success':True,'matches':[],'total':0})

        # Build user's planet list from stored longitudes
        user_planets = build_planets_from_record(user)

        # Score each candidate
        scored = []
        for candidate in candidates:
            cand_planets = build_planets_from_record(candidate)
            score, aspects = calc_synastry(user_planets, cand_planets)
            
            # Filter by age preference (basic check)
            scored.append({
                'userId':     candidate['id'],
                'name':       candidate['name'],
                'sunSign':    candidate.get('sun_sign',''),
                'moonSign':   candidate.get('moon_sign',''),
                'ascSign':    candidate.get('asc_sign',''),
                'venusSign':  candidate.get('venus_sign',''),
                'marsSign':   candidate.get('mars_sign',''),
                'dominantElement': candidate.get('dominant_element',''),
                'birthYear':  candidate.get('birth_year'),
                'gender':     candidate.get('gender',''),
                'city':       candidate.get('birth_city',''),
                'score':      score,
                'aspects':    aspects[:5],  # top 5 aspects
            })

        # Sort by score descending
        scored.sort(key=lambda x: x['score'], reverse=True)

        return jsonify({
            'success': True,
            'matches': scored[:20],  # top 20 matches
            'total': len(scored),
        })

    except Exception as e:
        return jsonify({'error':str(e)}), 500


def build_planets_from_record(record):
    """Reconstruct planet list from stored DB longitudes."""
    keys = ['sun','moon','mercury','venus','mars','jupiter','saturn',
            'uranus','neptune','pluto','northNode','asc','mc']
    db_keys = ['sun','moon','mercury','venus','mars','jupiter','saturn',
               'uranus','neptune','pluto','north_node','asc','mc']
    planets = []
    for key, db_key in zip(keys, db_keys):
        lon = record.get(f'{db_key}_lon')
        if lon is not None:
            planets.append({'key':key,'lon':float(lon)})
    return planets




@app.route('/user-by-email', methods=['GET'])
def user_by_email():
    """Look up a user by email or id for login."""
    email = request.args.get('email','')
    uid   = request.args.get('id','')

    if email:
        users, err = supabase_request('GET','users',
            params={'email':f'eq.{email.lower().strip()}','select':'*','limit':'1'})
    elif uid:
        users, err = supabase_request('GET','users',
            params={'id':f'eq.{uid}','select':'*','limit':'1'})
    else:
        return jsonify({'error':'Provide email or id'}), 400

    if err:   return jsonify({'error':err}), 500
    if not users: return jsonify({'success':False,'error':'Not found'}), 404
    return jsonify({'success':True,'userId':users[0]['id'],'user':users[0]})


@app.route('/messages', methods=['GET'])
def get_messages():
    """Get conversation between two users."""
    user1 = request.args.get('user1','')
    user2 = request.args.get('user2','')
    if not user1 or not user2:
        return jsonify({'error':'Provide user1 and user2'}), 400

    # Get messages in both directions
    msgs1, _ = supabase_request('GET','messages', params={
        'sender_id':  f'eq.{user1}',
        'receiver_id':f'eq.{user2}',
        'select':'*','order':'created_at.asc','limit':'100'
    })
    msgs2, _ = supabase_request('GET','messages', params={
        'sender_id':  f'eq.{user2}',
        'receiver_id':f'eq.{user1}',
        'select':'*','order':'created_at.asc','limit':'100'
    })

    all_msgs = (msgs1 or []) + (msgs2 or [])
    all_msgs.sort(key=lambda m: m.get('created_at',''))
    return jsonify({'success':True,'messages':all_msgs})


@app.route('/messages', methods=['POST'])
def send_message():
    """Send a message between two users."""
    data = request.get_json()
    if not data: return jsonify({'error':'No data'}), 400

    required = ['sender_id','receiver_id','content']
    for f in required:
        if f not in data: return jsonify({'error':f'Missing {f}'}), 400

    content = str(data['content']).strip()
    if not content: return jsonify({'error':'Empty message'}), 400
    if len(content) > 2000: return jsonify({'error':'Message too long'}), 400

    msg = {
        'sender_id':   data['sender_id'],
        'receiver_id': data['receiver_id'],
        'content':     content,
    }
    result, err = supabase_request('POST','messages', msg)
    if err: return jsonify({'error':err}), 500
    return jsonify({'success':True,'message':result[0] if result else {}})

@app.route('/admin/users', methods=['GET'])
def admin_users():
    """Admin endpoint — returns all users. Protected by admin key."""
    admin_key = request.headers.get('X-Admin-Key','')
    expected  = os.environ.get('ADMIN_PASSWORD','destined2025')
    if admin_key != expected:
        return jsonify({'error':'Unauthorized'}), 401

    limit  = int(request.args.get('limit', 500))
    offset = int(request.args.get('offset', 0))

    users, err = supabase_request('GET', 'users', params={
        'select': 'id,created_at,name,email,gender,seeking,my_age_range,seek_age_range,'
                  'birth_year,birth_month,birth_day,birth_hour,birth_minute,'
                  'birth_city,has_time,sun_sign,moon_sign,asc_sign,venus_sign,'
                  'mars_sign,dominant_element,chart_json',
        'order':  'created_at.desc',
        'limit':  str(limit),
        'offset': str(offset),
    })
    if err:
        return jsonify({'error': err}), 500

    return jsonify({'success': True, 'users': users or [], 'total': len(users or [])})


# ══════════════════════════════════════
# PAID READING SYSTEM
# ══════════════════════════════════════

READING_PRICE_CENTS = 999  # $9.99

def generate_ai_reading(chart_data):
    """Generate personalized reading using Claude API."""
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not anthropic_key:
        return None, "Anthropic API key not configured"

    planets = {p['key']: p for p in chart_data.get('planets', [])}
    houses  = chart_data.get('houses', [])
    
    def p(key): return planets.get(key, {})
    def sign(key): return p(key).get('sign', '')
    def house(key): return p(key).get('house', '')
    def deg(key): return p(key).get('degree', 0)

    h5  = next((h for h in houses if h['house']==5), {}).get('sign','')
    h7  = next((h for h in houses if h['house']==7), {}).get('sign','')
    h11 = next((h for h in houses if h['house']==11), {}).get('sign','')

    prompt = f"""You are a professional Western astrologer writing a deeply personalized natal chart reading. 
Write in a warm, insightful, poetic but grounded tone — like a wise friend who knows astrology deeply.
Never be vague. Always reference the specific placements.

The person natal chart:
- Sun: {sign('sun')} (House {house('sun')}) at {deg('sun')}°
- Moon: {sign('moon')} (House {house('moon')}) at {deg('moon')}°
- Ascendant: {sign('asc')} at {deg('asc')}°
- Mercury: {sign('mercury')} (House {house('mercury')})
- Venus: {sign('venus')} (House {house('venus')}) at {deg('venus')}°
- Mars: {sign('mars')} (House {house('mars')}) at {deg('mars')}°
- Jupiter: {sign('jupiter')} (House {house('jupiter')})
- Saturn: {sign('saturn')} (House {house('saturn')})
- Uranus: {sign('uranus')} (House {house('uranus')})
- Neptune: {sign('neptune')} (House {house('neptune')})
- Pluto: {sign('pluto')} (House {house('pluto')})
- North Node: {sign('northNode')} (House {house('northNode')})
- South Node: {sign('southNode')}
- 5th House cusp: {h5}
- 7th House cusp: {h7}
- 11th House cusp: {h11}

Write a complete natal chart reading with these EXACT sections. Each section must be 2-3 rich paragraphs:

1. YOUR SOUL BLUEPRINT
Core identity synthesis of Sun, Moon and Rising. Who this person fundamentally is.

2. YOUR INNER WORLD
Emotional nature, Moon placement, what makes them feel safe and loved.

3. HOW YOU LOVE
Venus sign and house, Mars sign and house. How they love, what they need in a partner.

4. YOUR DESTINY IN LOVE
5th house romance, 7th house partnership, 11th house connection. What love story is written for them.

5. NORTH NODE — SOUL PURPOSE
What this soul came here to learn and become. The path forward.

6. YOUR DESTINED MATCH
Based on ALL placements, describe the soul they are most compatible with. Be specific about signs, elements and qualities.

End with one powerful closing paragraph that feels like a personal message to this person.

Write with depth, warmth and specificity. This is a paid reading — make it worth every penny."""

    try:
        import http.client, ssl
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode('utf-8')

        headers = {
            "x-api-key":         anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        }
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.anthropic.com", context=ctx, timeout=60)
        conn.request("POST", "/v1/messages", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()

        if resp.status == 200:
            result  = json.loads(body)
            reading = result['content'][0]['text']
            return reading, None
        else:
            return None, f"API error {resp.status}: {body}"
    except Exception as e:
        return None, str(e)


def send_reading_email(to_email, name, reading_text, user_id):
    """Send the full reading as a beautiful email."""
    resend_key = os.environ.get('RESEND_API_KEY', '')
    if not resend_key:
        return False, "Resend not configured"

    sections_html = ""
    current_section = ""
    for line in reading_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line and (line[0].isdigit() or line.isupper()) and len(line) < 80:
            if current_section:
                sections_html += f'<div style="margin-bottom:32px;">{current_section}</div>'
            sections_html += f"""
            <div style="font-size:10px;letter-spacing:3px;color:#c9a84c;
                 text-transform:uppercase;margin:32px 0 12px;
                 border-top:1px solid rgba(201,168,76,.2);padding-top:24px;">
                {line}
            </div>"""
            current_section = ""
        else:
            current_section += f'<p style="font-size:15px;color:#c8c8e0;line-height:1.9;margin:0 0 16px;">{line}</p>'
    if current_section:
        sections_html += f'<div style="margin-bottom:32px;">{current_section}</div>'

    matches_url = f"https://destined.cuartoastral.com/destined-matches.html?userId={user_id}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#06060f;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#06060f;padding:40px 20px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
      <tr><td style="text-align:center;padding:40px 40px 32px;border-bottom:1px solid rgba(201,168,76,.2);">
        <div style="font-size:11px;letter-spacing:6px;color:#c9a84c;text-transform:uppercase;margin-bottom:8px;">DESTINED</div>
        <div style="font-size:11px;letter-spacing:3px;color:rgba(168,168,192,.5);text-transform:uppercase;">Your Complete Natal Reading</div>
      </td></tr>
      <tr><td style="background:#0d0b1e;padding:40px 40px 8px;">
        <p style="font-size:12px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:0 0 12px;">Personal Reading for {name}</p>
        <h1 style="font-size:34px;font-weight:300;color:#f0eefc;line-height:1.3;margin:0 0 24px;">
          Your soul,<br><em style="color:#e8c96d;font-style:italic;">written in the stars.</em>
        </h1>
        <p style="font-size:14px;color:#a8a8c0;line-height:1.9;margin:0 0 32px;padding-bottom:32px;border-bottom:1px solid rgba(255,255,255,.06);">
          This is your complete natal chart reading — prepared exclusively for you based on the precise positions of the planets at the moment of your birth. Read slowly. Let it land.
        </p>
      </td></tr>
      <tr><td style="background:#0d0b1e;padding:8px 40px 40px;">{sections_html}</td></tr>
      <tr><td style="background:#0d0b1e;padding:0 40px 48px;text-align:center;">
        <div style="border:1px solid rgba(201,168,76,.2);padding:32px;background:rgba(201,168,76,.03);">
          <p style="font-size:14px;color:#a8a8c0;line-height:1.9;margin:0 0 24px;">
            Your chart has revealed your soul blueprint.<br>Now meet the soul already written for you.
          </p>
          <a href="{matches_url}" style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8721e);color:#06060f;padding:16px 40px;font-size:12px;letter-spacing:3px;text-decoration:none;text-transform:uppercase;">
            View My Destined Matches →
          </a>
        </div>
      </td></tr>
      <tr><td style="padding:24px 40px;text-align:center;border-top:1px solid rgba(255,255,255,.05);">
        <p style="font-size:11px;color:rgba(168,168,192,.3);letter-spacing:2px;text-transform:uppercase;margin:0;">
          DESTINED · Written in the Stars · cuartoastral.com
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""

    try:
        import http.client, ssl
        email_data = {
            "from":    "Destined <info@cuartoastral.com>",
            "to":      [to_email],
            "subject": f"Your Complete Natal Reading, {name} ✨",
            "html":    html_body,
        }
        payload = json.dumps(email_data).encode('utf-8')
        headers = {
            "Authorization": f"Bearer {resend_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "User-Agent":    "Destined-App/1.0",
        }
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.resend.com", context=ctx, timeout=15)
        conn.request("POST", "/emails", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        if resp.status in (200, 201):
            return True, None
        else:
            return False, f"HTTP {resp.status}: {body}"
    except Exception as e:
        return False, str(e)


@app.route('/create-payment', methods=['POST'])
def create_payment():
    """Create a Stripe payment intent for the full reading."""
    stripe_secret = os.environ.get('STRIPE_SECRET_KEY', '')
    if not stripe_secret:
        return jsonify({'error': 'Stripe not configured'}), 500

    data    = request.get_json() or {}
    user_id = data.get('userId', '')
    email   = data.get('email', '')
    name    = data.get('name', 'Explorer')

    if not user_id or not email:
        return jsonify({'error': 'userId and email required'}), 400

    try:
        import http.client, ssl, base64
        payload = urllib.parse.urlencode({
            'amount':   str(READING_PRICE_CENTS),
            'currency': 'usd',
            'metadata[user_id]': user_id,
            'metadata[email]':   email,
            'metadata[name]':    name,
            'description': 'Destined — Complete Natal Chart Reading',
        }).encode()

        auth    = base64.b64encode(f"{stripe_secret}:".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type':  'application/x-www-form-urlencoded',
        }
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.stripe.com", context=ctx, timeout=15)
        conn.request("POST", "/v1/payment_intents", body=payload, headers=headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()

        if resp.status == 200:
            intent = json.loads(body)
            return jsonify({
                'success':      True,
                'clientSecret': intent['client_secret'],
                'amount':       READING_PRICE_CENTS,
            })
        else:
            return jsonify({'error': f'Stripe error: {body}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/deliver-reading', methods=['POST'])
def deliver_reading():
    """Called after successful Stripe payment. Generates AI reading and emails it."""
    stripe_secret     = os.environ.get('STRIPE_SECRET_KEY', '')
    data              = request.get_json() or {}
    payment_intent_id = data.get('paymentIntentId', '')
    user_id           = data.get('userId', '')
    email             = data.get('email', '')
    name              = data.get('name', 'Explorer')

    if not all([payment_intent_id, user_id, email]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Verify payment with Stripe
    if stripe_secret:
        try:
            import http.client, ssl, base64
            auth = base64.b64encode(f"{stripe_secret}:".encode()).decode()
            ctx  = ssl.create_default_context()
            conn = http.client.HTTPSConnection("api.stripe.com", context=ctx, timeout=15)
            conn.request("GET", f"/v1/payment_intents/{payment_intent_id}",
                        headers={"Authorization": f"Basic {auth}"})
            resp = conn.getresponse()
            body = json.loads(resp.read().decode())
            conn.close()
            if body.get('status') != 'succeeded':
                return jsonify({'error': 'Payment not confirmed'}), 402
        except Exception as e:
            return jsonify({'error': f'Payment verification failed: {e}'}), 500

    # Get user chart from database
    users, err = supabase_request('GET', 'users',
        params={'id': f'eq.{user_id}', 'select': 'chart_json,name,email', 'limit': '1'})
    if err or not users:
        return jsonify({'error': 'User not found'}), 404

    user       = users[0]
    chart_json = user.get('chart_json', '{}')
    chart_data = json.loads(chart_json) if isinstance(chart_json, str) else chart_json

    # Generate AI reading
    reading, err = generate_ai_reading(chart_data)
    if err:
        return jsonify({'error': f'Reading generation failed: {err}'}), 500

    # Send reading email
    sent, err = send_reading_email(email, name, reading, user_id)
    if not sent:
        return jsonify({'error': f'Email delivery failed: {err}'}), 500

    # Mark reading as purchased
    supabase_request('PATCH', 'users',
        data={'reading_purchased': True},
        params={'id': f'eq.{user_id}'})

    return jsonify({'success': True, 'message': f'Your complete reading has been sent to {email}!'})



# ══════════════════════════════════════════
# PAID READING — STRIPE + ANTHROPIC
# ══════════════════════════════════════════

STRIPE_SECRET_KEY    = os.environ.get('STRIPE_SECRET_KEY', '')
ANTHROPIC_API_KEY    = os.environ.get('ANTHROPIC_API_KEY', '')
READING_PRICE_CENTS  = 999  # $9.99


def generate_ai_reading(user):
    """Generate a full personalized natal chart reading using Claude."""
    if not ANTHROPIC_API_KEY:
        return None, "Anthropic API key not configured"

    # Build the prompt from user's chart data
    chart = json.loads(user.get('chart_json', '{}'))
    planets = {p['key']: p for p in chart.get('planets', [])}
    houses  = {h['house']: h for h in chart.get('houses', [])}

    def ps(key):
        p = planets.get(key, {})
        house = f" in House {p.get('house','')}" if p.get('house') else ''
        retro = ' (retrograde)' if p.get('retrograde') else ''
        return f"{p.get('sign','Unknown')}{house}{retro}" if p else 'Unknown'

    h5  = houses.get(5,  {}).get('sign', '?')
    h7  = houses.get(7,  {}).get('sign', '?')
    h11 = houses.get(11, {}).get('sign', '?')

    prompt = f"""You are a professional Western astrologer writing a deep, personalized natal chart reading. 
Write in a warm, insightful, poetic but grounded tone. Be specific to the placements — not generic.
Never say "as an astrologer" or "in astrology". Just speak directly and personally.

This is for {user.get('name', 'this person')}, born on {user.get('birth_month')}/{user.get('birth_day')}/{user.get('birth_year')} in {user.get('birth_city', 'their birth city')}.

Their natal chart:
- Sun: {ps('sun')}
- Moon: {ps('moon')}  
- Ascendant (Rising): {ps('asc')}
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

Write a complete natal chart reading with these 5 sections. Each section should be 2-3 rich paragraphs:

1. YOUR SOUL BLUEPRINT — Sun, Moon and Rising: who you are at your core, your emotional world, how others first experience you

2. YOUR MIND & VOICE — Mercury: how you think, communicate, process information and make decisions

3. LOVE, BEAUTY & DESIRE — Venus, Mars, 5th and 7th houses: how you love, what you need in a partner, your romantic style, what attracts you and what you attract

4. YOUR DESTINY & PURPOSE — North Node, Jupiter, Saturn: your soul's mission this lifetime, where you're growing, your gifts and your challenges

5. YOUR DESTINED PARTNER — Based on all placements, describe the astrological profile of the person most destined for them: their likely Sun, Moon, Rising signs, their qualities, how they'll meet, what the relationship will feel like

End with a short paragraph titled YOUR COSMIC MESSAGE — one powerful, personal message from the stars to this soul.

Write beautifully. Be specific. Make them feel truly seen."""

    try:
        import http.client, ssl
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
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
            result  = json.loads(body)
            reading = result['content'][0]['text']
            return reading, None
        else:
            return None, f"Anthropic error {resp.status}: {body}"
    except Exception as e:
        return None, str(e)


def send_reading_email(to_email, name, reading_text, user_id):
    """Send the full reading as a beautiful HTML email."""
    resend_key = os.environ.get('RESEND_API_KEY', '')
    if not resend_key:
        return False, "No Resend key"

    # Convert reading text to HTML paragraphs
    sections = reading_text.split('\n\n')
    html_sections = ''
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Check if it's a section header (all caps or starts with number)
        if section.isupper() or (len(section) < 60 and section.replace(' ','').replace('&','').replace('—','').replace('.','').isupper()):
            html_sections += f'<h2 style="font-family:Georgia,serif;font-size:14px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:32px 0 12px;">{section}</h2>'
        elif section.startswith(('1.','2.','3.','4.','5.','YOUR ')):
            html_sections += f'<h2 style="font-family:Georgia,serif;font-size:14px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:32px 0 12px;">{section}</h2>'
        else:
            html_sections += f'<p style="font-size:15px;color:#c8c8e0;line-height:1.9;margin:0 0 16px;">{section}</p>'

    matches_url = f"https://destined.cuartoastral.com/destined-matches.html?userId={user_id}"

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#06060f;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#06060f;padding:40px 20px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

      <tr><td style="text-align:center;padding:40px 40px 32px;border-bottom:1px solid rgba(201,168,76,.2);">
        <div style="font-size:11px;letter-spacing:6px;color:#c9a84c;text-transform:uppercase;margin-bottom:8px;">DESTINED</div>
        <div style="font-size:11px;letter-spacing:3px;color:rgba(168,168,192,.5);text-transform:uppercase;">Your Complete Natal Reading</div>
      </td></tr>

      <tr><td style="background:#0d0b1e;padding:48px 40px;">
        <p style="font-size:13px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:0 0 12px;">A reading for {name}</p>
        <h1 style="font-size:28px;font-weight:300;color:#f0eefc;line-height:1.3;margin:0 0 32px;">
          Your stars have<br><em style="color:#e8c96d;font-style:italic;">spoken.</em>
        </h1>
        <div style="border-left:2px solid rgba(201,168,76,.3);padding:16px 20px;background:rgba(201,168,76,.03);margin-bottom:32px;">
          <p style="font-size:13px;font-style:italic;color:#a8a8c0;margin:0;line-height:1.7;">
            "Stop wasting years on the wrong chapter. Your person is already out there — written in the same sky."
          </p>
        </div>
        {html_sections}
        <div style="text-align:center;margin-top:40px;padding-top:32px;border-top:1px solid rgba(255,255,255,.06);">
          <a href="{matches_url}" style="display:inline-block;background:linear-gradient(135deg,#c9a84c,#a8721e);color:#06060f;padding:16px 40px;font-size:12px;letter-spacing:3px;text-decoration:none;text-transform:uppercase;">
            View Your Matches →
          </a>
        </div>
      </td></tr>

      <tr><td style="padding:24px 40px;text-align:center;border-top:1px solid rgba(255,255,255,.05);">
        <p style="font-size:11px;color:rgba(168,168,192,.3);letter-spacing:2px;text-transform:uppercase;margin:0;">
          DESTINED · Written in the Stars · destined.cuartoastral.com
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

    email_data = {
        "from":    "Destined <info@cuartoastral.com>",
        "to":      [to_email],
        "subject": f"✨ {name}, your complete natal reading is here",
        "html":    html_body,
    }

    try:
        import http.client, ssl
        payload = json.dumps(email_data).encode('utf-8')
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
        result = json.loads(body)
        if resp.status in (200, 201):
            return True, None
        else:
            return False, f"HTTP {resp.status}: {body}"
    except Exception as e:
        return False, str(e)


def create_stripe_payment(amount_cents, description, success_url, cancel_url, metadata):
    """Create a Stripe Checkout session."""
    if not STRIPE_SECRET_KEY:
        return None, "Stripe not configured"

    try:
        import http.client, ssl, urllib.parse
        payload = urllib.parse.urlencode({
            'payment_method_types[]':        'card',
            'line_items[0][price_data][currency]':                    'usd',
            'line_items[0][price_data][unit_amount]':                 str(amount_cents),
            'line_items[0][price_data][product_data][name]':          description,
            'line_items[0][price_data][product_data][description]':   'Personalized AI natal chart reading delivered to your email',
            'line_items[0][quantity]':        '1',
            'mode':                           'payment',
            'success_url':                    success_url,
            'cancel_url':                     cancel_url,
            'metadata[user_id]':              metadata.get('user_id',''),
            'metadata[user_email]':           metadata.get('user_email',''),
            'metadata[user_name]':            metadata.get('user_name',''),
        }).encode('utf-8')

        import base64
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
            return None, f"Stripe error {resp.status}: {body}"
    except Exception as e:
        return None, str(e)


@app.route('/create-reading-payment', methods=['POST'])
def create_reading_payment():
    """Create a Stripe checkout session for a paid reading."""
    try:
        data     = request.get_json() or {}
        user_id  = data.get('userId', '')
        if not user_id:
            return jsonify({'error': 'userId required'}), 400

        # Get user from DB
        users, err = supabase_request('GET', 'users',
            params={'id': f'eq.{user_id}', 'select': 'id,name,email,sun_sign,moon_sign,asc_sign'})
        if err or not users:
            return jsonify({'error': 'User not found'}), 404
        user = users[0]

        base_url    = 'https://destined.cuartoastral.com'
        success_url = f"{base_url}/destined-chart.html?reading=success&userId={user_id}"
        cancel_url  = f"{base_url}/destined-chart.html?reading=cancelled&userId={user_id}"

        session, err = create_stripe_payment(
            amount_cents = READING_PRICE_CENTS,
            description  = f"Complete Natal Reading for {user['name']}",
            success_url  = success_url,
            cancel_url   = cancel_url,
            metadata     = {
                'user_id':    user_id,
                'user_email': user['email'],
                'user_name':  user['name'],
            }
        )
        if err:
            return jsonify({'error': err}), 500

        return jsonify({
            'success':     True,
            'checkoutUrl': session['url'],
            'sessionId':   session['id'],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/deliver-reading', methods=['POST'])
def deliver_reading():
    """
    Called after successful Stripe payment.
    Generates AI reading and emails it to the user.
    Can be called from success page or Stripe webhook.
    """
    try:
        data    = request.get_json() or {}
        user_id = data.get('userId', '')
        if not user_id:
            return jsonify({'error': 'userId required'}), 400

        # Check if reading already delivered (avoid double charging)
        users, err = supabase_request('GET', 'users',
            params={'id': f'eq.{user_id}', 'select': '*'})
        if err or not users:
            return jsonify({'error': 'User not found'}), 404
        user = users[0]

        if user.get('reading_delivered'):
            return jsonify({'success': True, 'message': 'Reading already delivered', 'already_sent': True})

        # Generate the AI reading
        reading, err = generate_ai_reading(user)
        if err:
            return jsonify({'error': f'Reading generation failed: {err}'}), 500

        # Send the email
        sent, err = send_reading_email(
            to_email = user['email'],
            name     = user['name'],
            reading_text = reading,
            user_id  = user_id,
        )
        if not sent:
            return jsonify({'error': f'Email delivery failed: {err}'}), 500

        # Mark reading as delivered in DB
        supabase_request('PATCH', 'users',
            data={'reading_delivered': True},
            params={'id': f'eq.{user_id}'}
        )

        return jsonify({
            'success': True,
            'message': f'Reading delivered to {user["email"]}',
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/create-reading-payment', methods=['POST'])
def create_reading_payment():
    try:
        data    = request.get_json() or {}
        user_id = data.get('userId','')
        if not user_id: return jsonify({'error':'userId required'}), 400
        users, err = supabase_request('GET','users',
            params={'id':f'eq.{user_id}','select':'*'})
        if err or not users: return jsonify({'error':'User not found'}), 404
        session, err = create_stripe_session(users[0], 'https://destined.cuartoastral.com')
        if err: return jsonify({'error': err}), 500
        return jsonify({'success':True,'checkoutUrl':session['url'],'sessionId':session['id']})
    except Exception as e:
        return jsonify({'error':str(e)}), 500


@app.route('/deliver-reading', methods=['POST'])
def deliver_reading():
    try:
        data    = request.get_json() or {}
        user_id = data.get('userId','')
        if not user_id: return jsonify({'error':'userId required'}), 400
        users, err = supabase_request('GET','users',
            params={'id':f'eq.{user_id}','select':'*'})
        if err or not users: return jsonify({'error':'User not found'}), 404
        user = users[0]
        if user.get('reading_delivered'):
            return jsonify({'success':True,'message':'Reading already delivered','already_sent':True})
        reading, err = generate_ai_reading(user)
        if err: return jsonify({'error':f'Reading failed: {err}'}), 500
        resend_key = os.environ.get('RESEND_API_KEY','')
        sent, detail = send_reading_email(user['email'], user['name'], reading, user_id, resend_key)
        if not sent: return jsonify({'error':f'Email failed: {detail}'}), 500
        supabase_request('PATCH','users',
            data={'reading_delivered':True},
            params={'id':f'eq.{user_id}'})
        return jsonify({'success':True,'message':f'Reading delivered to {user["email"]}'})
    except Exception as e:
        return jsonify({'error':str(e)}), 500


@app.route('/reading-status', methods=['GET'])
def reading_status():
    """Check if Stripe and Anthropic are configured."""
    return jsonify({
        'stripe':    'configured' if os.environ.get('STRIPE_SECRET_KEY') else 'missing',
        'anthropic': 'configured' if os.environ.get('ANTHROPIC_API_KEY') else 'missing',
    })

@app.route('/geocode', methods=['GET'])
def geocode():
    query = request.args.get('q','')
    if not query: return jsonify({'error':'No query'}), 400
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=6&addressdetails=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Destined-App/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return jsonify(json.loads(resp.read()))
    except Exception as e:
        return jsonify({'error':str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
