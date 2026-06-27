# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

近鉄バスの接近情報サイト（`kintetsu-bus.jorudan.biz/busstatedtl`）から到着予定情報を取得し、Ubuntu 13.04 Kobo タブレット上で HTTP サーバーとして起動・表示するツール。

**問題**: Kobo の古いブラウザーは TLS 証明書を検証できず、HTTPS サイトを閲覧できない。  
**解決策**: このPC（Python 3.12）から SSH/SCP で Kobo にスクリプトを転送し、Kobo 上で HTTP サーバーを起動。Firefox で `http://localhost:8080/` を開いて表示する。

## 開発環境

Python 3.12 / uv を使用。

```bash
uv sync                                      # 依存関係のインストール
uv run python main.py                        # Kobo に接続してサーバー起動
uv run python bus_fetch.py config.yaml       # ローカルテスト（HTML 出力: /tmp/buses.html）
```

## ファイル構成

```
このPC                               Kobo (/home/marek/python_apps/bus_statedtl/)
├── main.py          ─SSH/SCP→      ├── bus_fetch.py
├── bus_fetch.py     ─SCP→          ├── bus_server.py
├── bus_server.py    ─SCP→          ├── startup.sh  ← chmod +x / ~/.xinitrc 登録
├── startup.sh       ─SCP→          └── config.yaml
├── config.yaml
└── .env (接続情報・コミット禁止)
```

## アーキテクチャ

### `main.py`（PC 上で実行）
- `.env` から `KOBO_IP` / `KOBO_ACCONT` / `KOBO_ACCONT_PASSWORD` を読み込む
- `scp` + `SSH_ASKPASS` でパスワード認証（Dropbear 2014 対応のレガシーSSH鍵交換方式を使用）
- `bus_fetch.py`・`bus_server.py`・`startup.sh`・`config.yaml` を Kobo の `/home/marek/python_apps/bus_statedtl/` へ転送
- `startup.sh` を `chmod +x` して実行権を付与
- `~/.xinitrc` に `startup.sh &` を追記（`grep` による冪等チェック付き）
- `bash startup.sh` でサーバー起動・Firefox 表示

### `startup.sh`（Kobo 上で実行・自動起動）
- `command -v` で `python3` / `python` / `python2` を自動検出
- 既存の `bus_server.py` プロセスと Firefox を `pkill` で終了（不要なタブを残さない）
- `bus_server.py` をバックグラウンドで起動後、Firefox で `http://localhost:8080/` を開く
- `~/.xinitrc` 経由で X セッション起動時に自動実行される

### `bus_fetch.py`（Kobo 上で実行）
- Python 2/3 両対応（Ubuntu 13.04 は Python 2.7 が標準）
- `ssl._create_unverified_context()` で TLS 検証をスキップ
- `get_server_time()`: バスサイトの HTTP Date ヘッダーからサーバー時刻（JST）を取得（Kobo クロックが不正確なため）
- `html_to_text()` でページ全体のテキストを抽出
- `parse_bus_entries()` で正規表現パターン `N | HH:MM 到着予定 STATUS ... 定刻：HH:MM (遅延)` を解析
- `generate_html()`: Kobo グレースケール向けカード形式 HTML を生成（複数ページ対応・ページ切り替えボタン付き）
- スタンドアロン起動時は `/tmp/buses.html` に出力して `xdg-open` でブラウザを起動

### `bus_server.py`（Kobo 上で実行）
- Python 3 専用（`http.server` モジュールを使用）
- ポート 8080 で HTTP サーバーを起動
- `GET /?page=N` でページ切り替え（`config.yaml` の複数ページに対応）
- リクエストごとにバスサイトから最新情報を取得して HTML を生成
- `<meta http-equiv="refresh" content="60">` で 60 秒ごとに自動更新

### `config.yaml`（路線設定）
- `url` 内の `YYYYMMDDHHMM` プレースホルダーを実行時に現在時刻で置換
- 路線の追加・削除はこのファイルを編集するだけ
- 複数 `page` を定義するとサーバー画面にページ切り替えボタンが表示される

## 依存パッケージ

PC 側のみ必要（Kobo 側は標準ライブラリのみ）:
- `paramiko` — SSH/SCP（参照用に残存、実際は `scp` コマンドを使用）
- `python-dotenv` — `.env` 読み込み
