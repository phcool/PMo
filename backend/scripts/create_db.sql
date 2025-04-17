-- 创建数据库
CREATE DATABASE dlmonitor;

-- 连接到数据库
\c dlmonitor

-- 创建扩展（用于全文搜索）
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin; 