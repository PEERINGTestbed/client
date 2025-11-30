#!/bin/bash
set -eu

function usage {
    cat <<HELP
usage: $0 -f <PIDFILE>

    PIDFILE: File with one PID to kill per line
HELP
    exit 0
}

function die {
    msg=$1
    status=$(( $2 ))
    echo "$msg"
    exit $status
}

pidfile=/dev/invalid

while getopts "f:h" OPT; do
case $OPT in
f)
    pidfile=$OPTARG
    ;;
h|*)
    usage
    ;;
esac
done
shift $(( OPTIND - 1 ))
OPTIND=1

if [[ ! -s $pidfile ]] ; then
    die "PIDFILE not set or does not exist" 1
fi

while read -r pid ; do
    kill $(( pid )) || true
done < "$pidfile"
