#!/bin/bash
# Verhuizing oude Mac naar nieuwe Mac (23-11-2026).
#   bash scripts/verhuis_controle.sh maak    op de OUDE Mac: schrijft ~/.omnivaleur/verhuis-manifest.txt
#   bash scripts/verhuis_controle.sh check   op de NIEUWE Mac: vergelijkt en meldt OK of ONTBREEKT
# Het manifest bevat alleen namen, aantallen en versies, geen sleutels.

M="$HOME/.omnivaleur/verhuis-manifest.txt"
REPOS=("Documents/omnivaleur" "omnivaleur-klantfouten" "Sites/kortax-dashboard" "Documents/apex-forge" "Documents/revaleur-blog" "Documents/garmin-coach" "Documents/Prediction Market Trading bot " "Documents/ZENbtw" "earshot" "huashu-motion" "huashu-art-motion" "claude-animation-skills" "Documents/hallmark" ".claude/skills/uxui-max")
MAPPEN=(".omnivaleur" ".claude/scheduled-tasks" ".claude/skills" ".claude/projects" "garmin-tracker" "Documents/porsche-monitor" "Documents/Handige Scripts Mac" "Library/Application Support/omnivaleur")
TELLEN() { timeout 120 find "$HOME/$1" -type f -not -path '*/node_modules/*' -not -path '*/venv/*' -not -path '*/.venv/*' -not -path '*/.git/*' 2>/dev/null | wc -l | tr -d ' '; }

maak() {
  mkdir -p "$HOME/.omnivaleur"
  : > "$M"
  echo "# gemaakt $(date '+%d-%m-%Y %H:%M') op $(scutil --get ComputerName)" >> "$M"
  for r in "${REPOS[@]}"; do
    echo "REPO|$r|$(git -C "$HOME/$r" rev-parse HEAD 2>/dev/null)" >> "$M"
  done
  for d in "${MAPPEN[@]}"; do echo "MAP|$d|$(TELLEN "$d")" >> "$M"; done
  for f in "$HOME"/Library/LaunchAgents/*.plist; do
    b=$(basename "$f" .plist)
    case "$b" in com.google.*|com.microsoft.*|com.grammarly.*|com.lwouis.*) continue;; esac
    echo "AGENT|$b" >> "$M"
  done
  for t in "$HOME"/.claude/scheduled-tasks/*/; do echo "TAAK|$(basename "$t")" >> "$M"; done
  for p in "$HOME/Library/Application Support/Google/Chrome"/{Default,Profile*}; do [ -d "$p" ] && echo "CHROME|$(basename "$p")" >> "$M"; done
  for a in /Applications/*.app; do echo "APP|$(basename "$a")" >> "$M"; done
  for c in node python3.13 uv gh pm2 ffmpeg git; do echo "TOOL|$c" >> "$M"; done
  echo "ENV|$(grep -c '=' "$HOME/Documents/omnivaleur/.env" 2>/dev/null)" >> "$M"
  echo "Manifest klaar: $(wc -l < "$M") regels in $M"
}

check() {
  [ -f "$M" ] || { echo "Geen manifest gevonden op $M"; exit 1; }
  ok=0; mis=0
  r() { if [ "$1" = ok ]; then ok=$((ok+1)); else mis=$((mis+1)); echo "ONTBREEKT: $2"; fi; }
  while IFS='|' read -r soort a b; do
    case "$soort" in
      REPO) h=$(git -C "$HOME/$a" rev-parse HEAD 2>/dev/null); [ -n "$h" ] && [ "$h" = "$b" ] && r ok || r mis "repo $a (stand ${h:0:7} tegen ${b:0:7})";;
      MAP) n=$(TELLEN "$a"); [ "$n" -ge "$b" ] && r ok || r mis "map $a ($n bestanden, was $b)";;
      AGENT) [ -f "$HOME/Library/LaunchAgents/$a.plist" ] && r ok || r mis "achtergrondprogramma $a";;
      TAAK) [ -d "$HOME/.claude/scheduled-tasks/$a" ] && r ok || r mis "geplande taak $a";;
      CHROME) [ -d "$HOME/Library/Application Support/Google/Chrome/$a" ] && r ok || r mis "Chrome-profiel $a";;
      APP) [ -d "/Applications/$a" ] && r ok || r mis "app $a";;
      TOOL) command -v "$a" >/dev/null && r ok || r mis "programma $a";;
      ENV) n=$(grep -c '=' "$HOME/Documents/omnivaleur/.env" 2>/dev/null); [ "${n:-0}" -ge "$a" ] && r ok || r mis ".env heeft ${n:-0} regels, was $a";;
    esac
  done < <(grep -v '^#' "$M")
  gh auth status >/dev/null 2>&1 && r ok || r mis "gh niet ingelogd"
  echo "Klaar: $ok goed, $mis ontbreken."
  [ "$mis" -eq 0 ]
}

case "$1" in maak) maak;; check) check;; *) echo "Gebruik: maak of check"; exit 2;; esac
