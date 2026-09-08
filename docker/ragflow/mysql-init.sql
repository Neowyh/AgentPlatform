-- MySQL bootstrap for the iDeer knowledge-dev RAGFlow profile.
-- Mounted as /data/application/init.sql and executed by the MySQL entrypoint
-- on first start (empty data volume).

CREATE DATABASE IF NOT EXISTS rag_flow;
USE rag_flow;
