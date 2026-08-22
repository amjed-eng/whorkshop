import json as _json

class Response:
    def __init__(self, response, status=200, mimetype=None):
        if isinstance(response, str):
            self.data = response.encode('utf-8')
        elif hasattr(response, '__iter__'):
            self.data = b''.join([r.encode('utf-8') if isinstance(r, str) else r for r in response])
        else:
            self.data = b''
        self.status_code = status
        self.mimetype = mimetype
        
    def get_json(self):
        return _json.loads(self.data.decode('utf-8'))

def jsonify(data):
    return Response(_json.dumps(data), mimetype='application/json')

class Request:
    def __init__(self):
        self.is_json = False
        self._json = None
        self.data = None
        
    def get_json(self):
        return self._json

# Globals for requests
request = Request()

class TestClient:
    def __init__(self, app):
        self.app = app
        
    def get(self, path):
        route = self.app.routes.get((path, 'GET'))
        if not route:
            return Response("Not Found", status=404)
        return route()
        
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
        # Allow returning tuple (response, status)
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
            def error(self, msg):
                pass
            def exception(self, msg):
                pass
        self.logger = Logger()
        
    def route(self, path, methods=None):
        if methods is None:
            methods = ['GET']
        def decorator(f):
            for m in methods:
                self.routes[(path, m)] = f
            return f
        return decorator
        
    def test_client(self):
        return TestClient(self)
