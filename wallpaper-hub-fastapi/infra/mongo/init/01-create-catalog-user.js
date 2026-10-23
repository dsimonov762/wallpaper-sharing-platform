// Runs once, when the Mongo data volume is empty (official mongo image, /docker-entrypoint-initdb.d).
// Creates the service's own database user, like infra/postgres/init does for Postgres.
// The password comes from the container environment (set in docker-compose.yml from infra/.env).
const password = process.env.CATALOG_DB_PASSWORD;
if (!password) {
  throw new Error("CATALOG_DB_PASSWORD is not set");
}

db.getSiblingDB("catalog").createUser({
  user: "catalog_svc",
  pwd: password,
  roles: [
    { role: "readWrite", db: "catalog" },
    // Integration tests use their own database so they never touch dev data.
    { role: "readWrite", db: "catalog_test" },
  ],
});
