#!/bin/bash
while true
do
    curl -X PATCH -H "Content-Type: application/sparql-update" -d "INSERT {<> a <http://example.org/whatever>} WHERE {}" http://localhost:8080/rest/
done
