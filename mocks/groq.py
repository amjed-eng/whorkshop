class Groq:
    def __init__(self, api_key=None):
        self.api_key = api_key
        
        class Chat:
            class Completions:
                def create(self, **kwargs):
                    pass
            self.completions = Completions()
            
        self.chat = Chat()
