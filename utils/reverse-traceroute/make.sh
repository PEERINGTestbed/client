#!/bin/bash
set -eu

PEERING=$(cd ../../ ; pwd)
REVTR=$(cd ../../../../measurements/revtr ; pwd)

cat "$PEERING/requirements.txt" "$REVTR/requirements.txt" > requirements.txt
pip install -r requirements.txt

