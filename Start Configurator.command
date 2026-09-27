#!/bin/sh
# macOS: double click to open the configurator; the first time it also sets
# up the Python tools. Same as start-configurator.sh, in a Terminal window.
cd "$(dirname "$0")" || exit 1
./start-configurator.sh "$@"
status=$?
if [ $status -ne 0 ]; then
    echo
    read -r -p "Press Return to close this window. " _
fi
exit $status
