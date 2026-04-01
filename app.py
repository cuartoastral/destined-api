"""
Destined Natal Chart API
Swiss Ephemeris + built-in timezone database + Supabase user storage.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe
import math, os, urllib.request, urllib.parse, json, hashlib
# Payments module — imported conditionally to avoid startup crashes
try:
    from payments import generate_ai_reading, send_reading_email, create_stripe_session
    PAYMENTS_AVAILABLE = True
except Exception as _pay_err:
    PAYMENTS_AVAILABLE = False
    print(f"Warning: payments module not loaded: {_pay_err}")
    def generate_ai_reading(u): return None, "Payments module not available"
    def send_reading_email(*a, **k): return False, "Payments module not available"
    def create_stripe_session(*a, **k): return None, "Payments module not available" 

FOUNDING_MEMBER_CAP = 200  # Free forever for first 200 members

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
# Synastry pairs — (chart1_planet, chart2_planet, weight)
# We check BOTH directions for each pair so no connection is missed
LOVE_PAIRS = [
    # Tier 1 — Soul level (highest weight)
    ('sun',  'moon',   3.0),  # Sun-Moon: emotional recognition, "home" feeling
    ('moon', 'sun',    3.0),  # Reverse: his Moon to her Sun (your case!)
    ('venus','mars',   3.0),  # Venus-Mars: magnetic attraction
    ('mars', 'venus',  3.0),  # Reverse
    ('sun',  'venus',  2.5),  # Sun-Venus: warmth, admiration, genuine like
    ('venus','sun',    2.5),  # Reverse
    ('moon', 'moon',   2.5),  # Moon-Moon: deep emotional resonance
    ('sun',  'sun',    2.0),  # Sun-Sun: core identity alignment

    # Tier 2 — Destiny connections
    ('northNode','sun',   2.0),  # Node-Sun: karmic destiny
    ('sun','northNode',   2.0),  # Reverse
    ('northNode','moon',  2.0),  # Node-Moon: emotional karma
    ('moon','northNode',  2.0),  # Reverse
    ('northNode','venus', 2.5),  # Node-Venus: destined love
    ('venus','northNode', 2.5),  # Reverse

    # Tier 3 — Magnetic pull
    ('sun',  'asc',    2.0),  # Sun-ASC: instant recognition
    ('asc',  'sun',    2.0),  # Reverse
    ('moon', 'asc',    1.5),  # Moon-ASC: emotional comfort
    ('asc',  'moon',   1.5),  # Reverse
    ('venus','asc',    1.5),  # Venus-ASC: physical attraction
    ('asc',  'venus',  1.5),  # Reverse
    ('moon', 'venus',  2.0),  # Moon-Venus: tenderness
    ('venus','moon',   2.0),  # Reverse

    # Tier 4 — Passion and drive
    ('sun',  'mars',   1.5),  # Sun-Mars: vitality, drive
    ('mars', 'sun',    1.5),  # Reverse
    ('moon', 'mars',   1.0),  # Moon-Mars: emotional passion
    ('mars', 'moon',   1.0),  # Reverse
    ('asc',  'asc',    1.0),  # ASC-ASC: physical type match
]

# Aspect meanings for display
ASPECT_MEANINGS = {
    ('sun','moon'):    'emotional recognition — the "home" feeling',
    ('moon','sun'):    'emotional recognition — the "home" feeling',
    ('venus','mars'):  'magnetic attraction and physical chemistry',
    ('mars','venus'):  'magnetic attraction and physical chemistry',
    ('sun','venus'):   'warmth, admiration and genuine affection',
    ('venus','sun'):   'warmth, admiration and genuine affection',
    ('moon','moon'):   'deep emotional resonance and intuitive understanding',
    ('northNode','venus'): 'destined love — karmic romantic connection',
    ('venus','northNode'): 'destined love — karmic romantic connection',
    ('northNode','sun'):   'karmic soul recognition',
    ('sun','northNode'):   'karmic soul recognition',
    ('sun','asc'):     'instant recognition — you see each other clearly',
    ('asc','sun'):     'instant recognition — you see each other clearly',
    ('venus','asc'):   'physical attraction and magnetic pull',
    ('asc','venus'):   'physical attraction and magnetic pull',
    ('moon','venus'):  'tenderness and emotional affection',
    ('venus','moon'):  'tenderness and emotional affection',
}

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

    seen_pairs = set()  # avoid double counting same planetary pair
    for key1, key2, weight in LOVE_PAIRS:
        if key1 not in p1 or key2 not in p2: continue

        # Skip if we already scored this exact planetary pair
        pair_key = tuple(sorted([key1, key2]))
        if pair_key in seen_pairs: continue
        seen_pairs.add(pair_key)

        max_possible += weight * ASPECT_WEIGHTS['conjunction']

        aspect, orb = get_aspect(p1[key1], p2[key2])
        if aspect:
            aspect_weight = ASPECT_WEIGHTS[aspect]
            pair_score = weight * aspect_weight
            total_score += pair_score
            meaning = ASPECT_MEANINGS.get((key1,key2), '')
            aspects_found.append({
                'planet1': key1, 'planet2': key2,
                'aspect': aspect, 'orb': round(orb, 1),
                'score': round(pair_score, 2),
                'meaning': meaning,
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
    try:
        all_users, _ = supabase_request('GET', 'users', params={'select':'id'})
        member_count  = len(all_users) if all_users else 0
    except:
        member_count = 0
    return jsonify({
        'status':          'ok',
        'engine':          'Swiss Ephemeris',
        'version':         swe.version,
        'timezone':        'built-in geo database (no extra deps)',
        'database':        db_status,
        'resend':          resend_status,
        'members':         member_count,
        'spots_remaining': max(0, 200 - member_count),
    })




@app.route('/founding-status', methods=['GET'])
def founding_status():
    """Returns founding member count and spots remaining."""
    members, _ = supabase_request('GET', 'users', params={'select':'id','limit':'200'})
    count = len(members) if members else 0
    return jsonify({
        'success':       True,
        'members':       count,
        'cap':           FOUNDING_MEMBER_CAP,
        'spots_left':    max(0, FOUNDING_MEMBER_CAP - count),
        'is_founding':   count < FOUNDING_MEMBER_CAP,
        'pct_full':      round((count / FOUNDING_MEMBER_CAP) * 100),
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

        # Check founding member cap
        all_members, _ = supabase_request('GET', 'users', params={'select':'id','limit':'500'})
        member_count = len(all_members) if all_members else 0
        is_founding  = member_count < 200
        member_number = member_count + 1

        # Check if email already exists
        existing, err = supabase_request('GET', 'users',
            params={'email': f'eq.{data["email"]}', 'select': 'id'})
        if existing and len(existing) > 0:
            return jsonify({'error':'Email already registered','exists':True}), 409

        # Count total members for founding member tracking
        all_members, _ = supabase_request('GET', 'users', params={'select':'id'})
        member_count = len(all_members) if all_members else 0
        founding_member = member_count < 200
        founding_number = member_count + 1

        # Check founding member cap (200 free spots)
        FOUNDING_CAP = 200
        all_users, _ = supabase_request('GET', 'users', params={'select':'id'})
        current_count = len(all_users) if all_users else 0
        if current_count >= FOUNDING_CAP:
            return jsonify({
                'error': 'Founding membership is full',
                'founding_full': True,
                'message': 'All 200 founding spots have been claimed. Join the waitlist.'
            }), 403
        founding_number = current_count + 1

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
            # Founding member status
            'founding_member': is_founding,
            'member_number':   member_number,
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

        return jsonify({
            'success':       True,
            'userId':        user_id,
            'message':       f'Welcome to Destined! You are founding member #{member_number}.' if is_founding else 'Welcome to Destined!',
            'founding':      is_founding,
            'memberNumber':  member_number,
            'remaining':     max(0, 200 - member_number),
        })

    except Exception as e:
        return jsonify({'error':str(e),'success':False}), 500


@app.route('/matches/<user_id>', methods=['GET'])
def get_matches(user_id):
    """Get top compatibility matches with age filter, mutual seeking, and founding member count."""
    try:
        user_data, err = supabase_request('GET', 'users', params={'id':'eq.'+user_id, 'select':'*'})
        if err or not user_data:
            return jsonify({'error':'User not found'}), 404
        user = user_data[0]

        seeking    = user.get('seeking','Everyone')
        user_gender = user.get('gender','')

        if seeking == 'Women':   gender_filter = 'eq.Woman'
        elif seeking == 'Men':   gender_filter = 'eq.Man'
        else:                    gender_filter = None

        params = {'id': f'neq.{user_id}', 'select': '*', 'limit': '500'}
        if gender_filter:
            params['gender'] = gender_filter

        candidates, err = supabase_request('GET', 'users', params=params)
        if err:
            return jsonify({'error': f'Database error: {err}'}), 500

        # Total member count for founding member display
        all_users, _ = supabase_request('GET', 'users', params={'select':'id'})
        total_members    = len(all_users) if all_users else 0
        founding_spots_left = max(0, 200 - total_members)

        if not candidates:
            return jsonify({'success':True,'matches':[],'total':0,
                'totalMembers':total_members,'foundingLeft':founding_spots_left,'isFounding':total_members<=200})

        # Age range filter
        def parse_age_range(r):
            if not r: return None, None
            r = r.replace('+','').strip()
            if '-' in r:
                parts = r.split('-')
                try: return int(parts[0]), int(parts[1])
                except: return None, None
            try: return int(r), 99
            except: return None, None

        from datetime import date
        current_year = date.today().year
        seek_min, seek_max = parse_age_range(user.get('seek_age_range',''))

        user_planets = build_planets_from_record(user)
        scored = []

        for candidate in candidates:
            # Age filter
            birth_year = candidate.get('birth_year')
            if birth_year and seek_min and seek_max:
                age = current_year - birth_year
                if age < seek_min or age > seek_max:
                    continue

            # Mutual seeking filter — candidate must also be open to user's gender
            cand_seeking = candidate.get('seeking','Everyone')
            if cand_seeking != 'Everyone' and user_gender:
                if cand_seeking == 'Women' and user_gender != 'Woman': continue
                if cand_seeking == 'Men'   and user_gender != 'Man':   continue

            cand_planets = build_planets_from_record(candidate)
            score, aspects = calc_synastry(user_planets, cand_planets)

            scored.append({
                'userId':          candidate['id'],
                'name':            candidate['name'],
                'sunSign':         candidate.get('sun_sign',''),
                'moonSign':        candidate.get('moon_sign',''),
                'ascSign':         candidate.get('asc_sign',''),
                'venusSign':       candidate.get('venus_sign',''),
                'marsSign':        candidate.get('mars_sign',''),
                'dominantElement': candidate.get('dominant_element',''),
                'birthYear':       birth_year,
                'gender':          candidate.get('gender',''),
                'city':            candidate.get('birth_city',''),
                'score':           score,
                'aspects':         aspects[:6],
            })

        scored.sort(key=lambda x: x['score'], reverse=True)

        return jsonify({
            'success':      True,
            'matches':      scored[:20],
            'total':        len(scored),
            'totalMembers': total_members,
            'foundingLeft': founding_spots_left,
            'isFounding':   total_members <= 200,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/founding-count', methods=['GET'])
def founding_count():
    """Public endpoint — returns founding member count and spots remaining."""
    try:
        all_users, _ = supabase_request('GET', 'users', params={'select':'id'})
        count = len(all_users) if all_users else 0
        return jsonify({
            'success':        True,
            'members':        count,
            'cap':            200,
            'spots_remaining': max(0, 200 - count),
            'is_full':        count >= 200,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/founding-stats', methods=['GET'])
def founding_stats():
    """Get founding member stats for landing page counter."""
    users, err = supabase_request('GET', 'users', params={'select':'id', 'limit':'500'})
    if err:
        return jsonify({'error': err}), 500
    total     = len(users) if users else 0
    spots_left = max(0, FOUNDING_MEMBER_CAP - total)
    return jsonify({
        'success':      True,
        'total':        total,
        'cap':          FOUNDING_MEMBER_CAP,
        'spotsLeft':    spots_left,
        'isFull':       total >= FOUNDING_MEMBER_CAP,
        'pctFull':      round((total / FOUNDING_MEMBER_CAP) * 100),
    })

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
            return jsonify({'success':True,'message':'Already delivered','already_sent':True})
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
    return jsonify({
        'stripe':    'configured' if os.environ.get('STRIPE_SECRET_KEY') else 'missing',
        'anthropic': 'configured' if os.environ.get('ANTHROPIC_API_KEY') else 'missing',
    })



def founding_status():
    """Get founding member status — how many spots remain."""
    try:
        members, err = supabase_request('GET', 'users', 
            params={'select':'id','limit':'500'})
        count = len(members) if members else 0
        remaining = max(0, 200 - count)
        return jsonify({
            'success':   True,
            'total':     count,
            'cap':       200,
            'remaining': remaining,
            'is_open':   remaining > 0,
            'message':   f'{remaining} of 200 founding spots remaining' if remaining > 0 else 'Founding membership is now closed',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/deliver-reading-get', methods=['GET'])
def deliver_reading_get():
    """Trigger reading delivery via GET request (browser-friendly)."""
    user_id = request.args.get('userId','')
    if not user_id:
        return jsonify({'error':'Provide userId parameter'}), 400
    try:
        users, err = supabase_request('GET','users',
            params={'id':f'eq.{user_id}','select':'*'})
        if err or not users:
            return jsonify({'error':'User not found'}), 404
        user = users[0]
        if user.get('reading_delivered'):
            return f"<h2 style='font-family:serif;color:green;padding:40px'>✓ Reading already delivered to {user['email']} — check your inbox!</h2>"
        reading, err = generate_ai_reading(user)
        if err:
            return f"<h2 style='font-family:serif;color:red;padding:40px'>✗ Reading generation failed: {err}</h2>"
        resend_key = os.environ.get('RESEND_API_KEY','')
        sent, detail = send_reading_email(user['email'], user['name'], reading, user_id, resend_key)
        if not sent:
            return f"<h2 style='font-family:serif;color:red;padding:40px'>✗ Email failed: {detail}</h2>"
        supabase_request('PATCH','users',data={'reading_delivered':True},params={'id':f'eq.{user_id}'})
        return f"<h2 style='font-family:serif;color:green;padding:40px'>✓ Reading delivered to {user['email']} — check your inbox now!</h2>"
    except Exception as e:
        return f"<h2 style='font-family:serif;color:red;padding:40px'>✗ Error: {str(e)}</h2>"


# ══════════════════════════════════════════
# SPIRITUAL LEVEL REPORT ENDPOINTS
# ══════════════════════════════════════════

def send_slr_email(to_email, person1_name, person2_name, scores, resend_key):
    """Send the Spiritual Level Report to customer."""
    vibration = scores.get('vibration', 0)
    readiness = scores.get('readiness', 0)
    divine    = scores.get('divine', 0)
    union     = scores.get('union', 0)
    past_life = scores.get('past_life', 'Uncertain')
    contract  = scores.get('contract', 'Uncertain')
    note      = scores.get('note', '')

    def bar(pct):
        filled = int(pct / 5)
        return '█' * filled + '░' * (20 - filled) + f' {pct}%'

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#06060f;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#06060f;padding:40px 20px;">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="max-width:600px;width:100%;">
<tr><td style="text-align:center;padding:40px 40px 32px;border-bottom:1px solid rgba(155,122,200,.2);">
  <div style="font-size:11px;letter-spacing:6px;color:#c9a84c;text-transform:uppercase;margin-bottom:8px;">DESTINED</div>
  <div style="font-size:11px;letter-spacing:3px;color:rgba(196,168,232,.6);text-transform:uppercase;">Spiritual Level Report</div>
</td></tr>
<tr><td style="background:#0d0b1e;padding:48px 40px;">
  <p style="font-size:13px;letter-spacing:3px;color:#c9a84c;text-transform:uppercase;margin:0 0 12px;">A reading for</p>
  <h1 style="font-size:28px;font-weight:300;color:#f0eefc;line-height:1.3;margin:0 0 32px;">
    {person1_name} <em style="color:#c4a8e8;font-style:italic;">&</em> {person2_name}
  </h1>

  <div style="background:rgba(155,122,200,.05);border:1px solid rgba(155,122,200,.15);padding:28px;margin-bottom:28px;">
    <div style="font-size:10px;letter-spacing:3px;color:#c4a8e8;text-transform:uppercase;margin-bottom:20px;">Frequency Scores</div>

    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05);">
        <span style="font-size:13px;color:#a8a8c0;">⚡ Vibrational Match</span>
        <span style="font-size:18px;font-style:italic;color:#c4a8e8;float:right;">{vibration}%</span>
      </td></tr>
      <tr><td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05);">
        <span style="font-size:13px;color:#a8a8c0;">💗 Relationship Readiness</span>
        <span style="font-size:18px;font-style:italic;color:#c4a8e8;float:right;">{readiness}%</span>
      </td></tr>
      <tr><td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05);">
        <span style="font-size:13px;color:#a8a8c0;">✨ Divine Appointment</span>
        <span style="font-size:18px;font-style:italic;color:#c4a8e8;float:right;">{divine}%</span>
      </td></tr>
      <tr><td style="padding:10px 0;">
        <span style="font-size:13px;color:#a8a8c0;">🌿 Union Potential</span>
        <span style="font-size:18px;font-style:italic;color:#c4a8e8;float:right;">{union}%</span>
      </td></tr>
    </table>
  </div>

  <div style="margin-bottom:24px;">
    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:13px;">
      <span style="color:#a8a8c0;">🔁 Past Life Connection</span>
      <span style="color:#e8c96d;font-style:italic;">{past_life}</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:10px 0;font-size:13px;">
      <span style="color:#a8a8c0;">📖 Soul Contract Type</span>
      <span style="color:#e8c96d;font-style:italic;">{contract}</span>
    </div>
  </div>

  {f'''<div style="border-left:2px solid rgba(155,122,200,.4);padding:16px 20px;background:rgba(155,122,200,.04);margin-bottom:28px;">
    <div style="font-size:10px;letter-spacing:2px;color:#c4a8e8;text-transform:uppercase;margin-bottom:8px;">Practitioner Note</div>
    <p style="font-size:15px;font-style:italic;color:#f0eefc;line-height:1.8;margin:0;">&ldquo;{note}&rdquo;</p>
  </div>''' if note else ''}

  <p style="font-size:12px;color:rgba(168,168,192,.4);text-align:center;line-height:1.8;font-style:italic;">
    The only entity who knows the full truth of any soul connection is God.<br>
    This report is offered in the spirit of guidance, not certainty.
  </p>
</td></tr>
<tr><td style="padding:24px;text-align:center;">
  <p style="font-size:11px;color:rgba(168,168,192,.3);letter-spacing:2px;text-transform:uppercase;margin:0;">DESTINED · destined.cuartoastral.com</p>
</td></tr>
</table></td></tr></table>
</body></html>"""

    try:
        import http.client, ssl
        payload = json.dumps({
            "from":    "Destined <info@cuartoastral.com>",
            "to":      [to_email],
            "subject": f"✨ Your Spiritual Level Report — {person1_name} & {person2_name}",
            "html":    html,
        }).encode('utf-8')
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
        return resp.status in (200, 201), body
    except Exception as e:
        return False, str(e)


