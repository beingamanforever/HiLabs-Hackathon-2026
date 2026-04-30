#!/usr/bin/env bash
# Container entrypoint — assume the judge-provided IAM role (if any) before
# starting the API. The PS requires that the docker image "publish ... endpoints
# to query the data by assuming the write-only role created by the IT team."
#
# This script supports three credential modes, in priority order:
#
#   1. AWS_ROLE_ARN + AWS_WEB_IDENTITY_TOKEN_FILE  (IRSA / OIDC, EKS-style)
#      -> aws sts assume-role-with-web-identity, export the temp credentials.
#
#   2. AWS_ROLE_ARN alone (with the host already authenticated, e.g. EC2 IMDS)
#      -> aws sts assume-role, export the temp credentials.
#
#   3. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY already set (local dev)
#      -> pass through unchanged.
#
# If none of these are present we still start the API (read-only mode) so the
# /health and /metrics endpoints can be sanity-checked without AWS access.
#
# Required tooling in the image: aws CLI v2, jq, python3, uvicorn.

set -euo pipefail

log() { printf '[entrypoint] %s\n' "$*" >&2; }

assume_with_web_identity() {
    log "AWS_ROLE_ARN + AWS_WEB_IDENTITY_TOKEN_FILE present — assuming role via OIDC"
    local creds
    creds="$(aws sts assume-role-with-web-identity \
        --role-arn "${AWS_ROLE_ARN}" \
        --role-session-name "r3hackathon-$(date +%s)" \
        --web-identity-token "$(cat "${AWS_WEB_IDENTITY_TOKEN_FILE}")" \
        --duration-seconds 3600)"
    export AWS_ACCESS_KEY_ID="$(echo "${creds}" | jq -r .Credentials.AccessKeyId)"
    export AWS_SECRET_ACCESS_KEY="$(echo "${creds}" | jq -r .Credentials.SecretAccessKey)"
    export AWS_SESSION_TOKEN="$(echo "${creds}" | jq -r .Credentials.SessionToken)"
    log "OIDC role assumed. Session expires: $(echo "${creds}" | jq -r .Credentials.Expiration)"
}

assume_plain() {
    log "AWS_ROLE_ARN present (no token file) — assuming role with host credentials"
    local creds
    creds="$(aws sts assume-role \
        --role-arn "${AWS_ROLE_ARN}" \
        --role-session-name "r3hackathon-$(date +%s)" \
        --duration-seconds 3600)"
    export AWS_ACCESS_KEY_ID="$(echo "${creds}" | jq -r .Credentials.AccessKeyId)"
    export AWS_SECRET_ACCESS_KEY="$(echo "${creds}" | jq -r .Credentials.SecretAccessKey)"
    export AWS_SESSION_TOKEN="$(echo "${creds}" | jq -r .Credentials.SessionToken)"
    log "Plain role assumed."
}

# --- credential resolution ---------------------------------------------------
if [[ -n "${AWS_ROLE_ARN:-}" && -n "${AWS_WEB_IDENTITY_TOKEN_FILE:-}" ]]; then
    if ! command -v aws >/dev/null 2>&1; then
        log "FATAL: aws CLI required for AWS_WEB_IDENTITY_TOKEN_FILE flow but not installed."
        exit 2
    fi
    assume_with_web_identity
elif [[ -n "${AWS_ROLE_ARN:-}" ]]; then
    if ! command -v aws >/dev/null 2>&1; then
        log "FATAL: aws CLI required for AWS_ROLE_ARN flow but not installed."
        exit 2
    fi
    assume_plain
elif [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    log "Using static AWS credentials from environment (local dev mode)."
else
    log "No AWS credentials supplied — starting API in read-only mode (no S3 writes will work)."
fi

# --- sanity logging ----------------------------------------------------------
log "OUTPUT_DIR=${OUTPUT_DIR:-outputs}"
log "PORT=${PORT:-8000}"
log "BASE_DATA_FILE=${BASE_DATA_FILE:-/app/Base data_hackathon.xlsx}"

# --- launch ------------------------------------------------------------------
# Default command is uvicorn; allow override (e.g. for /predict CLI).
if [[ "$#" -gt 0 ]]; then
    exec "$@"
else
    exec uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
fi
