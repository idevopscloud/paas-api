#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

usage()
{
    echo "build.sh [-h] VERSION"
}

OPTS=`getopt -o "h" -- "$@"`
if [ $? != 0 ]; then
    echo "Usage error"
    exit 1
fi
eval set -- "$OPTS"

outdir=$DIR/target

while true ; do
    case "$1" in
        -h) usage; exit 0;; 
        --) shift; break;;
    esac
done

if [ $# != 1 ]; then
    usage
    exit 1
fi
version=$1

mkdir -p $outdir 2>&1>/dev/null
rm -rf $outdir/*

cp -r src $outdir && mv $outdir/src $outdir/paas-api
cd $outdir
python -m compileall paas-api
rm paas-api/*.py
tar cvf $outdir/paas-api.tar paas-api

cd $DIR
cp -r dfile $outdir
cp $outdir/paas-api.tar $outdir/dfile
cd $outdir/dfile
./build.sh $version
