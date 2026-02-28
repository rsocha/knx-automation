# Built-in logic blocks
from .ecowitt_ws90 import EcowittWS90
from .oauth2_tokenmanager import OAuth2TokenManager
from .epex_spot import EPEXSpotPrice
from .netatmo_homecoach import NetatmoHomecoach
from .fritzdect200 import FritzDect200
from .ical_termine import ICalTermine
from .timer import Timer
from .sonne_mond import SonneMond

EXTRA_BLOCKS = {
    'EcowittWS90': EcowittWS90,
    'OAuth2TokenManager': OAuth2TokenManager,
    'EPEXSpotPrice': EPEXSpotPrice,
    'NetatmoHomecoach': NetatmoHomecoach,
    'FritzDect200': FritzDect200,
    'ICalTermine': ICalTermine,
    'Timer': Timer,
    'SonneMond': SonneMond,
}
