#!/usr/bin/bash

for askpass_helper in /usr/bin/ssh-askpass /usr/libexec/openssh/ssh-askpass; do
  if [[ -x "$askpass_helper" ]]; then
    export SUDO_ASKPASS="$askpass_helper"
    break
  fi
done
