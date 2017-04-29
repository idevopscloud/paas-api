#!/bin/bash
export PATH=/sbin:/usr/sbin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin

pull_imgs(){
    docker pull $img > /dev/null
}

rm_old_contains(){
    containers=`docker ps -a | egrep "${paas_api_cname}" | awk '{print $1}'`
    for c in $containers; do 
        echo "removing container: $c"
        docker rm -vf $c > /dev/null
    done
}

wait_for_service_ready()
{
  local PORT=$1
  attempt=0
  while true; do
    local ok=1
    curl --connect-timeout 3 http://localhost:$PORT > /dev/null 2>&1 || ok=0
    if [[ ${ok} == 0 ]]; then
      if (( attempt > 10 )); then
        echo "failed to start $PORT on localhost." 
        exit 1
      fi
    else
        echo "Attempt $(($attempt+1)) [$PORT running]"
      break
    fi
    echo "Attempt $(($attempt+1)): [$PORT not working yet]"
    attempt=$(($attempt+1))
    sleep 3 
  done
}

get_repo()
{
    if (( $# != 1 )); then
        echo "usage:    $0 repo(1:mainland, 2:oversea)"
        echo "e.g:      $0 mainland"
        exit 0
    fi

    repo=idevopscloud

    if [[ "$1" == "1" ]]; then
        repo=index.idevopscloud.com:5000/idevops
    elif [[ "$1" == "2" ]]; then
        repo=idevopscloud
    else
        echo "error repo type"
        exit 1
    fi
}

get_repo $*
img=${repo}/paas-api:1.1.1
paas_api_cname=ido-paas-api
#pull_imgs
rm_old_contains
docker run -d \
	-p 22306:12306 \
	-e ETCD_IP=10.141.10.36 \
	-e DOCKER_REGISTRY_URL=10.141.46.209:5002 \
	-e HEAT_USERNAME=admin \
	-e HEAT_AUTH_URL=http://10.141.10.36:35357/v2.0 \
	-e HEAT_IP=10.141.10.36 \
	-e K8S_IP=10.141.10.36 \
	-e HEAT_PASSWORD=ADMIN_PASS \
	--name=${paas_api_cname} $img

wait_for_service_ready 22306
