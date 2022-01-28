# shellcheck shell=bash

export CTX_NAME_PREFIX=revtr

export USER=cunha
export GROUP=cunha

export OUTDIR=revtr-ispy-exp-outdir/
export REMOTE_SCRIPTS_DIR=scripts/remote/

export BASE_TABLE=50
export SUPERPREFIX=184.164.224.0/19

export APIHOST=localhost
export APIPORT=8082
export APILOGDIR=/home/cunha/revtr_survey_peering/
export APIKEY=7vg3XfyGIJZL92Ql
export APITRACES=10

export REVTR_CONTROLLER_HOST=walter
export REVTR_DB_HOST=achtung17

export ATLAS_REFRESH_TIME=$((35*60))  # RIPE Atlas + RR
export CONTAINER_START_TIME=$((60))  # Docker
export CONVERGENCE_TIME=$((3*60))  # BGP
export REVTR_WAIT_TIME=$((15*60))  # RevTr (last batch only)

export REVTR_LABEL=revtr_ispy_test

declare -gA mux2octet
export mux2octet
mux2octet=([amsterdam01]=224
           [gatech01]=225
           [grnet01]=230)

declare -gA mux2id
export mux2id
mux2id=([amsterdam01]=5
        [clemson01]=16
        [gatech01]=6
        [grnet01]=9
        [isi01]=2
        [neu01]=14
        [phoenix01]=4
        [seattle01]=1
        [ufmg01]=7
        [ufms01]=18
        [utah01]=17
        [uw01]=10
        [wisc01]=11)
