#!/bin/bash
# Sincroniza el repo local con el commit del bot de GitHub Actions.
set -u
cd /mnt/c/Users/GIGABYTE-PC/Documents/mi-epg || exit 1

echo "--- fetch ---"
git fetch origin

echo "--- rebase ---"
if git rebase origin/main; then
    echo "rebase limpio"
else
    echo "conflictos detectados, resolviendo a favor de la limpieza"
    git status --short | head -20
    # Los XML grandes y el diagnostico deben quedar fuera del repo
    git rm -f --ignore-unmatch output/mi-epg.xml >/dev/null 2>&1
    git rm -f --ignore-unmatch output/mi-epg-compatible.xml >/dev/null 2>&1
    git rm -rf --ignore-unmatch output/diagnostico >/dev/null 2>&1
    git rm -f --ignore-unmatch output/mi-epg-tivimate.xml >/dev/null 2>&1
    git rm -f --ignore-unmatch output/mi-epg-tivimate.xml.gz >/dev/null 2>&1
    git rm -f --ignore-unmatch output/prueba-mini.xml >/dev/null 2>&1
    git rm -f --ignore-unmatch output/prueba-mini.xml.gz >/dev/null 2>&1
    git add -A
    if git -c core.editor=true rebase --continue; then
        echo "rebase completado"
    else
        echo "rebase sigue con problemas"
        git status | head -20
        exit 1
    fi
fi

echo "--- push ---"
git push origin main 2>&1 | tail -6

echo "--- estado final ---"
git log --oneline -3
git status --short | head -10
