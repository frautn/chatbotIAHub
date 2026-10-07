# syntax=docker/dockerfile:1
#
# Production image for Moodle 5.3.
# Build context MUST be the root of this Moodle checkout, e.g.:
#   docker build -t moodle:5.3 /path/to/moodle503
#
# config.php is intentionally NOT copied from this checkout (it is a dev/testing
# file used by moodle-docker). It is instead generated at container startup from
# environment variables - see the entrypoint script installed below.

############################################
# Stage 1: production composer dependencies
############################################
FROM composer:2 AS vendor

WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install \
        --no-dev \
        --no-interaction \
        --no-progress \
        --optimize-autoloader \
        --no-scripts \
        --ignore-platform-reqs

############################################
# Stage 2: runtime image
############################################
FROM moodlehq/moodle-php-apache:8.3-bookworm

# Moodle source code.
COPY . /var/www/html
COPY --from=vendor /app/vendor /var/www/html/vendor

# config.php is per-environment, never ship the dev one baked into the checkout.
RUN set -eux; \
    rm -f /var/www/html/config.php; \
    rm -rf /var/www/html/.git; \
    mkdir -p /var/www/moodledata; \
    chown -R www-data:www-data /var/www/html /var/www/moodledata

# Renders config.php from environment variables on every container start.
# Required: MOODLE_DB_PASS, MOODLE_WWWROOT.
RUN mkdir -p /docker-entrypoint.d
RUN cat <<'EOS' > /docker-entrypoint.d/20-render-moodle-config.sh
#!/bin/bash
set -euo pipefail

: "${MOODLE_DB_PASS:?MOODLE_DB_PASS must be set}"
: "${MOODLE_WWWROOT:?MOODLE_WWWROOT must be set, e.g. https://moodle.example.com}"

chown -R www-data:www-data /var/www/moodledata || true

config=/var/www/html/config.php

cat > "$config" <<CONFIG
<?php
unset(\$CFG);
global \$CFG;
\$CFG = new stdClass();

\$CFG->dbtype    = 'pgsql';
\$CFG->dblibrary = 'native';
\$CFG->dbhost    = '${MOODLE_DB_HOST:-host.docker.internal}';
\$CFG->dbname    = '${MOODLE_DB_NAME:-moodle_db}';
\$CFG->dbuser    = '${MOODLE_DB_USER:-moodle_user}';
\$CFG->dbpass    = '${MOODLE_DB_PASS}';
\$CFG->prefix    = 'mdl_';
\$CFG->dboptions = [
    'dbpersist' => false,
    'dbport'    => '${MOODLE_DB_PORT:-5432}',
];

\$CFG->wwwroot   = '${MOODLE_WWWROOT}';
\$CFG->dataroot  = '/var/www/moodledata';
\$CFG->admin     = 'admin';
\$CFG->directorypermissions = 02770;

// This deployment terminates TLS on the host nginx reverse proxy.
\$CFG->sslproxy     = ${MOODLE_SSLPROXY:-true};
\$CFG->reverseproxy = ${MOODLE_REVERSEPROXY:-false};

require_once(__DIR__ . '/lib/setup.php');

// There is no PHP closing tag in this file - this is intentional.
CONFIG

chown www-data:www-data "$config"
chmod 640 "$config"
EOS
RUN chmod +x /docker-entrypoint.d/20-render-moodle-config.sh
