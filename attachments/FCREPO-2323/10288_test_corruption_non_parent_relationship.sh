#!/bin/bash

#############
# This shows the same corruption as "test_corruption.sh" but instead
# of resource 'b' being a child of the resource/container being updated
# to include a relationship to a hash URI (under 'b'), here the resource being update - resource 'a' - is 
# a sibling of 'b'. Resources 'a' and 'b' are under a common parent/container.
############# 

pfx="http://192.168.99.100:8080/fcrepo/rest/prod"
uuid=$(uuidgen)
container="${pfx}/${uuid}"

echo; echo; echo "Creating Container ${container}."
curl -iXPUT "${container}"

echo; echo; echo "Creating resource 'a' ${container}/a."
curl -iXPUT "${container}/a"

echo; echo; echo "Creating trouble resource 'b'."
curl -iXPUT "${container}/b"
echo; echo; echo "Creating harmless resource 'z'."
curl -iXPUT "${container}/z"

echo; echo; echo "Updating resource 'a' to include relationship to hash uri 'b#c'."
curl -iXPATCH -H'Content-Type:application/sparql-update' -d"DELETE {} INSERT {<> <http://www.iana.org/assignments/relation/first> <${container}/b#c> .} WHERE {}" "${container}/a"

echo; echo; echo "Let's see what the container - ${container} - looks like now."
curl -i "${container}"

echo; echo; echo "Let's see what resource 'a' - ${container}/a - looks like now."
curl -i "${container}/a"

echo; echo; echo "Let's see what resource 'b' looks like now."
curl -i -H "Prefer: return=representation; include=\"http://fedora.info/definitions/v4/repository#EmbedResources\";" "${container}/b"

echo; echo; echo "Deleting resource 'b'. This corrupts resource 'a'."
curl -XDELETE "${container}/b"

echo; echo; echo "Resource 'a' - ${container}/a - is now inaccessible via GET (404)..."
curl -i "${container}/a"

echo; echo; echo "But HEAD still looks OK!"
curl -I "${container}/a"

echo; echo; echo "For good measure, here is the container resource - ${container}"
curl -i "${container}"

echo; echo; echo "Also the second child is perfectly fine."
curl -i "${container}/z"


