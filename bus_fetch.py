#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""近鉄バス接近情報取得スクリプト（Kobo上で直接実行）"""
from __future__ import print_function
import sys
import ssl
import os
import re
import subprocess
from datetime import datetime, timedelta

# Python 2/3 両対応
try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode, quote, urlparse, parse_qs
    from html.parser import HTMLParser
    PY3 = True
except ImportError:
    from urllib2 import urlopen, Request
    from urllib import urlencode, quote
    from urlparse import urlparse, parse_qs
    from HTMLParser import HTMLParser
    PY3 = False


def load_config(config_path):
    """config.yaml を読み込んでページリストを返す（PyYAML 不要）
    返り値: [{'page': str, 'routes': [{'label': str, 'url': str}]}]
    """
    pages = []
    cur_page = None
    cur_route = None

    with open(config_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip()
            if not line.lstrip() or line.lstrip().startswith('#'):
                continue

            m = re.match(r'\s+-\s+page:\s+"(.+)"', line)
            if m:
                if cur_route is not None and cur_page is not None:
                    cur_page['routes'].append(cur_route)
                    cur_route = None
                cur_page = {'page': m.group(1), 'routes': []}
                pages.append(cur_page)
                continue

            m = re.match(r'\s+-\s+label:\s+"(.+)"', line)
            if m and cur_page is not None:
                if cur_route is not None:
                    cur_page['routes'].append(cur_route)
                cur_route = {'label': m.group(1)}
                continue

            m = re.match(r'\s+url:\s+"(.+)"', line)
            if m and cur_route is not None:
                cur_route['url'] = m.group(1)

    if cur_route is not None and cur_page is not None:
        cur_page['routes'].append(cur_route)

    return pages


def _make_ssl_ctx():
    """TLS 検証をスキップした SSL コンテキストを返す"""
    try:
        return ssl._create_unverified_context()
    except AttributeError:
        ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def get_server_time():
    """
    バスサイトの HTTP レスポンス Date ヘッダーからサーバー時刻（JST）を取得する。
    Kobo のシステムクロックが正確でなくても正しい時刻を返す。
    失敗時は datetime.now() にフォールバック。
    """
    from email.utils import parsedate
    try:
        ctx = _make_ssl_ctx()
        req = Request(
            'https://kintetsu-bus.jorudan.biz/',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        req.get_method = lambda: 'HEAD'
        try:
            resp = urlopen(req, context=ctx, timeout=10)
        except TypeError:
            import urllib.request as _ur
            opener = _ur.build_opener(_ur.HTTPSHandler(context=ctx))
            resp = opener.open(req, timeout=10)
        date_str = resp.headers.get('Date', '')
        if date_str:
            t = parsedate(date_str)
            if t:
                dt_utc = datetime(*t[:6])
                return dt_utc + timedelta(hours=9)  # UTC → JST
    except Exception:
        pass
    return datetime.now()


def build_url(url_template, now=None):
    """URL の dt プレースホルダーを指定時刻（省略時は現在時刻）で置換する"""
    if now is None:
        now = datetime.now()
    return url_template.replace('YYYYMMDDHHMM', now.strftime('%Y%m%d%H%M'))


def fetch_page(url):
    """TLS 検証をスキップしてページを取得する"""
    ctx = _make_ssl_ctx()
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) Gecko/20100101 Firefox/20.0',
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Accept-Language': 'ja,en;q=0.5',
    }
    req = Request(url, headers=headers)
    try:
        resp = urlopen(req, context=ctx, timeout=15)
    except TypeError:
        # Python 3.4.2 は urlopen(context=...) 未対応
        import urllib.request as _ur
        opener = _ur.build_opener(_ur.HTTPSHandler(context=ctx))
        resp = opener.open(req, timeout=15)
    raw = resp.read()
    charset = 'utf-8'
    # rb'' はRaw文字列なので \' がエスケープされない → 先頭をASCII文字列に変換してから検索
    header_text = raw[:2000].decode('ascii', errors='replace')
    m = re.search(r'charset=["\']?([\w-]+)', header_text)
    if m:
        charset = m.group(1)
    try:
        return raw.decode(charset, errors='replace')
    except (LookupError, UnicodeDecodeError):
        return raw.decode('utf-8', errors='replace')


def html_to_text(html):
    """HTML タグを除去してテキストを取得する"""
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    return re.sub(r'\s+', ' ', text).strip()


def parse_bus_entries(text):
    """
    テキストから個別バス接近情報を抽出する。
    対象パターン: "N | HH:MM 到着予定 STATUS ... 定刻：HH:MM (遅延情報)"
    """
    entries = []
    # "1 | 09:12 到着予定 まもなく到着 ... 定刻： 09:09 (約3分遅れ)" のパターン
    pattern = re.compile(
        r'(\d+)\s*\|\s*(\d{1,2}:\d{2})\s*到着予定\s*'
        r'(まもなく到着|約\d+分後[にへ]到着)'
        r'.*?定刻[：:]\s*(\d{1,2}:\d{2})\s*\(([^)]+)\)'
    )
    for m in pattern.finditer(text):
        entries.append({
            'num': m.group(1),
            'arrival': m.group(2),
            'status': m.group(3),
            'scheduled': m.group(4),
            'delay': m.group(5),
        })
    return entries


