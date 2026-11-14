#!/bin/sh
# Fetch the course harness (pinned) into ./harness. It is not committed here.
set -e
cd "$(dirname "$0")/.."
if [ ! -d harness/.git ]; then
  git clone https://github.com/Ryfernandes/megagem-harness.git harness
fi
git -C harness checkout -q 4675a29
echo "harness ready at $(git -C harness rev-parse --short HEAD)"
