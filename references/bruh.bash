#!/bin/bash

# Check for special case "bruh moment"
if [[ "$1" == "moment" ]]; then
  exec brh rollback "$@"
  exit
fi

# Otherwise, pass all arguments to brh
exec brh "$@"
