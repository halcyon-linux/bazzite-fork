# shellcheck disable=SC2148 sourced, not executed
# msedit is a friendlier default for interactive terminal editing than vim.

if [ -z "$EDITOR" ]; then
  export EDITOR=/usr/bin/msedit
fi
