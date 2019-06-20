import os
import mimetypes
from datetime import datetime
from owrx.websocket import WebSocketConnection
from owrx.config import PropertyManager
from owrx.source import ClientRegistry
from owrx.connection import WebSocketMessageHandler
from owrx.version import openwebrx_version

import logging
logger = logging.getLogger(__name__)

class Controller(object):
    def __init__(self, handler, matches):
        self.handler = handler
        self.matches = matches
    def send_response(self, content, code = 200, content_type = "text/html", last_modified: datetime = None, max_age = None):
        self.handler.send_response(code)
        if content_type is not None:
            self.handler.send_header("Content-Type", content_type)
        if last_modified is not None:
            self.handler.send_header("Last-Modified", last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT"))
        if max_age is not None:
            self.handler.send_header("Cache-Control", "max-age: {0}".format(max_age))
        self.handler.end_headers()
        if (type(content) == str):
            content = content.encode()
        self.handler.wfile.write(content)
    def render_template(self, template, **variables):
        f = open('htdocs/' + template)
        data = f.read()
        f.close()

        self.send_response(data)

class StatusController(Controller):
    def handle_request(self):
        pm = PropertyManager.getSharedInstance()
        # TODO keys that have been left out since they are no longer simple strings: sdr_hw, bands, antenna
        vars = {
            "status": "active",
            "name": pm["receiver_name"],
            "op_email": pm["receiver_admin"],
            "users": ClientRegistry.getSharedInstance().clientCount(),
            "users_max": pm["max_clients"],
            "gps": pm["receiver_gps"],
            "asl": pm["receiver_asl"],
            "loc": pm["receiver_location"],
            "sw_version": openwebrx_version,
            "avatar_ctime": os.path.getctime("htdocs/gfx/openwebrx-avatar.png")
        }
        self.send_response("\n".join(["{key}={value}".format(key = key, value = value) for key, value in vars.items()]))

class AssetsController(Controller):
    def serve_file(self, file, content_type = None):
        try:
            modified = datetime.fromtimestamp(os.path.getmtime('htdocs/' + file))

            if "If-Modified-Since" in self.handler.headers:
                client_modified = datetime.strptime(self.handler.headers["If-Modified-Since"], "%a, %d %b %Y %H:%M:%S %Z")
                if modified <= client_modified:
                    self.send_response("", code = 304)
                    return

            f = open('htdocs/' + file, 'rb')
            data = f.read()
            f.close()

            if content_type is None:
                (content_type, encoding) = mimetypes.MimeTypes().guess_type(file)
            self.send_response(data, content_type = content_type, last_modified = modified, max_age = 3600)
        except FileNotFoundError:
            self.send_response("file not found", code = 404)
    def handle_request(self):
        filename = self.matches.group(1)
        self.serve_file(filename)

class IndexController(AssetsController):
    def handle_request(self):
        self.serve_file("index.html", content_type = "text/html")

class WebSocketController(Controller):
    def handle_request(self):
        conn = WebSocketConnection(self.handler, WebSocketMessageHandler())
        conn.send("CLIENT DE SERVER openwebrx.py")
        # enter read loop
        conn.read_loop()
