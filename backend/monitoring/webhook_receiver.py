from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class AlertReceiver(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)

        alert_data = json.loads(body)

        print("\n======= GRAFANA ALERT =========")
        print(json.dumps(alert_data, indent=4))

        print("================\n")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alert received successfully")

    def log_message(self, format, *args):
        return


server = HTTPServer(("0.0.0.0", 8001), AlertReceiver)

print("Grafana webhook receiver running on port 8001...")

server.serve_forever()