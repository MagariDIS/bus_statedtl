import os
import sys
import subprocess
import tempfile
from dotenv import load_dotenv

load_dotenv()

REMOTE_DIR = '/home/marek/python_apps/bus_statedtl'
SCRIPT_NAME = 'bus_fetch.py'
SERVER_NAME = 'bus_server.py'
QT_NAME     = 'bus_qt.py'
PUSH_NAME   = 'bus_push.py'
CONFIG_NAME = 'config.yaml'
SERVER_PORT = 8080
STARTUP_NAME = 'startup.sh'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dropbear 2014 (Kobo) に接続するための SSH オプション
SSH_OPTS = [
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'ConnectTimeout=10',
    '-o', 'HostKeyAlgorithms=+ssh-rsa,ssh-dss',
    '-o', 'KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group14-sha1',
    '-o', 'PubkeyAuthentication=no',
]


def get_kobo_config():
    host = os.environ.get('KOBO_IP')
    user = os.environ.get('KOBO_ACCONT')
    password = os.environ.get('KOBO_ACCONT_PASSWORD')
    if not all([host, user, password]):
        print('ERROR: .env に KOBO_IP / KOBO_ACCONT / KOBO_ACCONT_PASSWORD が必要です')
        sys.exit(1)
    return host, user, password


def make_env(password):
    """SSH_ASKPASS でパスワードを渡すための環境変数を作成する"""
    askpass = os.path.join(tempfile.gettempdir(), 'kobo_askpass.sh')
    with open(askpass, 'w') as f:
        f.write('#!/bin/sh\necho ' + password.replace("'", "'\\''") + '\n')
    os.chmod(askpass, 0o700)
    env = os.environ.copy()
    env['DISPLAY'] = ''
    env['SSH_ASKPASS'] = askpass
    env['SSH_ASKPASS_REQUIRE'] = 'force'
    return env


def run(cmd, env, check=True):
    """setsid 経由でコマンドを実行してパスワードを自動入力する"""
    full_cmd = ['setsid', '-w'] + cmd
    result = subprocess.run(
        full_cmd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.stdout:
        print(result.stdout.decode('utf-8', errors='replace'), end='')
    if result.stderr:
        sys.stderr.write(result.stderr.decode('utf-8', errors='replace'))
    if check and result.returncode != 0:
        print(f'ERROR: コマンド失敗 (exit {result.returncode})')
        sys.exit(result.returncode)
    return result


def scp_file(local_path, remote, env):
    print(f'転送: {local_path} → {remote}')
    # -O: Dropbear は SFTP サブシステムを持たないのでレガシー SCP プロトコルを使用
    run(['scp', '-O'] + SSH_OPTS + [local_path, remote], env)


def ssh_run(host_str, command, env, check=True):
    print(f'実行: {command}')
    run(['ssh'] + SSH_OPTS + [host_str, command], env, check=check)


def detect_python(host_str, env):
    """Kobo 上で使用可能な Python コマンドを検出する"""
    for candidate in ('python3', 'python', 'python2'):
        result = run(
            ['ssh'] + SSH_OPTS + [host_str, f'{candidate} --version 2>&1'],
            env, check=False,
        )
        out = result.stdout.decode('utf-8', errors='replace')
        if 'Python' in out:
            print(f'Python 検出: {out.strip()}  ({candidate})')
            return candidate
    print('WARNING: Python が見つかりません。python を使用します。')
    return 'python'


def main():
    host, user, password = get_kobo_config()
    host_str = f'{user}@{host}'
    env = make_env(password)

    local_script  = os.path.join(BASE_DIR, SCRIPT_NAME)
    local_server  = os.path.join(BASE_DIR, SERVER_NAME)
    local_qt      = os.path.join(BASE_DIR, QT_NAME)
    local_config  = os.path.join(BASE_DIR, CONFIG_NAME)
    local_startup = os.path.join(BASE_DIR, STARTUP_NAME)
    remote_script  = f'{REMOTE_DIR}/{SCRIPT_NAME}'
    remote_server  = f'{REMOTE_DIR}/{SERVER_NAME}'
    remote_qt      = f'{REMOTE_DIR}/{QT_NAME}'
    remote_config  = f'{REMOTE_DIR}/{CONFIG_NAME}'
    remote_startup = f'{REMOTE_DIR}/{STARTUP_NAME}'

    print(f'接続先: {host_str}')

    # PC の現在時刻を Kobo に同期
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'日時同期: {now}')
    ssh_run(host_str, f'sudo date -s "{now}" 2>/dev/null || date -s "{now}"', env, check=False)

    ssh_run(host_str, f'mkdir -p {REMOTE_DIR}', env)
    scp_file(local_script, f'{host_str}:{remote_script}', env)
    scp_file(local_server, f'{host_str}:{remote_server}', env)
    scp_file(local_qt, f'{host_str}:{remote_qt}', env)
    scp_file(local_config, f'{host_str}:{remote_config}', env)
    scp_file(local_startup, f'{host_str}:{remote_startup}', env)
    ssh_run(host_str, f'chmod +x {remote_startup}', env)

    # ~/.xinitrc から startup.sh の行を削除（残留エントリのクリーンアップ）
    ssh_run(host_str,
        f'grep -v "startup.sh" ~/.xinitrc > /tmp/xrc_new 2>/dev/null'
        f' && mv /tmp/xrc_new ~/.xinitrc',
        env, check=False)

    # startup.sh 経由で Qt アプリ起動
    ssh_run(host_str, f'bash {remote_startup}', env, check=False)

    # PC 側プッシュデーモンをバックグラウンドで起動
    push_script = os.path.join(BASE_DIR, PUSH_NAME)
    subprocess.Popen([sys.executable, push_script])
    print(f'バスデータプッシュデーモン起動（{PUSH_NAME}）')
    print('（60秒ごとにデータ取得 → Kobo へ SCP 転送）')


if __name__ == '__main__':
    main()
