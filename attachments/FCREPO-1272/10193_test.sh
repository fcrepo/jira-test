#!/bin/bash

host="localhost:8080/ff"

# Create initial container
curl -s -X PUT "${host}/stressTest"

# create 10,000 transactions
time for x in {0..10000}; do
  echo -e "\n\nCreating transaction #$x"

  export txuri=`curl -si -X POST ${host}/rest/fcr:tx | grep Location | cut -f2 -d' '`;
  echo "transaction: $txuri"

  # create a container within current txn
  node_ret=`curl -s -X POST "$txuri/stressTest"`
  echo $node_ret
  
  curl -si -X POST "${txuri}/fcr:tx/fcr:commit"
done
