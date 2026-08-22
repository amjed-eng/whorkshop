import sys

class Groq:
    def __init__(self, api_key=None):
        self.api_key = api_key
        
class MockGroqModule:
    Groq = Groq

sys.modules['groq'] = MockGroqModule()