@app.route('/create-slr-payment', methods=['POST'])
def create_slr_payment():
    """Create Stripe checkout for Spiritual Level Report."""
    try:
        data = request.get_json() or {}
        price    = data.get('price', 27)
        delivery = data.get('delivery', '48 hours')
        email    = data.get('email', '')
        person1  = data.get('person1', {})
        person2  = data.get('person2', {})
        question = data.get('question', '')

        if not email or not person1 or not person2:
            return jsonify({'error': 'Missing required fields'}), 400

        # Store order in Supabase first
        order = {
            'customer_email': email,
            'price':          price,
            'delivery':       delivery,
            'person1_name':   person1.get('name',''),
            'person1_dob':    person1.get('dob',''),
            'person1_city':   person1.get('city',''),
            'person1_time':   person1.get('time',''),
            'person2_name':   person2.get('name',''),
            'person2_dob':    person2.get('dob',''),
            'person2_city':   person2.get('city',''),
            'person2_time':   person2.get('time',''),
            'question':       question,
            'completed':      False,
        }
        result, err = supabase_request('POST', 'slr_orders', order)
        if err:
            return jsonify({'error': f'Database error: {err}'}), 500

        order_id = result[0]['id'] if result else 'unknown'

        # Create Stripe session
        import base64, urllib.parse
        amount_cents = price * 100
        success_url = f"https://destined.cuartoastral.com/spiritual-level-report.html?order=success&orderId={order_id}"
        cancel_url  = f"https://destined.cuartoastral.com/spiritual-level-report.html"

        payload = urllib.parse.urlencode({
            'payment_method_types[]':                              'card',
            'line_items[0][price_data][currency]':                 'usd',
            'line_items[0][price_data][unit_amount]':              str(amount_cents),
            'line_items[0][price_data][product_data][name]':       f'Spiritual Level Report — {delivery} delivery',
            'line_items[0][price_data][product_data][description]':'Energetic compatibility assessment by certified practitioner',
            'line_items[0][quantity]':                             '1',
            'mode':                                                'payment',
            'success_url':                                         success_url,
            'cancel_url':                                          cancel_url,
            'customer_email':                                      email,
            'metadata[order_id]':                                  order_id,
        }).encode('utf-8')

        stripe_key = os.environ.get('STRIPE_SECRET_KEY','')
        auth = base64.b64encode(f"{stripe_key}:".encode()).decode()
        import http.client, ssl
        ctx  = ssl.create_default_context()
        conn = http.client.HTTPSConnection("api.stripe.com", context=ctx, timeout=15)
        conn.request("POST", "/v1/checkout/sessions", body=payload,
            headers={'Authorization':f'Basic {auth}','Content-Type':'application/x-www-form-urlencoded'})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()

        if resp.status == 200:
            return jsonify({'success': True, 'checkoutUrl': body['url']})
        else:
            return jsonify({'error': f'Stripe error: {body}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/slr-orders', methods=['GET'])
def slr_orders():
    """Get all SLR orders for practitioner portal."""
    admin_key = request.headers.get('X-Admin-Key','')
    if admin_key != os.environ.get('ADMIN_PASSWORD','destined2025'):
        return jsonify({'error':'Unauthorized'}), 401
    orders, err = supabase_request('GET', 'slr_orders',
        params={'select':'*','order':'created_at.desc','limit':'100'})
    if err:
        return jsonify({'error': err}), 500
    return jsonify({'success': True, 'orders': orders or []})


@app.route('/slr-submit', methods=['POST'])
def slr_submit():
    """Practitioner submits assessment — triggers email delivery."""
    admin_key = request.headers.get('X-Admin-Key','')
    if admin_key != os.environ.get('ADMIN_PASSWORD','destined2025'):
        return jsonify({'error':'Unauthorized'}), 401
    try:
        data     = request.get_json() or {}
        order_id = data.get('orderId','')
        if not order_id:
            return jsonify({'error':'orderId required'}), 400

        # Get order
        orders, err = supabase_request('GET','slr_orders',
            params={'id':f'eq.{order_id}','select':'*'})
        if err or not orders:
            return jsonify({'error':'Order not found'}), 404
        order = orders[0]

        scores = {
            'vibration': data.get('vibration', 70),
            'readiness': data.get('readiness', 70),
            'divine':    data.get('divine', 70),
            'union':     data.get('union', 70),
            'past_life': data.get('pastLife','Uncertain'),
            'contract':  data.get('contract','Uncertain'),
            'note':      data.get('note',''),
        }

        # Send email
        resend_key = os.environ.get('RESEND_API_KEY','')
        sent, detail = send_slr_email(
            order['customer_email'],
            order['person1_name'],
            order['person2_name'],
            scores, resend_key
        )
        if not sent:
            return jsonify({'error': f'Email failed: {detail}'}), 500

        # Mark completed
        supabase_request('PATCH','slr_orders',
            data={'completed':True,'scores':json.dumps(scores)},
            params={'id':f'eq.{order_id}'})

        return jsonify({'success': True, 'message': f'Report delivered to {order["customer_email"]}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def founding_count():
    """Get current founding member count for landing page display."""
    members, err = supabase_request('GET', 'users', params={'select':'id'})
    if err:
        return jsonify({'error': err}), 500
    count = len(members) if members else 0
    return jsonify({
        'success':        True,
        'total':          count,
        'spotsRemaining': max(0, 200 - count),
        'spotsTotal':     200,
        'isFull':         count >= 200,
        'pctFilled':      min(100, round((count / 200) * 100)),
    })


@app.route('/stats', methods=['GET'])
def stats():
    """Public stats — founding member count."""
    users, err = supabase_request('GET', 'users',
        params={'select': 'id', 'limit': '500'})
    count = len(users) if users else 0
    founding_cap  = 200
    spots_taken   = count
    spots_left    = max(0, founding_cap - spots_taken)
    return jsonify({
        'success':       True,
        'totalMembers':  count,
        'foundingCap':   founding_cap,
        'spotsTaken':    spots_taken,
        'spotsLeft':     spots_left,
        'isFull':        spots_left == 0,
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
