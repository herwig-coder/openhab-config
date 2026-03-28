"""
Custom ÖBB (Austrian Federal Railways) profile for pyhafas
"""

import pytz
from pyhafas.profile.base import BaseProfile


class OEBBProfile(BaseProfile):
    """
    ÖBB (Österreichische Bundesbahnen) HAFAS profile
    """
    baseUrl = "https://fahrplan.oebb.at/bin/mgate.exe"
    defaultUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    salt = '5DBkaU5t'
    addChecksum = True

    locale = 'de-AT'
    timezone = pytz.timezone('Europe/Vienna')

    requestBody = {
        'lang': 'deu',
        'client': {
            'id': 'OEBB',
            'v': '6140000',
            'type': 'AND',
            'name': 'oebbPROD-AND'
        },
        'ext': 'OEBB.1',
        'ver': '1.57',
        'auth': {
            'type': 'AID',
            'aid': 'OWDL4fE4ixNiPBBm'
        }
    }

    availableProducts = {
        'long_distance_express': [1],  # RJ/RJX
        'long_distance': [2],  # EC/IC
        'regional_express': [4],  # REX
        'regional': [8],  # R
        'suburban': [16],  # S
        'bus': [32],  # BUS
        'ferry': [64],  # F
        'subway': [128],  # U
        'tram': [256],  # Tram
        'taxi': [512]  # Taxi
    }

    defaultProducts = [
        'long_distance_express',
        'long_distance',
        'regional_express',
        'regional',
        'suburban',
        'bus',
        'ferry',
        'subway',
        'tram',
        'taxi'
    ]
