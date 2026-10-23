#!/bin/sh
# One Postgres server for local development, but one database AND one login role per
# service ("database per service"): account_svc cannot read the media database.
# Runs only when the data volume is empty (first start). To re-run: `just infra-reset`.
set -eu

create_database() {
  db="$1"; role="$2"; password="$3"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<EOSQL
CREATE ROLE ${role} LOGIN PASSWORD '${password}';
CREATE DATABASE ${db} OWNER ${role};
EOSQL
}

create_database account  account_svc  "$ACCOUNT_DB_PASSWORD"
create_database media    media_svc    "$MEDIA_DB_PASSWORD"
create_database keycloak keycloak_svc "$KEYCLOAK_DB_PASSWORD"
