#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""近鉄バス接近情報 Qt アプリ（Kobo 上で PySide/Qt4 で直接実行）"""
from __future__ import print_function
import sys
import os
import re
from datetime import datetime, timedelta

INSTALL_DIR = '/home/marek/python_apps/bus_statedtl'
CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else INSTALL_DIR + '/config.yaml'
REFRESH_SECS = 60
TICK_SECS = 30   # カウントダウン更新間隔

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or INSTALL_DIR)
from bus_fetch import (
    load_config, build_url, fetch_page, html_to_text,
    parse_bus_entries, get_server_time,
)

from PySide.QtCore import Qt, QTimer, QThread, Signal
from PySide.QtGui import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QFont, QSizePolicy,
)


def _get_mem_info():
    """プロセスと空きメモリを /proc から取得する（追加パッケージ不要）"""
    try:
        with open('/proc/self/status') as f:
            proc = f.read()
        with open('/proc/meminfo') as f:
            minfo = f.read()
        rss = re.search(r'VmRSS:\s+(\d+)', proc)
        avail = re.search(r'MemAvailable:\s+(\d+)', minfo) or re.search(r'MemFree:\s+(\d+)', minfo)
        total = re.search(r'MemTotal:\s+(\d+)', minfo)
        parts = []
        if rss:
            parts.append('App:%dMB' % (int(rss.group(1)) // 1024))
        if avail and total:
            parts.append('Free:%d/%dMB' % (int(avail.group(1)) // 1024, int(total.group(1)) // 1024))
        return ' | '.join(parts)
    except Exception:
        return ''


def _remaining_secs(arrival_str, now):
    try:
        h, m = map(int, arrival_str.split(':'))
        arrival = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if arrival < now:
            arrival += timedelta(days=1)
        return max(0, int((arrival - now).total_seconds()))
    except Exception:
        return None


class FetchThread(QThread):
    """バックグラウンドでバスデータを取得するスレッド"""
    data_ready = Signal(object, list)   # (server_time: datetime, route_results: list)

    def __init__(self, pages, page_idx):
        super(FetchThread, self).__init__()
        self._pages = pages
        self._idx = page_idx

    def run(self):
        now = get_server_time()
        results = []
        for route in self._pages[self._idx]['routes']:
            try:
                url = build_url(route['url'], now)
                html = fetch_page(url)
                text = html_to_text(html)
                entries = parse_bus_entries(text)
            except Exception:
                entries = []
            results.append((route['label'], entries))
        self.data_ready.emit(now, results)


class BusCard(QFrame):
    """1本分の接近情報カード"""

    def __init__(self, entry, server_time, parent=None):
        super(BusCard, self).__init__(parent)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setLineWidth(2)
        self._secs = _remaining_secs(entry['arrival'], server_time)
        self._urgency = -1   # 前回の緊急度レベル（変化時のみ再描画）

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # 番号・到着時刻・状態
        row1 = QHBoxLayout()
        lbl_num = QLabel(entry['num'] + '.')
        lbl_num.setFont(QFont('sans-serif', 11, QFont.Bold))
        lbl_arr = QLabel(entry['arrival'])
        lbl_arr.setFont(QFont('sans-serif', 20, QFont.Bold))
        lbl_sta = QLabel(entry['status'])
        lbl_sta.setFont(QFont('sans-serif', 14, QFont.Bold))
        row1.addWidget(lbl_num)
        row1.addWidget(lbl_arr)
        row1.addWidget(lbl_sta)
        row1.addStretch()
        layout.addLayout(row1)

        # カウントダウン
        self._lbl_cd = QLabel('')
        self._lbl_cd.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_cd)

        # 定刻・遅延
        delay = ('! ' + entry['delay']) if '遅れ' in entry['delay'] else entry['delay']
        lbl_detail = QLabel('定刻 %s (%s)' % (entry['scheduled'], delay))
        lbl_detail.setFont(QFont('sans-serif', 10))
        layout.addWidget(lbl_detail)

        self._update()

    def tick(self):
        if self._secs is not None and self._secs > 0:
            self._secs = max(0, self._secs - TICK_SECS)
        self._update()

    def _urgency_level(self, rem):
        if rem is None:  return -1
        if rem <= 0:     return 0
        if rem < 60:     return 1
        if rem < 120:    return 2
        if rem < 300:    return 3
        return 4

    def _update(self):
        rem = self._secs
        if rem is None:
            return
        m, s = divmod(max(0, rem), 60)

        # テキスト更新（軽量・毎ティック）
        if rem <= 0:
            self._lbl_cd.setText('到着')
        else:
            self._lbl_cd.setText('%d分%02d秒' % (m, s))

        # スタイル・フォント変更は緊急度が変わったときだけ（重い処理）
        level = self._urgency_level(rem)
        if level == self._urgency:
            return
        self._urgency = level

        if level == 0:
            self._lbl_cd.setFont(QFont('sans-serif', 28, QFont.Bold))
            self.setStyleSheet('QFrame{background:#000}QLabel{color:#fff}')
        elif level == 1:
            self._lbl_cd.setFont(QFont('sans-serif', 26, QFont.Bold))
            self.setStyleSheet('QFrame{background:#000}QLabel{color:#fff}')
        elif level == 2:
            self._lbl_cd.setFont(QFont('sans-serif', 22, QFont.Bold))
            self.setStyleSheet('QFrame{background:#444}QLabel{color:#fff}')
        elif level == 3:
            self._lbl_cd.setFont(QFont('sans-serif', 20, QFont.Bold))
            self.setStyleSheet('')
        else:
            self._lbl_cd.setFont(QFont('sans-serif', 18))
            self.setStyleSheet('')


class MainWindow(QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self._pages = load_config(CONFIG_PATH)
        self._page_idx = 0
        self._cards = []
        self._fetch_thread = None

        self._setup_ui()
        self._setup_timers()
        self._fetch()

    def _setup_ui(self):
        self.setWindowTitle('近鉄バス接近情報')
        self.showFullScreen()

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(34, 4, 4, 4)  # 左30px追加（画面見切れ対策）
        self._root.setSpacing(4)

        # ヘッダー（タイトル＋ページ切り替えボタン）
        hdr = QHBoxLayout()
        title = QLabel('近鉄バス接近情報')
        title.setFont(QFont('sans-serif', 14, QFont.Bold))
        hdr.addWidget(title)
        hdr.addStretch()

        self._nav_btns = []
        for i, p in enumerate(self._pages):
            btn = QPushButton(p['page'])
            btn.setFont(QFont('sans-serif', 11, QFont.Bold))
            btn.setMinimumSize(90, 40)   # タッチしやすいサイズ
            btn.clicked.connect(lambda checked=False, idx=i: self._switch_page(idx))
            hdr.addWidget(btn)
            self._nav_btns.append(btn)

        self._root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setLineWidth(3)
        self._root.addWidget(sep)

        info_row = QHBoxLayout()
        self._lbl_time = QLabel('取得中...')
        self._lbl_time.setFont(QFont('sans-serif', 10))
        self._lbl_mem = QLabel('')
        self._lbl_mem.setFont(QFont('sans-serif', 10))
        info_row.addWidget(self._lbl_time)
        info_row.addStretch()
        info_row.addWidget(self._lbl_mem)
        self._root.addLayout(info_row)

        # コンテンツエリア（路線カラムを横並び）
        self._content_widget = QWidget()
        self._content_layout = QHBoxLayout(self._content_widget)
        self._content_layout.setSpacing(8)
        self._root.addWidget(self._content_widget, 1)

        self._update_nav_style()

    def _setup_timers(self):
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(TICK_SECS * 1000)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._fetch)
        self._refresh_timer.start(REFRESH_SECS * 1000)

    def _switch_page(self, idx):
        self._page_idx = idx
        self._update_nav_style()
        self._fetch()

    def _update_nav_style(self):
        for i, btn in enumerate(self._nav_btns):
            if i == self._page_idx:
                btn.setStyleSheet(
                    'QPushButton{background:#000;color:#fff;'
                    'border:2px solid #000;padding:4px 8px}'
                )
            else:
                btn.setStyleSheet(
                    'QPushButton{background:#fff;color:#000;'
                    'border:2px solid #000;padding:4px 8px}'
                )

    def _fetch(self):
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        self._fetch_thread = FetchThread(self._pages, self._page_idx)
        self._fetch_thread.data_ready.connect(self._on_data)
        self._fetch_thread.start()

    def _on_data(self, now, route_results):
        self._lbl_time.setText('取得: ' + now.strftime('%Y-%m-%d %H:%M'))
        self._lbl_mem.setText(_get_mem_info())
        self._cards = []

        # コンテンツをクリア
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for label, entries in route_results:
            col_widget = QWidget()
            col = QVBoxLayout(col_widget)
            col.setSpacing(4)
            col.setContentsMargins(0, 0, 0, 0)

            lbl = QLabel(label)
            lbl.setFont(QFont('sans-serif', 13, QFont.Bold))
            lbl.setStyleSheet(
                'padding:4px 6px;background:#ccc;border-left:6px solid #000'
            )
            col.addWidget(lbl)

            if entries:
                for entry in entries:
                    card = BusCard(entry, now)
                    col.addWidget(card)
                    self._cards.append(card)
            else:
                no_info = QLabel('（情報なし）')
                no_info.setFont(QFont('sans-serif', 12))
                col.addWidget(no_info)

            col.addStretch()
            self._content_layout.addWidget(col_widget, 1)

    def _tick(self):
        for card in self._cards:
            card.tick()
        self._lbl_mem.setText(_get_mem_info())


def main():
    app = QApplication(sys.argv)
    app.setStyle('cleanlooks')
    win = MainWindow()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
