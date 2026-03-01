# Running PostgreSQL Tests

Start a local PostgreSQL instance:

    docker run -d -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15

Run all tests against PostgreSQL:

    pytest --pg

Run only PostgreSQL-specific compatibility tests:

    pytest --pg -m pg

Skip PostgreSQL-specific tests when running against SQLite (default):

    pytest -m "not pg"
