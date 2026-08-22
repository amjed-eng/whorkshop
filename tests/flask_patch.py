import sys

class Response:
    def __init__(self, response, status=200, mimetype=None):
        self.status_code = status
        self.mimetype = mimetype
        
        if isinstance(response, str):
            self.data = response.encode('utf-8')
            self.response = iter([self.data])
        elif hasattr(response, '__iter__') and not isinstance(response, bytes):
            # Do NOT consume generators, just store the iterable
            self.response = response
            self.data = b'' # data is empty for streams
        elif isinstance(response, bytes):
            self.data = response
            self.response = iter([self.data])
        else:
            self.data = b''
            self.response = iter([])
        
    def get_json(self):
        import json
        return json.loads(self.data.decode('utf-8'))

def jsonify(data):
    import json
    return Response(json.dumps(data), mimetype='application/json')

class Request:
    def __init__(self):
        self.is_json = False
        self._json = None
        self.data = None
        
    def get_json(self):
        return self._json

request = Request()

class TestClient:
    def __init__(self, app):
        self.app = app
        
    def get(self, path):
        route = self.app.routes.get((path, 'GET'))
        if not route:
            return Response("Not Found", status=404)
            
        res = route()
        if isinstance(res, tuple):
            resp, status = res
            resp.status_code = status
            return resp
        return res
        
    def post(self, path, json=None, data=None):
        route = self.app.routes.get((path, 'POST'))
        if not route:
            return Response("Not Found", status=404)
            
        global request
        request.is_json = False
        request._json = None
        request.data = None
        
        if json is not None:
            request.is_json = True
            request._json = json
        elif data is not None:
            request.data = data
            
        res = route()
        if isinstance(res, tuple):
            resp, status = res
            resp.status_code = status
            return resp
        return res

class Flask:
    def __init__(self, name):
        self.name = name
        self.routes = {}
        self.config = {}
        
        class Logger:
            def error(self, msg): pass
            def exception(self, msg): pass
        self.logger = Logger()
        
    def route(self, path, methods=None):
        if methods is None: methods = ['GET']
        def decorator(f):
            for m in methods:
                self.routes[(path, m)] = f
            return f
        return decorator
        
    def test_client(self):
        return TestClient(self)

class MockFlaskModule:
    Flask = Flask
    Response = Response
    request = request
    
    @staticmethod
    def jsonify(data):
        return jsonify(data)

    @staticmethod
    def render_template(template_name, **kwargs):
        # Return a mock HTML response
        html = f"<html><body>Mock rendered template: {template_name} Intruder Invisible</body></html>"
        return Response(html, mimetype='text/html')

sys.modules['flask'] = MockFlaskModule()
