# NetConfig Manager

ネットワーク機器のコンフィグ収集 / 世代管理 / 構成図 / ターミナル / ユーザ管理を行う Web アプリケーション。

## 概要

| 機能 | 説明 |
|---|---|
| コンフィグ収集 | スケジュール実行 / 手動実行で `show running-config` 等を取得し DB へ保存 |
| 世代管理 | コンフィグ取得時にハッシュを計算し、前世代と差分があった場合のみ新世代として保存。Unified Diff をブラウザで表示可能 |
| 構成図 | 機器ページ内の「構成図」タブから利用。収集済 config から interface description を解析し相互参照しているインタフェース同士を自動描画。管理外オブジェクト (cloud/router/switch/firewall/server/generic) はパレットから配置可能。ノードのドラッグ/手動接続/位置保存に対応 (React Flow) |
| ターミナル | xterm.js + WebSocket + AsyncSSH によるブラウザ内 PTY。操作ログを監査ログへ保存 |
| ユーザ管理 | 管理者 / 一般ユーザのロール制御。Argon2id によるパスワードハッシュ。JWT 認証 |

## 構成図 (Topology) の仕組み

```
config (running-config)
   │
   ▼  services/config_parser.py        (vendor 別パーサ)
[interface name, description, ip] ...
   │
   ▼  services/topology.py             (description マッチング)
candidate links A.if─?─>B (相手のホスト名/エイリアスを description 内検索)
   │
   ▼ ペアリング (双方向→confirmed, 片側のみ→one_way)
GET /api/topology  → React Flow に描画
```

* **confirmed (緑実線)**: A と B 双方の interface description が相手機器名を含む
* **one_way (橙破線)**: 片側のみ参照
* **manual (黒実線)**: 画面上でユーザがドラッグして手動作成した接続

管理外オブジェクト・ノード位置・手動エッジは DB に保存され、リロード後も維持されます。

## アーキテクチャ

```
┌──────────────────────────────────────────────────────────────┐
│                       Browser (xterm.js)                       │
└───────────────────────────────┬──────────────────────────────┘
                                │ HTTPS / WSS
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                  Nginx (reverse proxy, TLS)                    │
└──────┬──────────────────────────────────────────┬────────────┘
       │ static                                   │ /api, /ws
       ▼                                          ▼
┌──────────────┐                       ┌───────────────────────┐
│ Frontend     │                       │ Backend (FastAPI)     │
│ React + Vite │                       │ - REST                │
│ (Nginx)      │                       │ - WebSocket (PTY)     │
└──────────────┘                       │ - Scheduler (APScheduler)│
                                       │ - AsyncSSH / Netmiko  │
                                       └─────────┬─────────────┘
                                                 │
                            ┌────────────────────┴───────────────────┐
                            ▼                                        ▼
                  ┌──────────────────┐                  ┌──────────────────────┐
                  │ PostgreSQL 16    │                  │ Network Devices      │
                  │ users / devices  │                  │ (Cisco, Juniper, ...) │
                  │ configs / logs   │                  └──────────────────────┘
                  └──────────────────┘
```

## ディレクトリ構成

```
.
├── backend/                  # FastAPI バックエンド
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   ├── deps.py
│   │   ├── config.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── devices.py
│   │   │   ├── configs.py
│   │   │   └── terminal.py
│   │   └── services/
│   │       ├── ssh_service.py
│   │       └── collector.py
│   ├── requirements.txt
│   ├── requirements.lock     # pip-compile で生成
│   └── Containerfile
├── frontend/                 # React + Vite フロントエンド
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/client.ts
│   │   ├── components/
│   │   │   └── Layout.tsx
│   │   └── pages/
│   │       ├── Login.tsx
│   │       ├── Devices.tsx
│   │       ├── Configs.tsx
│   │       ├── Terminal.tsx
│   │       └── Users.tsx
│   └── Containerfile
├── db/
│   └── init.sql
├── nginx/
│   └── nginx.conf
├── compose.yaml              # podman-compose 用
├── .env.example
└── README.md
```

## RHEL 10 への展開手順

```bash
# 1. Podman 導入 (RHEL 10 既定で導入済の想定)
sudo dnf install -y podman podman-compose

# 2. SELinux ボリュームラベル (rootless でも :Z 推奨)
sudo setsebool -P container_manage_cgroup on

# 3. 環境変数ファイルを編集
cp .env.example .env
vi .env   # JWT_SECRET, POSTGRES_PASSWORD などを書き換え

# 4. 起動
podman-compose up -d --build

# 5. 動作確認
curl -k https://localhost/api/healthz
```

### Quadlet で systemd 化 (RHEL 10 推奨)

`/etc/containers/systemd/` に Quadlet ユニットを配置することで `systemctl` で管理できます (本リポジトリの `deploy/quadlet/` 参照、必要に応じ生成)。

## セキュリティ留意点

- `.env` で `JWT_SECRET` / `POSTGRES_PASSWORD` を 32 文字以上のランダム文字列に変更すること
- 初回 admin ユーザは `db/init.sql` でブートストラップされる (`admin` / `ChangeMe!23`)。**初回ログイン後に必ず変更**
- 機器の SSH パスワード / 鍵は `app_secret_key` (Fernet) で暗号化して DB に保存
- ターミナル操作はすべて `audit_logs` に保存

## 主要依存ライブラリ

### Backend
- fastapi, uvicorn[standard]
- sqlalchemy[asyncio], asyncpg, alembic
- pydantic, pydantic-settings
- passlib[argon2], python-jose[cryptography]
- asyncssh, netmiko
- apscheduler
- cryptography

### Frontend
- react, react-dom, react-router-dom
- @tanstack/react-query
- axios
- xterm, xterm-addon-fit, xterm-addon-attach
- monaco-editor (diff 表示)
- tailwindcss

詳細は `backend/requirements.txt` / `frontend/package.json` を参照。
