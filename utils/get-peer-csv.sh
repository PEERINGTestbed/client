#!/bin/sh
set -eu

PEER_CSV_LINK="https://peering.usc.edu/peers/?report-bgppeertable=csv"
OUTPUT_FILE=peers.csv

wget -q -O $OUTPUT_FILE "$PEER_CSV_LINK"