def generate_html(route_results, refresh_seconds=None, server_time=None,
                  page_labels=None, current_page=0):
    """Kobo グレースケール向けカード形式 HTML を生成する"""
    now_str = (server_time or datetime.now()).strftime('%Y-%m-%d %H:%M')
    parts = [
        '<!DOCTYPE html>',
        '<html><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width">',
    ]
    if refresh_seconds:
        parts.append('<meta http-equiv="refresh" content="%d">' % refresh_seconds)
    parts += [
        '<style>',
        # ベース
        'body{font-family:sans-serif;margin:4px;padding:0;background:#fff;color:#000}',
        # ヘッダー行（タイトル＋ナビを横並び）
        '.hdr{overflow:hidden;border-bottom:3px solid #000;margin-bottom:4px;padding-bottom:4px}',
        '.hdr h1{float:left;font-size:16px;font-weight:bold;margin:0;padding:0}',
        # ページ切り替えボタン
        '.nav{float:right}',
        '.nbtn{display:inline-block;padding:3px 10px;border:2px solid #000;'
        'margin-left:4px;text-decoration:none;color:#000;font-weight:bold;font-size:13px}',
        '.nbtn.act{background:#000;color:#fff}',
        # 取得時刻
        '.ts{font-size:11px;margin:0 0 6px;clear:both}',
        # 横並び2カラム（float ベース・旧ブラウザ互換）
        '.cols{overflow:hidden}',
        '.col{float:left;width:48%}',
        '.col+.col{margin-left:4%}',
        # 路線ヘッダー
        'h2{font-size:15px;font-weight:bold;margin:0 0 4px;padding:4px 6px;'
        'border-left:6px solid #000;background:#ccc}',
        # バスカード
        '.card{border:2px solid #000;margin:4px 0;padding:6px 8px}',
        '.card.alt{background:#ebebeb}',
        '.row1{margin-bottom:4px}',
        '.num{font-size:14px;font-weight:bold}',
        '.arr{font-size:22px;font-weight:bold;margin:0 8px}',
        '.sta{font-size:16px;font-weight:bold}',
        '.row2{font-size:12px;padding-left:6px}',
        '</style>',
        '</head><body>',
        '<div class="hdr">',
        '<h1>近鉄バス接近情報</h1>',
    ]

    # ページ切り替えボタン
    if page_labels and len(page_labels) > 1:
        parts.append('<div class="nav">')
        for i, label in enumerate(page_labels):
            act = ' act' if i == current_page else ''
            parts.append('<a href="/?page=%d" class="nbtn%s">%s</a>' % (i, act, label))
        parts.append('</div>')

    parts += [
        '</div>',
        '<p class="ts">取得: %s</p>' % now_str,
    ]

    parts.append('<div class="cols">')
    for label, entries in route_results:
        parts.append('<div class="col">')
        parts.append('<h2>%s</h2>' % label)
        if entries:
            for i, e in enumerate(entries):
                alt = ' alt' if i % 2 == 1 else ''
                delay_text = ('! ' + e['delay']) if '遅れ' in e['delay'] else e['delay']
                parts.append(
                    '<div class="card%s">'
                    '<div class="row1">'
                    '<span class="num">%s.</span>'
                    '<span class="arr">%s</span>'
                    '<span class="sta">%s</span>'
                    '</div>'
                    '<div class="row2">定刻&nbsp;%s&nbsp;(%s)</div>'
                    '</div>' % (
                        alt,
                        e['num'], e['arrival'], e['status'],
                        e['scheduled'], delay_text,
                    )
                )
        else:
            parts.append('<p style="margin:4px">（情報なし）</p>')
        parts.append('</div>')
    parts.append('</div>')

    parts.append('</body></html>')
    return '\n'.join(parts)


def open_browser(html_path):
    """HTML ファイルをブラウザで開く"""
    for cmd in ('xdg-open', 'firefox', 'midori', 'dillo'):
        try:
            subprocess.Popen([cmd, html_path])
            return
        except OSError:
            continue
    print('ブラウザが見つかりません: ' + html_path)


def main(config_path):
    pages = load_config(config_path)
    if not pages:
        print('設定ファイルにページが見つかりません: ' + config_path)
        sys.exit(1)

    # standalone モードは最初のページのみ表示
    page = pages[0]
    now = get_server_time()
    route_results = []
    for route in page['routes']:
        label = route['label']
        url = build_url(route['url'], now)
        print('取得中: ' + label)
        try:
            html = fetch_page(url)
            text = html_to_text(html)
            entries = parse_bus_entries(text)
            route_results.append((label, entries))
            print('  → %d 件' % len(entries))
        except Exception as e:
            print('  エラー: ' + str(e))
            route_results.append((label, []))

    page_labels = [p['page'] for p in pages]
    out_html = generate_html(route_results, server_time=now,
                             page_labels=page_labels, current_page=0)
    out_path = '/tmp/buses.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out_html)
    print('HTML 出力: ' + out_path)
    open_browser(out_path)


if __name__ == '__main__':
    config = sys.argv[1] if len(sys.argv) > 1 else '/home/marek/python_apps/bus_statedtl/config.yaml'
    main(config)
