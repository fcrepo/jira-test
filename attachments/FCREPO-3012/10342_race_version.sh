#!/bin/bash
FEDORA_URL="http://localhost:8080/rest"
ADMIN_USER="fedoraAdmin"
ADMIN_PASS="fedoraAdmin"

function checkCode() {
  if [ "$1" != "$2" ]; then
    echo "Error $1 != $2"
  else
    echo "Passed $1 == $2"
  fi
}

CURL_OPTS="-s -o /dev/null --write-out %{http_code} --no-keepalive"

echo "Check if jareds_test exists"
RES=$(curl $CURL_OPTS -u$ADMIN_USER:$ADMIN_PASS $FEDORA_URL/jareds_test)
if [ "200" -ne "$RES" ]; then
    echo "Create jareds_test binary"
    RES=$(curl $CURL_OPTS -u$ADMIN_USER:$ADMIN_PASS -H"Link: <http://www.w3.org/ns/ldp#NonRDFSource>; rel=\"type\"" -H"Content-type: text/plain" -d"This is some content" -XPUT $FEDORA_URL/jareds_test)
    checkCode 201 $RES
fi
echo "Make a version of the binary"
RES=$(curl $CURL_OPTS -u$ADMIN_USER:$ADMIN_PASS -XPOST $FEDORA_URL/jareds_test/fcr:versions)
checkCode 201 $RES
echo "Make a version of the description"
RES=$(curl $CURL_OPTS -u$ADMIN_USER:$ADMIN_PASS -XPOST $FEDORA_URL/jareds_test/fcr:metadata/fcr:versions)
checkCode 201 $RES

echo "Wait a second"
sleep 1
echo "Now try in reverse order"
echo "Make a version of the description"
RES=$(curl $CURL_OPTS -u$ADMIN_USER:$ADMIN_PASS -XPOST $FEDORA_URL/jareds_test/fcr:metadata/fcr:versions)
checkCode 201 $RES
echo "Make a version of the binary"
RES=$(curl $CURL_OPTS -u$ADMIN_USER:$ADMIN_PASS -XPOST $FEDORA_URL/jareds_test/fcr:versions)
checkCode 201 $RES

