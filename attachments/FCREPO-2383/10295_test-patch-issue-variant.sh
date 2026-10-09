#!/bin/bash

#############
# Fedora fails to delete triples when two WHERE patterns both match multiple triples.
# There are 4 PATCH requests below, all of which delete triples.
# The first two PATCH requests succeed.
# The second two fail.
# This file employs this sparql delete pattern: DELETE WHERE {}
#
# 461 - Last two PATCH requests result in 400 Bad Request errors and triples are not deleted.
# 470 - Last two PATCH requests result in 400 Bad Request errors and triples are not deleted.
# 471-rc2 - Last two PATCH requests result in 400 Bad Request errors and triples are not deleted.
############# 

pfx="http://192.168.99.100:8080/fcrepo/rest/prod"
pfx="http://localhost:8090/rest"
uuid=$(uuidgen)
resource="${pfx}/${uuid}"


insert='INSERT DATA {
  
  <> <http://example.org/test/x> "x" . 
  <> <http://example.org/test/y> "y" . 

  <> <http://example.org/test/a> "1" . 
  <> <http://example.org/test/a> "2" . 
  <> <http://example.org/test/a> "3" . 
  <> <http://example.org/test/a> "4" . 

  <> <http://example.org/test/b> "1" . 
  <> <http://example.org/test/b> "2" . 
  <> <http://example.org/test/b> "3" . 
  <> <http://example.org/test/b> "4" . 

  <> <http://example.org/test/c> "1" . 
  <> <http://example.org/test/c> "2" . 
  <> <http://example.org/test/c> "3" . 
  <> <http://example.org/test/c> "4" . 

}'

delete01='DELETE WHERE 
{ 
	<> <http://example.org/test/x> ?x .
	<> <http://example.org/test/y> ?y .
}'

delete02='DELETE WHERE 
{ 
	<> <http://example.org/test/b> ?b .
	<> <http://example.org/test/x> ?x .
}'

delete03='DELETE WHERE 
{ 
	<> <http://example.org/test/a> ?a .
	<> <http://example.org/test/b> ?b .
}'

# Switched the order of the WHERE clause.
delete04='DELETE WHERE 
{ 
	<> <http://example.org/test/b> ?b .
	<> <http://example.org/test/a> ?a .
}'


echo; echo; echo; echo; echo; echo; echo; echo; 

echo; echo; echo "Creating resource ${resource}."
curl -iXPUT "${resource}"

echo; echo; echo "Inserting some data with PATCH."
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${insert}" "${resource}"

echo; echo; echo "Let's see what the resource - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "Deleting some triples with PATCH"
echo "QUERY: $delete01"
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${delete01}" "${resource}"

echo; echo; echo "Let's see what the container - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "x and y should be gone."
echo; echo; echo; echo; echo; echo; echo; echo; 


uuid=$(uuidgen)
resource="${pfx}/${uuid}"

echo; echo; echo; echo; echo; echo; echo; echo; 

echo; echo; echo "Creating resource ${resource}."
curl -iXPUT "${resource}"

echo; echo; echo "Inserting some data with PATCH."
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${insert}" "${resource}"

echo; echo; echo "Let's see what the resource - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "Deleting some triples with PATCH"
echo "QUERY: $delete02"
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${delete02}" "${resource}"

echo; echo; echo "Let's see what the container - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "x and b should be gone."
echo; echo; echo; echo; echo; echo; echo; echo; 



uuid=$(uuidgen)
resource="${pfx}/${uuid}"

echo; echo; echo; echo; echo; echo; echo; echo; 

echo; echo; echo "Creating resource ${resource}."
curl -iXPUT "${resource}"

echo; echo; echo "Inserting some data with PATCH."
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${insert}" "${resource}"

echo; echo; echo "Let's see what the resource - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "Deleting some triples with PATCH"
echo "QUERY: $delete03"
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${delete03}" "${resource}"

echo; echo; echo "Let's see what the container - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "a and b should be gone, but they're not.  PATCH with the 'DELETE' returned 400 Bad Request on 471-rc2."
echo; echo; echo; echo; echo; echo; echo; echo; 



uuid=$(uuidgen)
resource="${pfx}/${uuid}"

echo; echo; echo; echo; echo; echo; echo; echo; 

echo; echo; echo "Creating resource ${resource}."
curl -iXPUT "${resource}"

echo; echo; echo "Inserting some data with PATCH."
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${insert}" "${resource}"

echo; echo; echo "Let's see what the resource - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "Deleting some triples with PATCH"
echo "QUERY: $delete04"
curl -iXPATCH -H "Content-Type: application/sparql-update" -d "${delete04}" "${resource}"

echo; echo; echo "Let's see what the container - ${resource} - looks like now."
curl "${resource}"

echo; echo; echo "a and b should be gone, but they're not.  PATCH with the 'DELETE' returned 400 Bad Request on 471-rc2."
echo; echo; echo; echo; echo; echo; echo; echo; 



