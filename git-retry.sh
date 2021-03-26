#!/usr/bin/env bash

for tries in {0..4}
do
    if ((tries)); then
        sleep_time=$((2**(tries-1) * 3))
        echo "Sleeping for $sleep_time until retry number $tries"
        sleep $sleep_time
    fi

    if git "$@"; then
        break
    fi
done
