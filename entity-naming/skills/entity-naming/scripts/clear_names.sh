#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# clear_names.sh — India entity/brand name clearance engine
#
# Checks candidate names against domain registries (authoritative, via RDAP) and
# emits the official/semi-official links for the checks India does not expose to
# machines (MCA register, IP India trademark register).
#
# WHY THE SPLIT MATTERS: domains are the only part of Indian name clearance that
# can be resolved definitively without a human. MCA sits behind Akamai bot
# protection and a login; IP India sits behind a CAPTCHA. Every automated route
# to both has been tried and blocked. So this script is deliberately honest about
# its own scope — it resolves what is resolvable and hands you clean links for
# the rest, rather than pretending a scrape is a verdict.
#
# Usage:
#   ./clear_names.sh trisendra kynexta ozarva
#   ./clear_names.sh --json trisendra kynexta > clearance.json
#   ./clear_names.sh --json --tlds "com,in,co.in" --file candidates.txt
#
# Options:
#   --json              Emit machine-readable JSON (feeds score_names.py)
#   --tlds "a,b,c"      Override TLD set (default: com,in,co.in,net)
#   --file PATH         Read candidates from file, one per line (# = comment)
#   --timeout N         Per-request timeout seconds (default 12)
#
# Exit codes: 0 = ran clean · 1 = usage error · 2 = every lookup failed (network)
# Deps: bash, curl, sed, tr (all preinstalled on macOS).
# ------------------------------------------------------------------------------

set -u

TIMEOUT=12
TLDS="com,in,co.in,net"
JSON=0
FILE=""
NAMES=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --json)    JSON=1; shift ;;
    --tlds)    TLDS="${2:-}"; shift 2 ;;
    --file)    FILE="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT="${2:-12}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    -*)        echo "Unknown option: $1" >&2; exit 1 ;;
    *)         NAMES+=("$1"); shift ;;
  esac
done

if [ -n "$FILE" ]; then
  [ -f "$FILE" ] || { echo "No such file: $FILE" >&2; exit 1; }
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [ -n "$line" ] && NAMES+=("$line")
  done < "$FILE"
fi

if [ "${#NAMES[@]}" -eq 0 ]; then
  echo "Usage: $0 [--json] [--tlds com,in] [--file candidates.txt] <name> [name2 ...]" >&2
  exit 1
fi

IFS=',' read -r -a TLD_ARR <<< "$TLDS"

# ---- RDAP lookup -------------------------------------------------------------
# RDAP is the IANA-mandated successor to WHOIS and returns structured, rate-clean
# answers: 404 means no registration record exists (the name is free to buy),
# 200 means it is taken. Verisign is queried directly for .com/.net because the
# bootstrap resolver adds a redirect hop we do not need; everything else goes
# through rdap.org, which routes to the correct registry automatically.
# Retries exist because RDAP endpoints return 429 under burst load, and a
# rate-limit answer misread as "available" is the single most expensive error
# this script could make.
check_domain() {
  local fqdn="$1" url code attempt=0
  case "$fqdn" in
    *.com|*.net) url="https://rdap.verisign.com/${fqdn##*.}/v1/domain/$fqdn" ;;
    *)           url="https://rdap.org/domain/$fqdn" ;;
  esac
  while [ "$attempt" -lt 3 ]; do
    code=$(curl -s -L -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null)
    case "$code" in
      404) echo "AVAILABLE"; return ;;
      200) echo "REGISTERED"; return ;;
      429) attempt=$((attempt+1)); sleep $((attempt*2)) ;;
      *)   echo "UNKNOWN"; return ;;
    esac
  done
  echo "RATE_LIMITED"
}

normalise() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]'; }

ANY_OK=0

# ---- JSON output -------------------------------------------------------------
if [ "$JSON" -eq 1 ]; then
  printf '{\n  "checked_utc": "%s",\n  "tlds": [' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  for i in "${!TLD_ARR[@]}"; do
    [ "$i" -gt 0 ] && printf ', '
    printf '"%s"' "${TLD_ARR[$i]}"
  done
  printf '],\n  "candidates": [\n'
  first=1
  for RAW in "${NAMES[@]}"; do
    NAME=$(normalise "$RAW")
    [ -z "$NAME" ] && continue
    [ "$first" -eq 0 ] && printf ',\n'
    first=0
    printf '    {\n      "input": "%s",\n      "slug": "%s",\n      "length": %d,\n      "domains": {' "$RAW" "$NAME" "${#NAME}"
    d_first=1
    for tld in "${TLD_ARR[@]}"; do
      res=$(check_domain "$NAME.$tld")
      [ "$res" = "AVAILABLE" ] || [ "$res" = "REGISTERED" ] && ANY_OK=1
      [ "$d_first" -eq 0 ] && printf ','
      d_first=0
      printf '\n        "%s": "%s"' "$tld" "$res"
    done
    printf '\n      },\n'
    printf '      "manual_checks": {\n'
    printf '        "mca_master_data": "https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html",\n'
    printf '        "mca_mirror": "https://www.zaubacorp.com/companysearchresults/%s",\n' "$NAME"
    printf '        "trademark_ipindia": "https://tmrsearch.ipindia.gov.in/eregister/",\n'
    printf '        "instagram": "https://instagram.com/%s",\n' "$NAME"
    printf '        "x": "https://x.com/%s",\n' "$NAME"
    printf '        "linkedin": "https://www.linkedin.com/company/%s"\n' "$NAME"
    printf '      }\n    }'
  done
  printf '\n  ]\n}\n'
  [ "$ANY_OK" -eq 1 ] || exit 2
  exit 0
fi

# ---- Human-readable output ---------------------------------------------------
for RAW in "${NAMES[@]}"; do
  NAME=$(normalise "$RAW")
  [ -z "$NAME" ] && continue
  echo "=============================================================="
  echo " CANDIDATE: $RAW   (slug: $NAME, ${#NAME} chars)"
  echo "=============================================================="
  echo "-- Domains (authoritative, RDAP) --------------------------------"
  for tld in "${TLD_ARR[@]}"; do
    res=$(check_domain "$NAME.$tld")
    [ "$res" = "AVAILABLE" ] || [ "$res" = "REGISTERED" ] && ANY_OK=1
    case "$res" in
      AVAILABLE)  mark="OK   " ;;
      REGISTERED) mark="TAKEN" ;;
      *)          mark="?????" ;;
    esac
    printf "   %-8s : %-5s %s\n" ".$tld" "$mark" "$res"
  done
  echo "-- Not machine-checkable in India: run these yourself ------------"
  echo "   MCA register    : https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html"
  echo "   MCA mirror      : https://www.zaubacorp.com/companysearchresults/$NAME"
  echo "   Trademark       : https://tmrsearch.ipindia.gov.in/eregister/  (Wordmark + Phonetic)"
  echo "   Instagram       : https://instagram.com/$NAME"
  echo "   LinkedIn        : https://www.linkedin.com/company/$NAME"
  echo ""
done

echo "REMINDER: domains above are live and authoritative. The MCA register and"
echo "trademark register are NOT — the only binding MCA check is your CA's"
echo "RUN/SPICe+ filing, and the only binding TM check is a proper IP India search."
[ "$ANY_OK" -eq 1 ] || exit 2
exit 0
