from enum import StrEnum


class Auth(StrEnum):
    JWT = "Jwt"
    BEARER = "Bearer"


class Method(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
