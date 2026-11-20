-- Runs once on first start of the db volume. Separate database for automated tests.
CREATE DATABASE pantalelle_test;
\c pantalelle
CREATE EXTENSION IF NOT EXISTS vector;
\c pantalelle_test
CREATE EXTENSION IF NOT EXISTS vector;
