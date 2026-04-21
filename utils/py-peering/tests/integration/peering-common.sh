export PREFIXES=(184.164.224.0/24 184.164.225.0/24)

function term {
    echo "$1"
    exit 1
}

function peering {
    ../../../../peering "$@"
}

function report_sc_ping_stats {
    local outdir=$1
    local sent recv
    while read -r warts; do
        stats=$(sc_warts2json "$warts" |
            jq -r -s '[.[]
                | select(.type == "ping")
                | {sent: .ping_sent, recv: .statistics.replies}
            ] | reduce .[] as $e ({sent:0,recv:0};
                {sent: (.sent + $e.sent), recv: (.recv + $e.recv)})
            | "\(.sent) \(.recv)"')
        sent=${stats%% *}
        recv=${stats##* }
        echo "$(basename "$warts"): $recv responses, $sent probes"
    done < <(find "$outdir" -name '*.warts.xz')
}
