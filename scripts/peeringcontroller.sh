#!/bin/bash
# generates config blob for peeringmon_controller
# sudo ./peering openvpn status | sh scripts/peeringcontroller.sh 

# Read input from stdin and process each line
while IFS= read -r line; do
    # Extract required fields using awk
    id=$(echo "$line" | awk '{print $2}' | sed 's/tap//')
    name=$(echo "$line" | awk '{print $1}')
    ip=$(echo "$line" | awk '{print $4}')
    
    # Calculate the neighbor IP by replacing the last octet with 1
    neighbor=$(echo "$ip" | sed 's/\.[0-9]*$/\.1/')
    
    # Print the formatted output
    echo "{ id = $id, name = \"$name\", neighbor = \"$neighbor\", asn = 47065 },"
done

