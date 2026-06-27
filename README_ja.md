# 近鉄バス接近情報ビューア（Kobo タブレット向け）

## 目的

近鉄バスの接近情報サイトの到着予定を、TLS 証明書を検証できない古いブラウザしか持たない Ubuntu 13.04 Kobo タブレット上で表示するためのツール。

**解決策**: PC からスクリプトを SSH/SCP で Kobo に転送し、Kobo 上で HTTP サーバーを起動。Firefox で `http://localhost:8080/` を開いて表示する（60 秒ごとに自動更新）。

## 実行環境

Kobo タブレットの改造手順は[こちら](https://sites.google.com/site/gibekm/hardware/kobo/kobo-as-tablet)を参照。

## セットアップ

`.env` ファイルをプロジェクトルートに作成（コミット禁止）:

```
KOBO_IP=192.168.x.x
KOBO_ACCONT=ユーザー名
KOBO_ACCONT_PASSWORD=パスワード
```

依存関係のインストール:

```bash
uv sync
```

## 使い方

```bash
# Kobo に接続してサーバーを起動
uv run python main.py

# ローカルテスト（PC 上で HTML を生成して開く）
uv run python bus_fetch.py config.yaml
```

`main.py` を実行すると以下が自動で行われる:
1. `bus_fetch.py`・`bus_server.py`・`config.yaml` を Kobo へ転送
2. Kobo 上で HTTP サーバーをポート 8080 で起動
3. Kobo の Firefox で `http://localhost:8080/` を開く

## 路線の設定

`config.yaml` を編集して路線を追加・削除する。複数 `page` を定義するとページ切り替えボタンが表示される。

```yaml
pages:
  - page: "ＪＲ八尾駅前"
    routes:
      - label: "近鉄八尾駅前行"
        url: "https://kintetsu-bus.jorudan.biz/busstatedtl?...&dt=YYYYMMDDHHMM&..."
      - label: "藤井寺駅行"
        url: "https://kintetsu-bus.jorudan.biz/busstatedtl?...&dt=YYYYMMDDHHMM&..."
  - page: "八尾→藤井寺"
    routes:
      - label: "八尾駅前発"
        url: "https://kintetsu-bus.jorudan.biz/busstatedtl?...&dt=YYYYMMDDHHMM&..."
```

URL 内の `YYYYMMDDHHMM` は実行時に現在時刻で自動置換される。

## 情報ソースの例（バスサイト）

- [近鉄八尾駅前行](https://kintetsu-bus.jorudan.biz/busstatedtl?mode=4&fr=%E8%97%A4%E3%81%AE%E9%87%8C%E4%BD%8F%E5%AE%85%E5%89%8D&frsk=B&tosk=&dt=202606270747&dgmpl=%E8%97%A4%E3%81%AE%E9%87%8C%E4%BD%8F%E5%AE%85%E5%89%8D%E3%80%94%E8%BF%91%E9%89%84%E3%83%90%E3%82%B9%E3%80%95%3A1%3A1&p=0%2C14%2C15)
