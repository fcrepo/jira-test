#!/bin/bash

FCREPO_HOST=localhost
FCREPO_PORT=8080
FCREPO_CONTEXT=/fcrepo

which nc 2>&1 >  /dev/null
if [ $? != 0 ] ;
then
  echo "nc not found."
  exit 1
fi

if [ ! -z $1 ] ;
then
  FCREPO_HOST=$1
fi

if [ ! -z $2 ] ;
then 
  FCREPO_PORT=$2
fi

if [ ! -z $3 ] ;
then
  FCREPO_CONTEXT=$3
fi

# Thu, 18 Nov 2016 16:29:38 GMT
ONE_DAY_FROM_NOW=`date -v+1d -u "+%a, %d %b %Y %T %Z"`

nc ${FCREPO_HOST} ${FCREPO_PORT} <<EOF
GET ${FCREPO_CONTEXT}/rest HTTP/1.1
Host: foo
If-Modified-Since: ${ONE_DAY_FROM_NOW}  


EOF
