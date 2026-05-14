-- =============================================================
-- NetConfig Manager - PostgreSQL schema bootstrap
-- =============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----- users -----
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(64)   NOT NULL UNIQUE,
    email           VARCHAR(255)  UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    role            VARCHAR(16)   NOT NULL DEFAULT 'user'
                                  CHECK (role IN ('admin','user','readonly')),
    is_active       BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 初期管理者 (Argon2id hash of "ChangeMe!23")
-- 起動後、必ずパスワード変更を行うこと
INSERT INTO users (username, email, password_hash, role)
VALUES (
  'admin',
  'admin@example.local',
  '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzb21lc2FsdA$5sZG1m9pXxK7uA4w3oQK1JwLMSV6P0nP3qkO7m1m1Hk',
  'admin'
)
ON CONFLICT (username) DO NOTHING;

-- ----- devices -----
CREATE TABLE IF NOT EXISTS devices (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(128)  NOT NULL UNIQUE,
    hostname        VARCHAR(255)  NOT NULL,
    port            INT           NOT NULL DEFAULT 22,
    vendor          VARCHAR(32)   NOT NULL,          -- cisco_ios, cisco_xe, juniper, arista_eos, ...
    description     TEXT,
    username        VARCHAR(128)  NOT NULL,
    -- Fernet で暗号化したパスワード / 鍵
    secret_enc      TEXT          NOT NULL,
    enable_secret_enc TEXT,
    tags            JSONB         NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_vendor ON devices(vendor);

-- ----- configs (世代管理) -----
CREATE TABLE IF NOT EXISTS configs (
    id              BIGSERIAL PRIMARY KEY,
    device_id       BIGINT        NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    revision        INT           NOT NULL,           -- 世代番号 (機器ごとに連番)
    content         TEXT          NOT NULL,
    content_sha256  CHAR(64)      NOT NULL,
    collected_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    collected_by    VARCHAR(64)   NOT NULL,           -- 'scheduler' or username
    note            TEXT,
    UNIQUE (device_id, revision),
    UNIQUE (device_id, content_sha256)               -- 同一内容の重複保存を防ぐ
);

CREATE INDEX IF NOT EXISTS idx_configs_device_collected
    ON configs(device_id, collected_at DESC);

-- ----- audit_logs -----
CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT        REFERENCES users(id) ON DELETE SET NULL,
    username        VARCHAR(64),
    device_id       BIGINT        REFERENCES devices(id) ON DELETE SET NULL,
    action          VARCHAR(64)   NOT NULL,           -- login, ssh_open, ssh_command, config_collect, ...
    detail          JSONB         NOT NULL DEFAULT '{}'::jsonb,
    occurred_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_occurred
    ON audit_logs(occurred_at DESC);

-- ====================================================================
-- Topology (構成図) 関連
-- ====================================================================

-- 管理外オブジェクト (cloud / router / switch / firewall / server / generic)
CREATE TABLE IF NOT EXISTS topology_nodes (
    id              BIGSERIAL PRIMARY KEY,
    label           VARCHAR(128)  NOT NULL,
    kind            VARCHAR(32)   NOT NULL DEFAULT 'generic'
                                  CHECK (kind IN ('cloud','router','switch','firewall','server','generic')),
    x               DOUBLE PRECISION NOT NULL DEFAULT 0,
    y               DOUBLE PRECISION NOT NULL DEFAULT 0,
    note            TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 管理対象 device の配置 (構成図用)
CREATE TABLE IF NOT EXISTS topology_device_positions (
    device_id       BIGINT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    x               DOUBLE PRECISION NOT NULL DEFAULT 0,
    y               DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 手動接続 (auto-detect された edge と組み合わせて表示)
-- source/target は 'device:<id>' / 'node:<id>' のいずれか
CREATE TABLE IF NOT EXISTS topology_edges (
    id              BIGSERIAL PRIMARY KEY,
    source_type     VARCHAR(8)    NOT NULL CHECK (source_type IN ('device','node')),
    source_id       BIGINT        NOT NULL,
    source_iface    VARCHAR(64),
    target_type     VARCHAR(8)    NOT NULL CHECK (target_type IN ('device','node')),
    target_id       BIGINT        NOT NULL,
    target_iface    VARCHAR(64),
    note            TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topology_edges_source
    ON topology_edges(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_topology_edges_target
    ON topology_edges(target_type, target_id);
