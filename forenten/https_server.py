import http.server
import ssl
import os

# Change to the directory with your files
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Set up the server
server_address = ('0.0.0.0', 3000)
httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)

# Add SSL
httpd.socket = ssl.wrap_socket(
    httpd.socket,
    server_side=True,
    certfile='cert.pem',
    keyfile='key.pem',
    ssl_version=ssl.PROTOCOL_TLS
)

print(f"Serving HTTPS on port {server_address[1]}...")
httpd.serve_forever()