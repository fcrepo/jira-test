#!/usr/bin/env bash

fedorauri="http://localhost:8080/rest/"

filename=`date +%s%N`.txt
echo "text" > $filename

echo "1) MD5, no transaction"
echo

objuri1=`curl -s -X POST --data-binary @$filename -H "digest: md5=e1cbb0c3879af8347246f12c559a86b5" "$fedorauri"`

# MD5 present
curl $objuri1/fcr:metadata

echo
echo "============================"
echo

echo "2) md5 in transaction"
echo

txresp2=$(curl -sD /dev/stdout -XPOST "$fedorauri/fcr:tx" | tr -d '\r' )
txuri2=`echo $txresp2 | sed -e "s/.*Location: //" -e "s/ .*//"`

txobjuri2=`curl -s -X POST --data-binary @$filename -H "digest: md5=e1cbb0c3879af8347246f12c559a86b5" "$txuri2"`

curl -X POST "$txuri2/fcr:tx/fcr:commit" 2>/dev/null

objuri2=`echo $txobjuri2 | sed -e 's/tx:[0-9a-f\-]*\///' 2>/dev/null`

# MD5 present
curl $objuri2/fcr:metadata

echo
echo "============================"
echo

echo "3) md5, inspection during transaction"
echo

txresp3=$(curl -sD /dev/stdout -XPOST "$fedorauri/fcr:tx" | tr -d '\r')
txuri3=`echo $txresp3 | sed -e "s/.*Location: //" -e "s/ .*//"`

txobjuri3=`curl -s -X POST --data-binary @$filename -H "digest: md5=e1cbb0c3879af8347246f12c559a86b5" "$txuri3"`

curl -s $txobjuri3/fcr:metadata > /dev/null

curl -X POST "$txuri3/fcr:tx/fcr:commit" 2>/dev/null

objuri3=`echo $txobjuri3 | sed -e 's/tx:[0-9a-f\-]*\///'`

# No MD5
curl $objuri3/fcr:metadata

rm $filename