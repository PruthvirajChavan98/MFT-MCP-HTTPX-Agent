#!/bin/sh
set -eu

API_BASE_URL_VALUE="${FRONTEND_API_BASE_URL:-/api}"
APP_ENV_VALUE="${FRONTEND_APP_ENV:-production}"

escape_js() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

API_BASE_URL_ESCAPED="$(escape_js "$API_BASE_URL_VALUE")"
APP_ENV_ESCAPED="$(escape_js "$APP_ENV_VALUE")"

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__RUNTIME_CONFIG__ = {
  API_BASE_URL: "${API_BASE_URL_ESCAPED}",
  APP_ENV: "${APP_ENV_ESCAPED}"
};
EOF
