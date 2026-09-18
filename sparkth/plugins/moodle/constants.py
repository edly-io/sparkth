# Path of Moodle's REST web service entry point, relative to the site base URL. Fixed by
# Moodle itself, not site-configurable.
MOODLE_WS_ENDPOINT = "webservice/rest/server.php"

# Moodle error codes that mean the token itself is rejected, rather than the request.
MOODLE_AUTH_ERROR_CODES = frozenset({"invalidtoken", "accessexception"})
