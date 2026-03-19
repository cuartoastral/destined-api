"""
Destined Natal Chart API
Swiss Ephemeris + built-in timezone database (no extra dependencies).
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe
import math, os, urllib.request, urllib.parse, json

app = Flask(__name__)
CORS(app)
swe.set_ephe_path('')

# ── Timezone database ──
# Maps timezone name → UTC offset in hours (standard, non-DST)
# DST adjustments handled by the DST rules table below
TZ_DB = {
    # Americas
    'America/New_York': -5, 'America/Chicago': -6, 'America/Denver': -7,
    'America/Los_Angeles': -8, 'America/Anchorage': -9, 'America/Honolulu': -10,
    'America/Phoenix': -7, 'America/Detroit': -5, 'America/Indiana/Indianapolis': -5,
    'America/Bogota': -5, 'America/Lima': -5, 'America/Guayaquil': -5,
    'America/Caracas': -4, 'America/La_Paz': -4, 'America/Manaus': -4,
    'America/Halifax': -4, 'America/Santo_Domingo': -4, 'America/Puerto_Rico': -4,
    'America/Sao_Paulo': -3, 'America/Argentina/Buenos_Aires': -3,
    'America/Santiago': -4, 'America/Asuncion': -4, 'America/Montevideo': -3,
    'America/Noronha': -2, 'America/Toronto': -5, 'America/Vancouver': -8,
    'America/Winnipeg': -6, 'America/Edmonton': -7, 'America/Halifax': -4,
    'America/St_Johns': -3.5, 'America/Mexico_City': -6, 'America/Monterrey': -6,
    'America/Tijuana': -8, 'America/Guatemala': -6, 'America/El_Salvador': -6,
    'America/Managua': -6, 'America/Costa_Rica': -6, 'America/Panama': -5,
    'America/Havana': -5, 'America/Jamaica': -5, 'America/Nassau': -5,
    # Europe
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
    # Asia/Pacific
    'Asia/Dubai': 4, 'Asia/Kabul': 4.5, 'Asia/Karachi': 5,
    'Asia/Kolkata': 5.5, 'Asia/Kathmandu': 5.75, 'Asia/Dhaka': 6,
    'Asia/Rangoon': 6.5, 'Asia/Bangkok': 7, 'Asia/Jakarta': 7,
    'Asia/Singapore': 8, 'Asia/Hong_Kong': 8, 'Asia/Shanghai': 8,
    'Asia/Taipei': 8, 'Asia/Manila': 8, 'Asia/Seoul': 9,
    'Asia/Tokyo': 9, 'Asia/Yakutsk': 9, 'Asia/Adelaide': 9.5,
    'Australia/Darwin': 9.5, 'Australia/Sydney': 10, 'Australia/Melbourne': 10,
    'Australia/Brisbane': 10, 'Australia/Perth': 8, 'Pacific/Auckland': 12,
    'Pacific/Fiji': 12, 'Pacific/Honolulu': -10, 'Pacific/Guam': 10,
    # Africa/Middle East
    'Africa/Cairo': 2, 'Africa/Johannesburg': 2, 'Africa/Lagos': 1,
    'Africa/Nairobi': 3, 'Africa/Casablanca': 0, 'Africa/Accra': 0,
    'Africa/Addis_Ababa': 3, 'Africa/Khartoum': 3, 'Africa/Dar_es_Salaam': 3,
    'Asia/Jerusalem': 2, 'Asia/Dubai': 4, 'Asia/Riyadh': 3, 'Asia/Baghdad': 3,
    'Asia/Tehran': 3.5, 'Asia/Beirut': 2, 'Asia/Amman': 2,
}

# Countries/regions that observe DST (simplified: +1 in summer)
# Format: tz_name -> (dst_offset, [months_with_dst])
# Northern hemisphere DST: roughly March-October (+1h)
# Southern hemisphere DST: roughly October-March (+1h)
DST_RULES = {
    # North America (clocks spring forward Mar, fall back Nov)
    'America/New_York':      (1, [3,4,5,6,7,8,9,10]),
    'America/Chicago':       (1, [3,4,5,6,7,8,9,10]),
    'America/Denver':        (1, [3,4,5,6,7,8,9,10]),
    'America/Los_Angeles':   (1, [3,4,5,6,7,8,9,10]),
    'America/Anchorage':     (1, [3,4,5,6,7,8,9,10]),
    'America/Detroit':       (1, [3,4,5,6,7,8,9,10]),
    'America/Indiana/Indianapolis': (1, [3,4,5,6,7,8,9,10]),
    'America/Toronto':       (1, [3,4,5,6,7,8,9,10]),
    'America/Vancouver':     (1, [3,4,5,6,7,8,9,10]),
    'America/Winnipeg':      (1, [3,4,5,6,7,8,9,10]),
    'America/Edmonton':      (1, [3,4,5,6,7,8,9,10]),
    'America/Halifax':       (1, [3,4,5,6,7,8,9,10]),
    'America/Havana':        (1, [3,4,5,6,7,8,9,10]),
    'America/Nassau':        (1, [3,4,5,6,7,8,9,10]),
    # South America (some observe DST Oct-Mar)
    'America/Sao_Paulo':     (1, [10,11,12,1,2]),   # Brazil (abolished 2019)
    'America/Santiago':      (1, [10,11,12,1,2,3]),
    'America/Asuncion':      (1, [10,11,12,1,2,3]),
    # Europe (last Sun March to last Sun October)
    'Europe/London':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Dublin':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Lisbon':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Paris':          (1, [3,4,5,6,7,8,9,10]),
    'Europe/Berlin':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Madrid':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Rome':           (1, [3,4,5,6,7,8,9,10]),
    'Europe/Amsterdam':      (1, [3,4,5,6,7,8,9,10]),
    'Europe/Stockholm':      (1, [3,4,5,6,7,8,9,10]),
    'Europe/Warsaw':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Athens':         (1, [3,4,5,6,7,8,9,10]),
    'Europe/Helsinki':       (1, [3,4,5,6,7,8,9,10]),
    'Europe/Kiev':           (1, [3,4,5,6,7,8,9,10]),
    # Australia (southern, Oct-Apr)
    'Australia/Sydney':      (1, [10,11,12,1,2,3]),
    'Australia/Melbourne':   (1, [10,11,12,1,2,3]),
    'Australia/Adelaide':    (1, [10,11,12,1,2,3]),
    # New Zealand
    'Pacific/Auckland':      (1, [9,10,11,12,1,2,3,4]),
}

# Geographic bbox for timezone lookup: (lat_min, lat_max, lon_min, lon_max) -> tz_name
# Ordered from most specific to least specific
GEO_TZ = [
    # Colombia (no DST ever)
    ((-4, 13, -79, -66), 'America/Bogota'),
    # Venezuela
    ((0, 13, -73, -59), 'America/Caracas'),
    # Ecuador
    ((-5, 2, -82, -75), 'America/Guayaquil'),
    # Peru
    ((-18, 0, -81, -68), 'America/Lima'),
    # Bolivia
    ((-23, -9, -70, -57), 'America/La_Paz'),
    # Argentina
    ((-55, -21, -74, -53), 'America/Argentina/Buenos_Aires'),
    # Chile
    ((-56, -17, -76, -66), 'America/Santiago'),
    # Paraguay
    ((-28, -19, -62, -54), 'America/Asuncion'),
    # Uruguay
    ((-35, -30, -58, -53), 'America/Montevideo'),
    # Brazil (large - Sao Paulo zone covers most)
    ((-34, 5, -74, -34), 'America/Sao_Paulo'),
    # Mexico
    ((14, 33, -118, -86), 'America/Mexico_City'),
    # Central America
    ((7, 18, -93, -77), 'America/Guatemala'),
    # Cuba
    ((19, 24, -85, -74), 'America/Havana'),
    # Eastern US/Canada
    ((24, 50, -83, -65), 'America/New_York'),
    # Central US
    ((25, 50, -104, -83), 'America/Chicago'),
    # Mountain US
    ((31, 50, -115, -104), 'America/Denver'),
    # Pacific US
    ((32, 50, -125, -115), 'America/Los_Angeles'),
    # Alaska
    ((54, 72, -170, -130), 'America/Anchorage'),
    # Hawaii
    ((18, 23, -161, -154), 'America/Honolulu'),
    # Canada Pacific
    ((48, 60, -140, -114), 'America/Vancouver'),
    # Canada Mountain
    ((49, 60, -120, -110), 'America/Edmonton'),
    # Canada Central
    ((49, 60, -102, -88), 'America/Winnipeg'),
    # Canada Atlantic
    ((44, 60, -64, -52), 'America/Halifax'),
    # UK/Ireland
    ((49, 61, -11, 2), 'Europe/London'),
    # Portugal
    ((36, 42, -10, -6), 'Europe/Lisbon'),
    # Spain
    ((35, 44, -9, 5), 'Europe/Madrid'),
    # France/Benelux
    ((42, 52, -5, 8), 'Europe/Paris'),
    # Germany/Austria/Swiss
    ((46, 55, 6, 18), 'Europe/Berlin'),
    # Italy
    ((36, 48, 6, 19), 'Europe/Rome'),
    # Scandinavia
    ((55, 71, 4, 32), 'Europe/Stockholm'),
    # Poland/Czech/Slovakia
    ((48, 55, 14, 24), 'Europe/Warsaw'),
    # Greece/Bulgaria/Romania
    ((35, 48, 20, 30), 'Europe/Athens'),
    # Turkey
    ((35, 42, 26, 45), 'Europe/Istanbul'),
    # Russia west
    ((50, 70, 27, 60), 'Europe/Moscow'),
    # Egypt
    ((22, 32, 24, 37), 'Africa/Cairo'),
    # South Africa
    ((-35, -22, 16, 33), 'Africa/Johannesburg'),
    # Nigeria
    ((4, 14, 2, 15), 'Africa/Lagos'),
    # Kenya/East Africa
    ((-5, 5, 33, 42), 'Africa/Nairobi'),
    # Israel
    ((29, 34, 34, 36), 'Asia/Jerusalem'),
    # Saudi Arabia
    ((22, 27, 51, 57), 'Asia/Dubai'),       # UAE
    ((16, 32, 36, 56), 'Asia/Riyadh'),
    # Iran
    ((25, 40, 44, 64), 'Asia/Tehran'),
    # India
    ((8, 37, 68, 97), 'Asia/Kolkata'),
    # Pakistan
    ((23, 37, 61, 77), 'Asia/Karachi'),
    # Bangladesh
    ((20, 27, 88, 93), 'Asia/Dhaka'),
    # China/HK/Taiwan
    ((18, 53, 73, 135), 'Asia/Shanghai'),
    # Japan
    ((24, 46, 122, 146), 'Asia/Tokyo'),
    # South Korea
    ((33, 38, 126, 130), 'Asia/Seoul'),
    # Thailand/Vietnam/Indochina
    ((5, 24, 98, 110), 'Asia/Bangkok'),
    # Indonesia/Singapore/Malaysia
    ((-8, 7, 95, 141), 'Asia/Singapore'),
    # Philippines
    ((4, 21, 116, 127), 'Asia/Manila'),
    # Australia East
    ((-44, -10, 141, 154), 'Australia/Sydney'),
    # Australia Central
    ((-38, -26, 129, 141), 'Australia/Adelaide'),
    # Australia West
    ((-35, -14, 113, 129), 'Australia/Perth'),
    # New Zealand
    ((-47, -34, 166, 178), 'Pacific/Auckland'),
]

def geo_to_tz(lat, lon):
    """Find timezone from coordinates using bounding boxes."""
    for (lat_min, lat_max, lon_min, lon_max), tz_name in GEO_TZ:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return tz_name
    # Last resort: estimate from longitude
    offset = round(lon / 15)
    return None

def resolve_utc_offset(year, month, day, hour, minute, lat, lon):
    """Resolve UTC offset with DST for any location and date."""
    tz_name = geo_to_tz(lat, lon)

    if tz_name and tz_name in TZ_DB:
        base_offset = TZ_DB[tz_name]
        # Check DST
        is_dst = False
        dst_offset = 0
        if tz_name in DST_RULES:
            dst_add, dst_months = DST_RULES[tz_name]
            if month in dst_months:
                # Simple month-based check (accurate enough for most cases)
                # Brazil abolished DST in 2019
                if tz_name == 'America/Sao_Paulo' and year >= 2019:
                    pass
                else:
                    is_dst = True
                    dst_offset = dst_add
        return base_offset + dst_offset, tz_name, is_dst
    else:
        # Pure longitude estimate
        offset = round(lon / 15 * 2) / 2
        return offset, f'Estimated from longitude ({lon:.2f}°)', False


# ── Constants ──
PLANETS = [
    (swe.SUN,       'sun',        'Sun',         '☉', '#f5c842'),
    (swe.MOON,      'moon',       'Moon',        '☽', '#c8c8e8'),
    (swe.MERCURY,   'mercury',    'Mercury',     '☿', '#90b8d0'),
    (swe.VENUS,     'venus',      'Venus',       '♀', '#e8a0a0'),
    (swe.MARS,      'mars',       'Mars',        '♂', '#e87050'),
    (swe.JUPITER,   'jupiter',    'Jupiter',     '♃', '#d4a860'),
    (swe.SATURN,    'saturn',     'Saturn',      '♄', '#a09070'),
    (swe.URANUS,    'uranus',     'Uranus',      '♅', '#80c8d0'),
    (swe.NEPTUNE,   'neptune',    'Neptune',     '♆', '#8080d0'),
    (swe.PLUTO,     'pluto',      'Pluto',       '♇', '#c080c0'),
    (swe.MEAN_NODE, 'northNode',  'North Node',  '☊', '#90c090'),
    (swe.CHIRON,    'chiron',     'Chiron',      '⚷', '#c8a870'),
]
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
SIGN_GLYPHS = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']
ELEMENTS = {
    'fire':  ['Aries','Leo','Sagittarius'],
    'earth': ['Taurus','Virgo','Capricorn'],
    'air':   ['Gemini','Libra','Aquarius'],
    'water': ['Cancer','Scorpio','Pisces'],
}
MODALITIES = {
    'cardinal': ['Aries','Cancer','Libra','Capricorn'],
    'fixed':    ['Taurus','Leo','Scorpio','Aquarius'],
    'mutable':  ['Gemini','Virgo','Sagittarius','Pisces'],
}
NODE_MEANINGS = {
    'Aries':       ('Lead boldly. Your soul is learning independence and self-initiation.', 'A past of co-dependence and people-pleasing.'),
    'Taurus':      ('Build security and lasting value. Peace is your destiny.', 'A past of disruption, transformation, and impermanence.'),
    'Gemini':      ('Embrace curiosity, flexibility, and open communication.', 'A past of rigid, singular thinking and fixed beliefs.'),
    'Cancer':      ('Nurture yourself and others. Emotional safety is your path.', 'A past of relentless ambition and emotional suppression.'),
    'Leo':         ('Step into creative self-expression and heartfelt leadership.', 'A past of group anonymity and self-erasure.'),
    'Virgo':       ('Master service, discernment, and grounded contribution.', 'A past of escapism and avoidance of reality.'),
    'Libra':       ('Learn partnership, fairness, and the art of meeting another.', 'A past of fierce self-reliance and resistance to others.'),
    'Scorpio':     ('Embrace transformation, depth, and surrender of control.', 'A past of material comfort and resistance to change.'),
    'Sagittarius': ('Seek truth, adventure, and expansive philosophy.', 'A past of small-picture thinking and rigid routine.'),
    'Capricorn':   ('Build mastery, discipline, and lasting legacy.', 'A past of emotional comfort without structure.'),
    'Aquarius':    ('Serve humanity, innovate, and find your people.', 'A past of ego, pride, and performance for approval.'),
    'Pisces':      ('Surrender to compassion, spirituality, and transcendence.', 'A past of hyper-criticism and over-analysis.'),
}
SOUL_SUMMARIES = {
    'fire':  'A radiant, self-directed soul who leads with passion and needs a partner who can match their fire without smothering it.',
    'earth': 'A grounded, loyal soul who builds love slowly and with intention — seeking permanence, not performance.',
    'air':   'An intellectually alive soul who falls for minds first. They need a partner who can meet them in thought and in freedom.',
    'water': 'A deeply feeling, intuitive soul who loves with their whole being — seeking emotional safety above all else.',
}

def lon_to_sign(lon):
    lon = lon % 360
    idx = int(lon / 30)
    return {'sign': SIGNS[idx], 'glyph': SIGN_GLYPHS[idx], 'degree': round(lon % 30, 4), 'lon': round(lon, 4)}

def get_element(sign):
    for el, signs in ELEMENTS.items():
        if sign in signs: return el
    return 'fire'

def get_modality(sign):
    for mod, signs in MODALITIES.items():
        if sign in signs: return mod
    return 'cardinal'

def get_house_of(planet_lon, cusps):
    planet_lon = planet_lon % 360
    for i in range(12):
        start = cusps[i] % 360
        end   = cusps[(i + 1) % 12] % 360
        if start < end:
            if start <= planet_lon < end: return i + 1
        else:
            if planet_lon >= start or planet_lon < end: return i + 1
    return 1


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'engine': 'Swiss Ephemeris',
        'version': swe.version,
        'timezone': 'built-in geo database (no extra deps)',
    })




@app.route('/chart', methods=['POST'])
def calculate_chart():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        year     = int(data['year'])
        month    = int(data['month'])
        day      = int(data['day'])
        hour     = int(data.get('hour', 12))
        minute   = int(data.get('minute', 0))
        lat      = float(data['lat'])
        lon      = float(data['lon'])
        name     = str(data.get('name', 'Chart'))
        has_time = bool(data.get('has_time', True))

        # Resolve timezone
        if 'utc_offset' in data and data['utc_offset'] is not None and data['utc_offset'] != '':
            utc_offset = float(data['utc_offset'])
            tz_name    = 'Manual'
            is_dst     = False
        else:
            utc_offset, tz_name, is_dst = resolve_utc_offset(year, month, day, hour, minute, lat, lon)

        # Local → UTC
        utc_decimal = hour + minute / 60.0 - utc_offset
        day_adj = day
        if utc_decimal < 0:   utc_decimal += 24; day_adj -= 1
        elif utc_decimal >= 24: utc_decimal -= 24; day_adj += 1

        jd_ut = swe.julday(year, month, day_adj, utc_decimal)

        # Planets
        planets_result = []
        el_counts = {'fire': 0, 'earth': 0, 'air': 0, 'water': 0}

        for planet_id, key, display_name, glyph, color in PLANETS:
            try:
                result, _ = swe.calc_ut(jd_ut, planet_id, swe.FLG_SWIEPH)
                planet_lon    = result[0]
                is_retrograde = result[3] < 0
                sd = lon_to_sign(planet_lon)
                el = get_element(sd['sign'])
                if key in ['sun','moon','mercury','venus','mars','jupiter','saturn']:
                    el_counts[el] += 1
                planets_result.append({
                    'key': key, 'name': display_name, 'glyph': glyph, 'color': color,
                    'lon': round(planet_lon, 4), 'sign': sd['sign'], 'signGlyph': sd['glyph'],
                    'degree': round(sd['degree'], 2), 'element': el,
                    'modality': get_modality(sd['sign']),
                    'retrograde': is_retrograde, 'house': None,
                })
            except: continue

        # South Node
        nn = next((p for p in planets_result if p['key'] == 'northNode'), None)
        if nn:
            sn_lon = (nn['lon'] + 180) % 360
            sn_sd  = lon_to_sign(sn_lon)
            planets_result.append({
                'key': 'southNode', 'name': 'South Node', 'glyph': '☋', 'color': '#c09080',
                'lon': round(sn_lon, 4), 'sign': sn_sd['sign'], 'signGlyph': sn_sd['glyph'],
                'degree': round(sn_sd['degree'], 2), 'element': get_element(sn_sd['sign']),
                'modality': get_modality(sn_sd['sign']), 'retrograde': False, 'house': None,
            })

        # Houses (Placidus)
        houses_data = None
        asc_data = mc_data = None

        if has_time:
            try:
                house_result = swe.houses(jd_ut, lat, lon, b'P')
                # Handle both pyswisseph return formats
                if isinstance(house_result[0], (list, tuple)):
                    cusps = house_result[0]
                    ascmc = house_result[1]
                else:
                    cusps = house_result[:13]
                    ascmc = house_result[13:]
                asc_lon = float(ascmc[0])
                mc_lon  = float(ascmc[1])
                asc_sd  = lon_to_sign(asc_lon)
                mc_sd   = lon_to_sign(mc_lon)
                asc_data = {'lon': round(asc_lon,4), 'sign': asc_sd['sign'], 'signGlyph': asc_sd['glyph'], 'degree': round(asc_sd['degree'],2)}
                mc_data  = {'lon': round(mc_lon,4),  'sign': mc_sd['sign'],  'signGlyph': mc_sd['glyph'],  'degree': round(mc_sd['degree'],2)}
                # This version of pyswisseph returns cusps[0..11] (no placeholder at index 0)
                house_cusps = [float(cusps[i]) for i in range(0, 12)]
                houses_data = [{'house': i+1, 'lon': round(c,4),
                                'sign': lon_to_sign(c)['sign'],
                                'signGlyph': lon_to_sign(c)['glyph'],
                                'degree': round(lon_to_sign(c)['degree'],2)}
                               for i, c in enumerate(house_cusps)]
                for p in planets_result:
                    p['house'] = get_house_of(p['lon'], house_cusps)
                planets_result.append({
                    'key': 'asc', 'name': 'Ascendant', 'glyph': 'AC', 'color': '#e8c96d',
                    'lon': round(asc_lon,4), 'sign': asc_sd['sign'], 'signGlyph': asc_sd['glyph'],
                    'degree': round(asc_sd['degree'],2), 'element': get_element(asc_sd['sign']),
                    'modality': get_modality(asc_sd['sign']), 'retrograde': False, 'house': 1,
                })
                planets_result.append({
                    'key': 'mc', 'name': 'Midheaven', 'glyph': 'MC', 'color': '#c9a84c',
                    'lon': round(mc_lon,4), 'sign': mc_sd['sign'], 'signGlyph': mc_sd['glyph'],
                    'degree': round(mc_sd['degree'],2), 'element': get_element(mc_sd['sign']),
                    'modality': get_modality(mc_sd['sign']), 'retrograde': False, 'house': 10,
                })
            except Exception as e:
                return jsonify({'error': f'House calc error: {str(e)}', 'success': False}), 500

        # Soul profile
        dominant_element = max(el_counts, key=el_counts.get)
        def ps(key):
            p = next((x for x in planets_result if x['key'] == key), None)
            return p['sign'] if p else ''
        nn_sign = ps('northNode'); sn_sign = ps('southNode')
        nn_d, sn_d = NODE_MEANINGS.get(nn_sign, ('Your destiny awaits.', 'Your karmic past.'))
        soul_profile = {
            'dominantElement': dominant_element, 'elementCounts': el_counts,
            'summary': SOUL_SUMMARIES.get(dominant_element, ''),
            'sunSign': ps('sun'), 'moonSign': ps('moon'),
            'ascSign': asc_data['sign'] if asc_data else None,
            'venusSign': ps('venus'), 'marsSign': ps('mars'),
            'northNodeSign': nn_sign, 'southNodeSign': sn_sign,
            'northNodeDestiny': nn_d, 'southNodePast': sn_d,
        }

        # Houses of love
        houses_of_love = None
        if has_time and houses_data:
            def hi(idx, meaning):
                h = houses_data[idx]
                return {'sign': h['sign'], 'glyph': h['signGlyph'], 'degree': h['degree'], 'meaning': meaning}
            houses_of_love = {
                'h5':  hi(4,  'Romance, flirtation, and the early magic of love.'),
                'h7':  hi(6,  'Committed partnership and what you seek in a long-term union.'),
                'h11': hi(10, 'Friendship, shared vision, and communities where love finds you.'),
            }

        return jsonify({
            'success': True, 'name': name,
            'birthData': {
                'year': year, 'month': month, 'day': day, 'hour': hour, 'minute': minute,
                'lat': lat, 'lon': lon, 'utcOffset': round(utc_offset, 2),
                'timezoneName': tz_name, 'isDST': is_dst,
                'hasTime': has_time, 'julianDay': round(jd_ut, 6),
            },
            'planets': planets_result, 'houses': houses_data,
            'asc': asc_data, 'mc': mc_data,
            'soulProfile': soul_profile, 'housesOfLove': houses_of_love,
        })

    except KeyError as e:
        return jsonify({'error': f'Missing field: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@app.route('/geocode', methods=['GET'])
def geocode():
    query = request.args.get('q', '')
    if not query: return jsonify({'error': 'No query'}), 400
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=6&addressdetails=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Destined-App/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return jsonify(json.loads(resp.read()))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
