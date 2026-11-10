#!/bin/zsh
# Mac から予約投稿の workflow を起動する（GitHub の定時実行が遅れるため）。
# launchd（mac/com.gkc.instagram-trigger.plist）が毎日 19:05 と 21:05 に呼ぶ。
# 出す投稿がなければ workflow 側で何もしない。二重投稿は posted.json と concurrency で防ぐ。
LOG="$HOME/Library/Logs/gkc-instagram-trigger.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') 起動" >> "$LOG"
"$HOME/.local/bin/gh" workflow run post.yml --repo yotty19911207/gkc-instagram >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') 終了コード $?" >> "$LOG"
