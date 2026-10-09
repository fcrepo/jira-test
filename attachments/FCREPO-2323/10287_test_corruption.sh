#!/bin/bash

pfx="http://repo.example.edu/fcrepo/rest"
uuid=$(uuidgen)
container="${pfx}/${uuid}"

echo "Creating Container ${container}."
curl -iXPUT "${container}"
echo; echo; echo "Creating trouble resource."
curl -iXPUT "${container}/b"
echo; echo; echo "Creating harmless resource."
curl -iXPUT "${container}/z"
echo; echo; echo "Updating container with trouble link."
curl -iXPATCH -H'Content-Type:application/sparql-update' -d"DELETE {} INSERT {<> <http://www.iana.org/assignments/relation/first> <${container}/b#c> .} WHERE {}" "${container}"

echo; echo "This corrupts the parent container."
curl -XDELETE "${container}/b"

echo; echo; echo "The container  is now inaccessible  via GET (404)..."
curl -i "${container}"
echo; echo; echo "But HEAD still looks OK!"
curl -I "${container}"
echo "Also the second child is perfectly fine."
curl -i "${container}/z"

