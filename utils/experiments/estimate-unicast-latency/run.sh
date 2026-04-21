#!/bin/bash
set -eu

 echo "Starting Run 1"
 echo "######################################################################"
 ./phaseX_cascading_subsets.py
 mv phaseX_cascading_subsets isoc_cascading_subsets_run1
 echo "Starting Run 2"
 echo "######################################################################"
 ./phaseX_cascading_subsets.py
 mv phaseX_cascading_subsets isoc_cascading_subsets_run2
 echo "Starting Run 3"
 echo "######################################################################"
 ./phaseX_cascading_subsets.py
 mv phaseX_cascading_subsets isoc_cascading_subsets_run3


# echo "Starting Run 1"
# echo "######################################################################"
# ./phaseX_amsterdam_ixps.py
# mv phaseX_amsterdam_ixps isoc_amsterdam_ixps_run1
# echo "Starting Run 2"
# echo "######################################################################"
# ./phaseX_amsterdam_ixps.py
# mv phaseX_amsterdam_ixps isoc_amsterdam_ixps_run2
# echo "Starting Run 3"
# echo "######################################################################"
# ./phaseX_amsterdam_ixps.py
# mv phaseX_amsterdam_ixps isoc_amsterdam_ixps_run3

