# shellcheck shell=bash

export CTX_NAME_PREFIX=revtr

export CDIR=/home/cunha/git/peering/client
export OPENVPN_DELAY_SEC=10

export USER=cunha
export GROUP=cunha

export OUTDIR=$CDIR/utils/reverse-traceroute/results/revtr-jc-exp
export REMOTE_SCRIPTS_DIR=$CDIR/utils/reverse-traceroute/scripts/remote/

export BASE_TABLE=-200
export SUPERPREFIX=184.164.224.0/19

export APIHOST=localhost
export APIPORT=8082
export APILOGDIR=/home/cunha/revtr_jc_exp/
export APIKEY=7vg3XfyGIJZL92Ql
export APITRACES=2000000000

export REVTR_CONTROLLER_HOST=walter
export REVTR_DB_HOST=achtung17

export ATLAS_REFRESH_TIME=$((40*60))  # RIPE Atlas + RR
export CONTAINER_START_TIME=$((2*60))  # Docker
export CONVERGENCE_TIME=$((25*60))  # BGP
export REVTR_WAIT_TIME=$((1*60))  # RevTr (last batch only)

export REVTR_LABEL=revtr_jc_exp1

export octets=(224 225 246 254)

export ANYCAST_UPSTREAM_MUX=amsterdam01

declare -gA mux2id
export mux2id
mux2id=([amsterdam01]=5
        [clemson01]=16
        [gatech01]=6
        [grnet01]=9
        [neu01]=14
        [seattle01]=1
        [utah01]=17
        [uw01]=10
        [wisc01]=11)
