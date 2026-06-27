#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PC側バスデータプッシュデーモン - PC でデータ取得して Kobo に SCP 転送"""
import json
import os
import sys
import time
import tempfile
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from bus_fetch import load_config, build_url, fetch_page, html_to_text, parse_bus_entries, get_server_time
from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, '.env'))

REMOTE_DIR  = '/home/marek/python_apps/bus_statedtl'
REMOTE_JSON = f'{REMOTE_DIR}/buses.json'
PUSH_INTERVAL = 60

SSH_OPTS = [
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    '-o', 'HostKeyAlgorithms=+ssh-rsa,ssh-dss',
    '-o', 'KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1',
    '-o', 'PubkeyAuthentication=no',
]


def make_env(password):
    askpass = os.path.join(tempfile.gettempdir(), 'kobo_askpass.sh')
    with open(askpass, 'w') as f:
        f.write('#!/bin/sh\necho ' + password.replace("'", "'\\''") + '\n')
    os.chmod(askpass, 0o700)
    env = os.environ.copy()
    env['DISPLAY'] = ''
    env['SSH_ASKPASS'] = askpass
    env['SSH_ASKPASS_REQUIRE'] = 'force'
    return env


def fetch_all(pages):
    now = get_server_time()
    data = {'server_time': now.strftime('%Y-%m-%d %H:%M'), 'pages': []}
    for page in pages:
        page_data = {'page': page['page'], 'routes': []}
        for route in page['routes']:
            try:
                url = build_url(route['url'], now)
                html = fetch_page(url)
                text = html_to_text(html)
                entries = parse_bus_entries(text)
            except Exception as e:
                print(f'  エラー [{route["label"]}]: {e}')
                entries = []
            page_data['routes'].append({'label': route['label'], 'entries': entries})
        data['pages'].append(page_data)
    return data


def push_json(data, host_str, env):
    tmp = tempfile.mktemp(suffix='.json')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    result = subprocess.run(
        ['setsid', '-w', 'scp', '-O'] + SSH_OPTS + [tmp, f'{host_str}:{REMOTE_JSON}'],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    os.unlink(tmp)
    if result.returncode != 0:
        err = result.stderr.decode('utf-8', errors='replace').strip()
        print(f'  SCP失敗: {err}')
    return result.returncode == 0


def main():
    host     = os.environ.get('KOBO_IP')
    user     = os.environ.get('KOBO_ACCONT')
    password = os.environ.get('KOBO_ACCONT_PASSWORD')
    if not all([host, user, password]):
        print('ERROR: .env に KOBO_IP / KOBO_ACCONT / KOBO_ACCONT_PASSWORD が必要です')
        sys.exit(1)

    host_str = f'{user}@{host}'
    env      = make_env(password)
    pages    = load_config(os.path.join(BASE_DIR, 'config.yaml'))

    print(f'プッシュデーモン起動 → {host_str}:{REMOTE_JSON}  ({PUSH_INTERVAL}秒間隔)')
    while True:
        t = datetime.now().strftime('%H:%M:%S')
        try:
            print(f'[{t}] 取得中...')
            data = fetch_all(pages)
            ok = push_json(data, host_str, env)
            print(f'[{t}] {"転送完了" if ok else "転送失敗（Koboオフライン？）"}')
        except Exception as e:
            print(f'[{t}] エラー: {e}')
        time.sleep(PUSH_INTERVAL)


if __name__ == '__main__':
    main()
