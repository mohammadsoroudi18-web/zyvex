import http.server
import socketserver
import subprocess
import html

PORT = 3000


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        result = subprocess.run(["python3", "main"], capture_output=True, text=True)
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"

        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hello</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f172a;
    color: #f8fafc;
  }}
  h1 {{ font-size: 3rem; font-weight: 700; }}
</style>
</head>
<body>
  <h1>{html.escape(output)}</h1>
</body>
</html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving on port {PORT}")
        httpd.serve_forever()
