#!/bin/bash

host="$1"
auth="$2:$3"

# Create initial container
curl -siu ${auth} -X PUT "${host}/stressTest"
# create 10,000 transactions
time for x in {0..10000}; do
	echo -e "\n\nCreating transaction #$x"

	export txuri=`curl -siu ${auth} -X POST ${host}/fcrepo/rest/fcr:tx | grep Location | cut -f2 -d' ' | tr -d '\r'`;
	echo "transaction: $txuri"

	# create a container within current txn
	node_ret=`curl -siu ${auth} -X POST "$txuri/stressTest" | grep 'HTTP/1.1' | tr -d '\r'`
	echo $node_ret
	
	curl -siu ${auth} -X POST "${txuri}/fcr:tx/fcr:commit"
done

