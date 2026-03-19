"""
Destined Natal Chart API
Uses Swiss Ephemeris (pyswisseph) for Astro.com-level accuracy.
Placidus house system.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe
import math
import os

app = Flask(__name__)
CORS(app)  # Allow requests from the frontend

# ── Swiss Ephemeris setup ──
# Use built-in ephemeris data (no extra files needed for dates 1800-2400)
swe.set_ephe_path('')

# Planet constants
PLANETS = [
    (swe.SUN,     'sun',       'Sun',        '☉', '#f5c842'),
    (swe.MOON,    'moon',      'Moon',       '☽', '#c8c8e8'),
    (swe.MERCURY, 'mercury',   'Mercury',    '☿', '#90b8d0'),
    (swe.VENUS,   'venus',     'Venus',      '♀', '#e8a0a0'),
    (swe.MARS,    'mars',      'Mars',       '♂', '#e87050'),
    (swe.JUPITER, 'jupiter',   'Jupiter',    '♃', '#d4a860'),
    (swe.SATURN,  'saturn',    'Saturn',     '♄', '#a09070'),
    (swe.URANUS,  'uranus',    'Uranus',     '♅', '#80c8d0'),
    (swe.NEPTUNE, 'neptune',   'Neptune',    '♆', '#8080d0'),
    (swe.PLUTO,   'pluto',     'Pluto',      '♇', '#c080c0'),
    (swe.MEAN_NODE, 'northNode', 'North Node', '☊', '#90c090'),
    (swe.CHIRON,  'chiron',    'Chiron',     '⚷', '#c8a870'),
]

SIGNS = [
    'Aries','Taurus','Gemini','Cancer','Leo','Virgo',
    'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'
]
SIGN_GLYPHS = ['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓']
ELEMENTS = {
    'fire': ['Aries','Leo','Sagittarius'],
    'earth': ['Taurus','Virgo','Capricorn'],
    'air': ['Gemini','Libra','Aquarius'],
    'water': ['Cancer','Scorpio','Pisces']
}
MODALITIES = {
    'cardinal': ['Aries','Cancer','Libra','Capricorn'],
    'fixed': ['Taurus','Leo','Scorpio','Aquarius'],
    'mutable': ['Gemini','Virgo','Sagittarius','Pisces']
}

NODE_MEANINGS = {
    'Aries':       ('Lead boldly. Your soul is learning independence and self-initiation.',
                    'A past of co-dependence and people-pleasing.'),
    'Taurus':      ('Build security and lasting value. Peace is your destiny.',
                    'A past of disruption, transformation, and impermanence.'),
    'Gemini':      ('Embrace curiosity, flexibility, and open communication.',
                    'A past of rigid, singular thinking and fixed beliefs.'),
    'Cancer':      ('Nurture yourself and others. Emotional safety is your path.',
                    'A past of relentless ambition and emotional suppression.'),
    'Leo':         ('Step into creative self-expression and heartfelt leadership.',
                    'A past of group anonymity and self-erasure.'),
    'Virgo':       ('Master service, discernment, and grounded contribution.',
                    'A past of escapism and avoidance of reality.'),
    'Libra':       ('Learn partnership, fairness, and the art of meeting another.',
                    'A past of fierce self-reliance and resistance to others.'),
    'Scorpio':     ('Embrace transformation, depth, and surrender of control.',
                    'A past of material comfort and resistance to change.'),
    'Sagittarius': ('Seek truth, adventure, and expansive philosophy.',
                    'A past of small-picture thinking and rigid routine.'),
    'Capricorn':   ('Build mastery, discipline, and lasting legacy.',
                    'A past of emotional comfort without structure.'),
    'Aquarius':    ('Serve humanity, innovate, and find your people.',
                    'A past of ego, pride, and performance for approval.'),
    'Pisces':      ('Surrender to compassion, spirituality, and transcendence.',
                    'A past of hyper-criticism and over-analysis.'),
}

SOUL_SUMMARIES = {
    'fire': 'A radiant, self-directed soul who leads with passion and needs a partner who can match their fire without smothering it.',
    'earth': 'A grounded, loyal soul who builds love slowly and with intention — seeking permanence, not performance.',
    'air': 'An intellectually alive soul who falls for minds first. They need a partner who can meet them in thought and in freedom.',
    'water': 'A deeply feeling, intuitive soul who loves with their whole being — seeking emotional safety above all else.',
}


def lon_to_sign(lon):
    """Convert ecliptic longitude to sign name, glyph, and degree within sign."""
    lon = lon % 360
    idx = int(lon / 30)
    deg = lon % 30
    return {
        'sign': SIGNS[idx],
        'glyph': SIGN_GLYPHS[idx],
        'degree': round(deg, 4),
        'lon': round(lon, 4),
        'signIndex': idx,
    }


def get_element(sign):
    for el, signs in ELEMENTS.items():
        if sign in signs:
            return el
    return 'fire'


def get_modality(sign):
    for mod, signs in MODALITIES.items():
        if sign in signs:
            return mod
    return 'cardinal'


def get_house_of(planet_lon, cusps):
    """Determine which Placidus house a planet falls in."""
    planet_lon = planet_lon % 360
    for i in range(12):
        start = cusps[i] % 360
        end = cusps[(i + 1) % 12] % 360
        if start < end:
            if start <= planet_lon < end:
                return i + 1
        else:  # crosses 0°
            if planet_lon >= start or planet_lon < end:
                return i + 1
    return 1


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'engine': 'Swiss Ephemeris', 'version': swe.version})


@app.route('/chart', methods=['POST'])
def calculate_chart():
    """
    Calculate a natal chart.
    
    Request body:
    {
        "year": 1978,
        "month": 2,
        "day": 23,
        "hour": 2,
        "minute": 3,
        "lat": 10.9639,
        "lon": -74.7964,
        "utc_offset": -5,
        "name": "Ingrid"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract and validate input
        year   = int(data['year'])
        month  = int(data['month'])
        day    = int(data['day'])
        hour   = int(data.get('hour', 12))
        minute = int(data.get('minute', 0))
        lat    = float(data['lat'])
        lon    = float(data['lon'])
        utc_offset = float(data.get('utc_offset', 0))
        name   = str(data.get('name', 'Chart'))
        has_time = data.get('has_time', True)

        # Convert local time to UTC
        local_decimal = hour + minute / 60.0
        utc_decimal = local_decimal - utc_offset

        # Handle day rollover
        day_adj = day
        if utc_decimal < 0:
            utc_decimal += 24
            day_adj -= 1
        elif utc_decimal >= 24:
            utc_decimal -= 24
            day_adj += 1

        # Calculate Julian Day (UT)
        jd_ut = swe.julday(year, month, day_adj, utc_decimal)

        # ── Calculate all planet positions ──
        planets_result = []
        el_counts = {'fire': 0, 'earth': 0, 'air': 0, 'water': 0}

        for planet_id, key, display_name, glyph, color in PLANETS:
            try:
                # swe.calc_ut returns (longitude, latitude, distance, speed_lon, speed_lat, speed_dist)
                result, flag = swe.calc_ut(jd_ut, planet_id, swe.FLG_SWIEPH)
                planet_lon = result[0]
                planet_speed = result[3]  # positive = direct, negative = retrograde
                is_retrograde = planet_speed < 0

                sign_data = lon_to_sign(planet_lon)
                element = get_element(sign_data['sign'])
                modality = get_modality(sign_data['sign'])

                # Count elements for inner planets only
                if key in ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn']:
                    el_counts[element] += 1

                planets_result.append({
                    'key': key,
                    'name': display_name,
                    'glyph': glyph,
                    'color': color,
                    'lon': round(planet_lon, 4),
                    'sign': sign_data['sign'],
                    'signGlyph': sign_data['glyph'],
                    'degree': round(sign_data['degree'], 2),
                    'element': element,
                    'modality': modality,
                    'retrograde': is_retrograde,
                    'house': None,  # filled in after house calculation
                })
            except Exception as e:
                # Skip planets that can't be calculated
                continue

        # ── South Node (opposite of North Node) ──
        nn = next((p for p in planets_result if p['key'] == 'northNode'), None)
        if nn:
            sn_lon = (nn['lon'] + 180) % 360
            sn_sign = lon_to_sign(sn_lon)
            planets_result.append({
                'key': 'southNode',
                'name': 'South Node',
                'glyph': '☋',
                'color': '#c09080',
                'lon': round(sn_lon, 4),
                'sign': sn_sign['sign'],
                'signGlyph': sn_sign['glyph'],
                'degree': round(sn_sign['degree'], 2),
                'element': get_element(sn_sign['sign']),
                'modality': get_modality(sn_sign['sign']),
                'retrograde': False,
                'house': None,
            })

        # ── House calculation (Placidus) ──
        houses_data = None
        asc_data = None
        mc_data = None

        if has_time:
            try:
                # swe.houses returns (cusps tuple of 13, ascmc tuple of 10)
                # cusps[1..12] = house cusps, ascmc[0]=ASC, ascmc[1]=MC
                cusps, ascmc = swe.houses(jd_ut, lat, lon, b'P')  # P = Placidus

                asc_lon = ascmc[0]
                mc_lon  = ascmc[1]
                ic_lon  = (mc_lon + 180) % 360
                dsc_lon = (asc_lon + 180) % 360

                asc_sign = lon_to_sign(asc_lon)
                mc_sign  = lon_to_sign(mc_lon)

                asc_data = {
                    'lon': round(asc_lon, 4),
                    'sign': asc_sign['sign'],
                    'signGlyph': asc_sign['glyph'],
                    'degree': round(asc_sign['degree'], 2),
                }
                mc_data = {
                    'lon': round(mc_lon, 4),
                    'sign': mc_sign['sign'],
                    'signGlyph': mc_sign['glyph'],
                    'degree': round(mc_sign['degree'], 2),
                }

                # House cusps list (1-indexed, cusps[0] unused)
                house_cusps = [cusps[i] for i in range(1, 13)]

                houses_data = []
                for i, cusp_lon in enumerate(house_cusps):
                    cusp_sign = lon_to_sign(cusp_lon)
                    houses_data.append({
                        'house': i + 1,
                        'lon': round(cusp_lon, 4),
                        'sign': cusp_sign['sign'],
                        'signGlyph': cusp_sign['glyph'],
                        'degree': round(cusp_sign['degree'], 2),
                    })

                # Assign house numbers to each planet
                for p in planets_result:
                    p['house'] = get_house_of(p['lon'], house_cusps)

                # Add ASC and MC to planet list for display
                planets_result.append({
                    'key': 'asc',
                    'name': 'Ascendant',
                    'glyph': 'AC',
                    'color': '#e8c96d',
                    'lon': round(asc_lon, 4),
                    'sign': asc_sign['sign'],
                    'signGlyph': asc_sign['glyph'],
                    'degree': round(asc_sign['degree'], 2),
                    'element': get_element(asc_sign['sign']),
                    'modality': get_modality(asc_sign['sign']),
                    'retrograde': False,
                    'house': 1,
                })
                planets_result.append({
                    'key': 'mc',
                    'name': 'Midheaven',
                    'glyph': 'MC',
                    'color': '#c9a84c',
                    'lon': round(mc_lon, 4),
                    'sign': mc_sign['sign'],
                    'signGlyph': mc_sign['glyph'],
                    'degree': round(mc_sign['degree'], 2),
                    'element': get_element(mc_sign['sign']),
                    'modality': get_modality(mc_sign['sign']),
                    'retrograde': False,
                    'house': 10,
                })

            except Exception as e:
                has_time = False  # Fall back to no-time mode

        # ── Soul profile ──
        dominant_element = max(el_counts, key=el_counts.get)
        sun_planet = next((p for p in planets_result if p['key'] == 'sun'), None)
        moon_planet = next((p for p in planets_result if p['key'] == 'moon'), None)
        venus_planet = next((p for p in planets_result if p['key'] == 'venus'), None)
        mars_planet = next((p for p in planets_result if p['key'] == 'mars'), None)
        nn_planet = next((p for p in planets_result if p['key'] == 'northNode'), None)
        sn_planet = next((p for p in planets_result if p['key'] == 'southNode'), None)

        nn_sign = nn_planet['sign'] if nn_planet else 'Aries'
        sn_sign = sn_planet['sign'] if sn_planet else 'Libra'
        nn_destiny, sn_past = NODE_MEANINGS.get(nn_sign, ('Your destiny awaits.', 'Your karmic past.'))

        soul_profile = {
            'dominantElement': dominant_element,
            'elementCounts': el_counts,
            'summary': SOUL_SUMMARIES.get(dominant_element, ''),
            'sunSign': sun_planet['sign'] if sun_planet else '',
            'moonSign': moon_planet['sign'] if moon_planet else '',
            'ascSign': asc_data['sign'] if asc_data else None,
            'venusSign': venus_planet['sign'] if venus_planet else '',
            'marsSign': mars_planet['sign'] if mars_planet else '',
            'northNodeSign': nn_sign,
            'southNodeSign': sn_sign,
            'northNodeDestiny': nn_destiny,
            'southNodePast': sn_past,
        }

        # ── Houses of love ──
        houses_of_love = None
        if has_time and houses_data:
            h5 = houses_data[4]  # index 4 = house 5
            h7 = houses_data[6]  # index 6 = house 7
            h11 = houses_data[10]  # index 10 = house 11
            houses_of_love = {
                'h5': {'sign': h5['sign'], 'glyph': h5['signGlyph'], 'degree': h5['degree'],
                        'meaning': 'Romance, flirtation, and the early magic of love.'},
                'h7': {'sign': h7['sign'], 'glyph': h7['signGlyph'], 'degree': h7['degree'],
                        'meaning': 'Committed partnership and what you seek in a long-term union.'},
                'h11': {'sign': h11['sign'], 'glyph': h11['signGlyph'], 'degree': h11['degree'],
                         'meaning': 'Friendship, shared vision, and communities where love finds you.'},
            }

        return jsonify({
            'success': True,
            'name': name,
            'birthData': {
                'year': year, 'month': month, 'day': day,
                'hour': hour, 'minute': minute,
                'lat': lat, 'lon': lon,
                'utcOffset': utc_offset,
                'hasTime': has_time,
                'julianDay': round(jd_ut, 6),
            },
            'planets': planets_result,
            'houses': houses_data,
            'asc': asc_data,
            'mc': mc_data,
            'soulProfile': soul_profile,
            'housesOfLove': houses_of_love,
        })

    except KeyError as e:
        return jsonify({'error': f'Missing required field: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/geocode', methods=['GET'])
def geocode():
    """
    Proxy geocoding via Nominatim (keeps API calls server-side).
    ?q=Barranquilla+Colombia
    """
    import urllib.request
    import urllib.parse
    import json

    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=6&addressdetails=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Destined-App/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
