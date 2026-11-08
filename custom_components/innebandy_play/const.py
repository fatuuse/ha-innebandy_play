"""Konstanter för Innebandy Play."""

DOMAIN = "innebandy_play"

CONF_COMPANY = "company"
CONF_TEAM_NAME = "team_name"
CONF_QUERY = "query"
CONF_GROUP_ID = "standings_group_id"

API_BASE = "https://solidsport.com/api/play_v1"
STANDINGS_URL = "https://api.solidsport.com/v1/standings/getFromEventReferenceV2"
SQUAD_URL = "https://api.solidsport.com/v1/standings/team/players"
EXTERNAL_SYSTEM = "ibis_floorball"
ROOT_CHANNEL = "innebandyplay"

GAMES_PER_PAGE = 50
REPLAYS_PER_PAGE = 50

# Hämtningsfönster kring en match, i sekunder
PRE_GAME_WINDOW = 10 * 60
POST_GAME_WINDOW = 15 * 60
DEFAULT_MATCH_LENGTH = 3 * 60 * 60

# Schema för matchlista och repriser: lördag och söndag kl. 08 (måndag = 0)
SCHEDULE_WEEKDAYS = (5, 6)
SCHEDULE_HOUR = 8

# Uppdateringsintervall, i sekunder
INTERVAL_LIVE = 30
INTERVAL_IDLE = 900

# Hur ofta respektive källa hämtas om
STANDINGS_REFRESH = 900
SQUAD_REFRESH = 6 * 60 * 60
METADATA_REFRESH = 24 * 60 * 60

MAX_BACKFILL_PER_CYCLE = 10
CACHE_LIMIT = 80
TIMELINE_LIMIT = 30
UPCOMING_LIMIT = 6
RESULTS_LIMIT = 10
SCORERS_LIMIT = 15
