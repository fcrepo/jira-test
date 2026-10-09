#!/bin/sh

BASE=http://localhost:8080/fedora/rest/migrate
FILES=/data/files

curl -X PUT $BASE && echo

# 400 obj x 5 pg x 100mb = 200gb
OBJECT_COUNT=400
PAGE_COUNT=5

FILE=1
OBJECT=0
while [ $OBJECT -lt $OBJECT_COUNT ]; do
  OBJ=$BASE/object-${OBJECT}

  # create object
  curl -X PUT -H "Content-type: text/turtle" -d @dummy.ttl $OBJ && echo

  # create indirect container for members
  curl -X PUT -H "Content-Type: text/turtle" -d "
    @prefix ore: <http://www.openarchives.org/ore/terms/> .
    @prefix ldp: <http://www.w3.org/ns/ldp#> .
    @prefix pcdm: <http://pcdm.org/models#> .
    <> a ldp:IndirectContainer ;
         ldp:hasMemberRelation pcdm:hasMember ;
         ldp:insertedContentRelation ore:proxyFor ;
         ldp:membershipResource <$OBJ> ." $OBJ/members && echo

  PAGE=0
  while [ $PAGE -lt $PAGE_COUNT ]; do
    # create fileset
    FILESET=$BASE/object-${OBJECT}-fileset-${PAGE}
    curl -X PUT $FILESET && echo

    # add metadata
    curl -X PATCH -H "Content-Type: application/sparql-update" -d "
      prefix dc: <http://purl.org/dc/elements/1.1/>
      insert { <> dc:title \"this is fileset # $PAGE\" } where { }" $FILESET

    # create direct container for files
    curl -X PUT -H "Content-Type: text/turtle" -d "
      @prefix ldp: <http://www.w3.org/ns/ldp#> .
      @prefix pcdm: <http://pcdm.org/models#> .
      <> a ldp:DirectContainer ;
           ldp:hasMemberRelation pcdm:hasFile ." $FILESET/files && echo

    # add a file to the container
    FN=$FILE
    FILE=$(( $FILE + 1 ))
    echo "ingesting file: $FILES/$FILE"

    curl -X PUT -d @$FILES/$FILE $FILESET/files/file1 && echo

    # add membership proxy
    curl -X PUT -H "Content-type: text/turtle" --data-binary "
      @prefix ore: <http://www.openarchives.org/ore/terms/> .
      <> a ore:Proxy ;
           ore:proxyFor <$FILESET> ;
           ore:proxyIn <$OBJ> ."  $OBJ/members/proxy-${PAGE} && echo

    PAGE=$(( $PAGE + 1 ))
  done

  OBJECT=$(( $OBJECT + 1 ))
done
