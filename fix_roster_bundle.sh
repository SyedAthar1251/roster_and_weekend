#!/usr/bin/env bash
# Run from the app root:  cd ~/frappe-bench/apps/roster_and_weekend && bash fix_roster_bundle.sh
# 1) makes the roster board use /hr/roster as its base (either state of the files is handled)
# 2) renames the two bundle files so the browser cannot serve the old cached copy
set -e
PKG=roster_and_weekend
A=$PKG/public/roster/assets
[ -d "$A" ] || { echo "Run this from the app root (the folder that contains pyproject.toml)"; exit 1; }

IDX=$(ls $A/index-*.js | head -1)
HOME_JS=$(ls $A/Home-*.js | head -1)

# base + login redirect
sed -i 's#Wb("/roster")#Wb("/hr/roster")#' "$IDX"
sed -i 's#redirect-to=%2Froster#redirect-to=%2Fhr%2Froster#' "$HOME_JS"

# rename for cache busting (only the first time)
case "$IDX" in
  *index-Il2aDi7h.js)
    for f in $A/*.js $PKG/public/roster/index.html $PKG/www/roster.html; do
      sed -i 's/index-Il2aDi7h/index-hrfix01/g; s/Home-B0D9W2wT/Home-hrfix01/g' "$f"
    done
    mv $A/index-Il2aDi7h.js $A/index-hrfix01.js
    mv $A/Home-B0D9W2wT.js $A/Home-hrfix01.js
    ;;
esac

echo "--- check (expect Wb(\"/hr/roster\") and redirect-to=%2Fhr%2Froster):"
grep -o 'Wb("[^"]*")' $A/index-*.js
grep -o 'redirect-to=[^"]*' $A/Home-*.js
echo "--- html entry points:"
grep -n "index-" $PKG/www/roster.html
ls $A | grep -E "^(index|Home)-"