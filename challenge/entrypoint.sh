#!/bin/sh
set -eu
python -m challenge.internal.engine &
exec python -m challenge.app.server
