# Path of Moodle's REST web service entry point, relative to the site base URL. Fixed by
# Moodle itself, not site-configurable.
MOODLE_WS_ENDPOINT = "webservice/rest/server.php"

# Moodle's error code for a call the token's user is not allowed to make.
MOODLE_ACCESS_EXCEPTION_CODE = "accessexception"

# Moodle error codes reported as a 401, because the token is rejected rather than the request.
# accessexception is handled by its own branch first, to carry the hint below.
MOODLE_AUTH_ERROR_CODES = frozenset({"invalidtoken", MOODLE_ACCESS_EXCEPTION_CODE})

# Appended to Moodle's own "Access control exception" wording, which names no cause.
MOODLE_ACCESS_EXCEPTION_HINT = (
    "This usually means the token's user has not been authorised on the restricted "
    "'Sparkth publishing' web service in Moodle's admin UI, rather than that the token is invalid."
)

# Status reported to a tool's caller when a typed accessor (call_dict/call_list) got
# a response body of the wrong shape from Moodle.
MOODLE_MALFORMED_RESPONSE_STATUS_CODE = 502
