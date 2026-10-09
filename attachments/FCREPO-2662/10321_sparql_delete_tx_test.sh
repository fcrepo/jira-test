#!/bin/bash

fedora_uri="http://localhost:8080/rest/"

delete_query_file=`date +%s%N`.sparql
echo "DELETE { <> <http://purl.org/dc/elements/1.1/relation> ?obj . }
 WHERE { <> <http://purl.org/dc/elements/1.1/relation> ?obj }" > $delete_query_file

function make_relation_ttl {
  query_file=rels_`date +%s%N`.ttl
  echo "<> <http://purl.org/dc/elements/1.1/relation> <$1>" > $query_file
  echo $query_file
}

function create_obj_with_relation {
  rels_ttl_file=$(make_relation_ttl $1)

  obj_uri=`curl -s -XPOST --data-binary "@$rels_ttl_file" -H "Content-type: text/turtle" "$2"`
  
  rm $rels_ttl_file
  echo $obj_uri
}

function start_tx {
  tx_resp=$(curl -sD /dev/stdout -XPOST "$fedora_uri/fcr:tx" | tr -d '\r' )
  tx_uri=`echo $tx_resp | sed -e "s/.*Location: //" -e "s/ .*//"`
  echo $tx_uri
}

function delete_relations {
  $(curl -s -XPATCH --data-binary "@$delete_query_file" -H "Content-type: application/sparql-update" "$1")
}

function check_result {
  obj_model=$(curl -s $1)
  #echo $obj_model
  
  if [[ $obj_model != *"Container"* ]]
  then
    echo "Unexpected response:"
    echo $obj_model
    return
  fi
  
  if [[ $obj_model =~ .*relation.* ]]
  then
    echo "- dc:relation unexpectedly retained"
  else
    echo "+ dc:relation was deleted"
  fi
}

echo
echo "1) Delete query with no TX"
echo

obj_uri_1=`curl -s -XPOST "$fedora_uri"`
obj_uri_2=$(create_obj_with_relation $obj_uri_1 $fedora_uri)

delete_relations $obj_uri_2

check_result $obj_uri_2


echo
echo "2) Delete query in TX, objects created out of TX"
echo

obj_uri_1=`curl -s -XPOST "$fedora_uri"`
obj_uri_2=$(create_obj_with_relation $obj_uri_1 $fedora_uri)

tx_uri=$(start_tx)

obj_2_tx_uri="${obj_uri_2/$fedora_uri/$tx_uri/}"
#echo $obj_2_tx_uri
delete_relations $obj_2_tx_uri

check_result $obj_2_tx_uri


echo
echo "3) Delete query in TX, subject created in tx, object before tx"
echo

obj_uri_1=`curl -s -XPOST "$fedora_uri"`

tx_uri=$(start_tx)
obj_1_tx_uri="${obj_uri_2/$fedora_uri/$tx_uri/}"
# Reference the object as part of the transaction
obj_uri_2=$(create_obj_with_relation $obj_1_tx_uri $tx_uri)

#echo $obj_2_tx_uri
delete_relations $obj_uri_2

check_result $obj_uri_2


echo
echo "4) Delete query in TX, subject created before tx, object created in tx"
echo

obj_uri_2=`curl -s -XPOST "$fedora_uri"`

tx_uri=$(start_tx)
obj_uri_1=`curl -s -XPOST "$tx_uri"`

insert_query_file=insert_`date +%s%N`.sparql
echo "DELETE {}
 INSERT { <> <http://purl.org/dc/elements/1.1/relation> <$obj_uri_1> . }
 WHERE {}" > $insert_query_file

# Add the relation to the subject within the tx
obj_2_tx_uri="${obj_uri_2/$fedora_uri/$tx_uri/}"
$(curl -s -XPATCH --data-binary "@$insert_query_file" -H "Content-type: application/sparql-update" "$obj_2_tx_uri")

delete_relations $obj_2_tx_uri

check_result $obj_2_tx_uri

rm $insert_query_file

echo
echo "5) Delete query in TX, subject and object created in tx"
echo

tx_uri=$(start_tx)

obj_uri_1=`curl -s -XPOST "$tx_uri"`
obj_uri_2=$(create_obj_with_relation $obj_uri_1 $tx_uri)

#echo $obj_2_tx_uri
delete_relations $obj_uri_2

check_result $obj_uri_2

echo

rm $delete_query_file


#
# filename=`date +%s%N`.txt
# echo "text" > $filename
#
# echo "1) MD5, no transaction"
# echo
#
# objuri1=`curl -s -X POST --data-binary @$filename -H "digest: md5=e1cbb0c3879af8347246f12c559a86b5" "$fedorauri"`
#
# # MD5 present
# curl $objuri1/fcr:metadata
#
# echo
# echo "============================"
# echo
#
# echo "2) md5 in transaction"
# echo
#
# txresp2=$(curl -sD /dev/stdout -XPOST "$fedorauri/fcr:tx" | tr -d '\r' )
# txuri2=`echo $txresp2 | sed -e "s/.*Location: //" -e "s/ .*//"`
#
# txobjuri2=`curl -s -X POST --data-binary @$filename -H "digest: md5=e1cbb0c3879af8347246f12c559a86b5" "$txuri2"`
#
# curl -X POST "$txuri2/fcr:tx/fcr:commit" 2>/dev/null
#
# objuri2=`echo $txobjuri2 | sed -e 's/tx:[0-9a-f\-]*\///' 2>/dev/null`
#
# # MD5 present
# curl $objuri2/fcr:metadata
#
# echo
# echo "============================"
# echo
#
# echo "3) md5, inspection during transaction"
# echo
#
# txresp3=$(curl -sD /dev/stdout -XPOST "$fedorauri/fcr:tx" | tr -d '\r')
# txuri3=`echo $txresp3 | sed -e "s/.*Location: //" -e "s/ .*//"`
#
# txobjuri3=`curl -s -X POST --data-binary @$filename -H "digest: md5=e1cbb0c3879af8347246f12c559a86b5" "$txuri3"`
#
# curl -s $txobjuri3/fcr:metadata > /dev/null
#
# curl -X POST "$txuri3/fcr:tx/fcr:commit" 2>/dev/null
#
# objuri3=`echo $txobjuri3 | sed -e 's/tx:[0-9a-f\-]*\///'`
#
# # No MD5
# curl $objuri3/fcr:metadata
#
# rm $filename