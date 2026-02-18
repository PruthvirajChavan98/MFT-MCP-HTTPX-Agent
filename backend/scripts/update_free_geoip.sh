#!/usr/bin/env bash
set -euo pipefail

# Free-only updater for GeoIP/IP2Proxy datasets.
# - GeoLite2 (free tier; requires MAXMIND_LICENSE_KEY + account id)
# - IP2Proxy LITE (free CSV/DB if a direct URL is provided)

DATA_DIR="${GEOIP_DATA_DIR:-/app/data/geoip}"
mkdir -p "$DATA_DIR"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

update_geolite2() {
  if [[ -z "${MAXMIND_ACCOUNT_ID:-}" || -z "${MAXMIND_LICENSE_KEY:-}" ]]; then
    log "GeoLite2 skipped: MAXMIND_ACCOUNT_ID/MAXMIND_LICENSE_KEY not set"
    return 0
  fi

  local edition="GeoLite2-City"
  local url="https://download.maxmind.com/app/geoip_download"
  local out_tgz="$DATA_DIR/${edition}.tar.gz"

  log "Downloading free ${edition} database"
  curl -fsSL "$url?edition_id=${edition}&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" -o "$out_tgz"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  tar -xzf "$out_tgz" -C "$tmp_dir"

  local mmdb
  mmdb="$(find "$tmp_dir" -name "*.mmdb" | head -n1 || true)"
  if [[ -z "$mmdb" ]]; then
    log "GeoLite2 update failed: .mmdb not found"
    rm -rf "$tmp_dir"
    return 1
  fi

  cp "$mmdb" "$DATA_DIR/GeoLite2-City.mmdb"
  rm -rf "$tmp_dir"
  log "GeoLite2 updated: $DATA_DIR/GeoLite2-City.mmdb"
}

update_ip2proxy_lite() {
  if [[ -z "${IP2PROXY_LITE_URL:-}" ]]; then
    log "IP2Proxy LITE skipped: IP2PROXY_LITE_URL not set"
    return 0
  fi

  local out_zip="$DATA_DIR/ip2proxy-lite.zip"
  log "Downloading free IP2Proxy LITE archive"
  curl -fsSL "$IP2PROXY_LITE_URL" -o "$out_zip"

  if command -v unzip >/dev/null 2>&1; then
    unzip -o "$out_zip" -d "$DATA_DIR" >/dev/null
    log "IP2Proxy LITE archive extracted into $DATA_DIR"
  else
    log "unzip not installed; kept archive at $out_zip"
  fi
}

main() {
  if [[ "${GEOIP_FREE_ONLY:-true}" != "true" ]]; then
    log "Refusing to run: GEOIP_FREE_ONLY must stay true"
    exit 1
  fi

  update_geolite2
  update_ip2proxy_lite
  log "Free GeoIP/IP2Proxy update cycle complete"
}

main "$@"
