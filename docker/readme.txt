It starts Postgres, waits for it to become healthy, then starts Open WebUI. Set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and OPENAI_API_KEY in the environment before running it; OPENAI_API_BASE_URL is configurable too.

For an external database, set START_POSTGRES=false and provide DATABASE_URL. The Compose files now accept these variables, and the two services remain on separate networks. Postgres credentials here configure the database; Open WebUI user accounts are created through its web interface.

.env
Keep the file out of Git and restrict its permissions with chmod 600 docker/.env; it contains secrets. 