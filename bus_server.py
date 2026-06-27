#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""近鉄バス接近情報 HTTP サーバー（Kobo上で直接実行）"""
import sys
import os

INSTALL_DIR = '/home/marek/python_apps/bus_statedtl'
CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else INSTALL_DIR + '/config.yaml'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
REFRESH_SECONDS = 60

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or INSTALL_DIR)
from bus_fetch import load_config, build_url, fetch_page, html_to_text, parse_bus_entries, generate_html, get_server_time

from http.server import HTTPServer, BaseHTTPRequestHandler

pages = load_config(CONFIG_PATH)
page_labels = [p['page'] for p in pages]


class BusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # パスとクエリを分離
        if '?' in self.path:
            path, query = self.path.split('?', 1)
        else:
            path, query = self.path, ''

        if path not in ('/', '/buses'):
            self.send_response(404)
            self.end_headers()
            return

        # ?page=N を解析
        page_idx = 0
        for part in query.split('&'):
            if part.startswith('page='):
                try:
                    page_idx = int(part[5:])
                except ValueError:
                    pass
        page_idx = max(0, min(page_idx, len(pages) - 1))

        now = get_server_time()
        route_results = []
        for route in pages[page_idx]['routes']:
            label = route['label']
            url = build_url(route['url'], now)
            try:
                html = fetch_page(url)
                text = html_to_text(html)
                entries = parse_bus_entries(text)
                route_results.append((label, entries))
            except Exception:
                route_results.append((label, []))

        body = generate_html(
            route_results,
            refresh_seconds=REFRESH_SECONDS,
            server_time=now,
            page_labels=page_labels,
            current_page=page_idx,
        ).encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    import io, threading, webbrowser
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    server = HTTPServer(('', PORT), BusHandler)
    url = 'http://localhost:{}/'.format(PORT)
    sys.stdout.write('server started: {}\n'.format(url))
    sys.stdout.flush()
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    server.serve_forever()
