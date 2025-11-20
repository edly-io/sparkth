class AuthenticationError(Exception):
    def __init__(self, message="Invalid API URL or token"):
        self.message = message
        super().__init__(self.message)


class LMSError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
