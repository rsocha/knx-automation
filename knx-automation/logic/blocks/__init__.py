# Built-in logic blocks
from .ecowitt_ws90 import EcowittWS90
from .oauth2_tokenmanager import OAuth2TokenManager
from .epex_spot import EPEXSpotPrice
from .netatmo_homecoach import NetatmoHomecoach

EXTRA_BLOCKS = {
    'EcowittWS90': EcowittWS90,
    'OAuth2TokenManager': OAuth2TokenManager,
    'EPEXSpotPrice': EPEXSpotPrice,
    'NetatmoHomecoach': NetatmoHomecoach,
}
