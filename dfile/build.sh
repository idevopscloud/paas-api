#!/bin/bash
#
# output:
#   $registry/idevops/paas-api:$version
#

registry="index.idevopscloud.com:5000/idevops"
version=""
python_kubernetes_version="0.8.1"

usage()
{
    echo "build.sh [--registry] VERSION"
}

OPTS=`getopt -o "h" -l registry: -l -- "$@"`
if [ $? != 0 ]; then
    echo "Usage error"
    exit 1
fi
eval set -- "$OPTS"

while true ; do
    case "$1" in
        -h) usage; exit 0;; 
        --registry) registry=$2; shift 2;; 
        --) shift; break;;
    esac
done

if [[ $# != 1 ]]; then
    usage
    exit 1
fi

version=$1

git clone git@bitbucket.org:idevops/python-kubernetes.git
cd python-kubernetes && git checkout ${python_kubernetes_version}
tar cvf python-kubernetes.tar kubernetes
cp python-kubernetes.tar ../
cd ..

if [ "$registry" == "" ]; then
    image="idevopscloud/paas-api:$version"
    docker build -t $image ./
else
    image="$registry/paas-api:$version"
    docker build -t $image ./
    docker push $image
fi

