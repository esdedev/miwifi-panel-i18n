#!/bin/sh
# File-backed stand-in for the router's nvram tool, for the emulator only.
DB=/tmp/nvram.db
touch "$DB"
case "$1" in
    get) grep "^$2=" "$DB" | head -1 | cut -d= -f2- ;;
    set) k=${2%%=*}; sed -i "/^$k=/d" "$DB"; echo "$2" >> "$DB" ;;
    unset) sed -i "/^$2=/d" "$DB" ;;
    show) cat "$DB" ;;
esac
exit 0
