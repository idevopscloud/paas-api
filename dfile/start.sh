#!/bin/bash

check_env_vars()
{
    if [ "$HEAT_USERNAME" == "" ]; then
        echo "[ERROR] HEAT_USERNAME is not specified"
        return 1
    fi
    if [ "$HEAT_PASSWORD" == "" ]; then
        echo "[ERROR] HEAT_PASSWORD is not specified"
        return 1
    fi
    if [ "$HEAT_AUTH_URL" == "" ]; then
        echo "[ERROR] HEAT_AUTH_URL is not specified"
        return 1
    fi
    if [ "$DOCKER_REGISTRY_URL" == "" ]; then
        echo "[ERROR] DOCKER_REGISTRY_URL is not specified"
        return 1
    fi
}

update_config_file()
{
    config_file="/ido/paas-api/config.py"
    rm -f $config_file

    echo "K8S_IP='$K8S_IP'" >> $config_file

    if [ "$HEAT_IP" != "" ]; then
        echo "HEAT_IP='$HEAT_IP'" >> $config_file
    fi
    if [ "$ETCD_IP" != "" ]; then
        echo "ETCD_IP='$ETCD_IP'" >> $config_file
    fi
    if [ "$ETCD_PORT" != "" ]; then
        echo "ETCD_PORT='$ETCD_PORT'" >> $config_file
    fi
    if [ "$HEAT_USERNAME" != "" ]; then
        echo "HEAT_USERNAME='$HEAT_USERNAME'" >> $config_file
    fi
    if [ "$HEAT_PASSWORD" != "" ]; then
        echo "HEAT_PASSWORD='$HEAT_PASSWORD'" >> $config_file
    fi
    if [ "$HEAT_AUTH_URL" != "" ]; then
        echo "HEAT_AUTH_URL='$HEAT_AUTH_URL'" >> $config_file
    fi
    if [ "$MAX_LOG_SIZE" != "" ]; then
        echo "MAX_LOG_SIZE='$MAX_LOG_SIZE'" >> $config_file
    fi
    if [ "$MAX_LOG_COUNT" != "" ]; then
        echo "MAX_LOG_COUNT='$MAX_LOG_COUNT'" >> $config_file
    fi
    if [ "$LOG_FILE" != "" ]; then
        echo "LOG_FILE='$LOG_FILE'" >> $config_file
    fi
    if [ "$PORT" != "" ]; then
        echo "PORT=$PORT" >> $config_file
    fi
    if [ "$DEBUG" != "" ]; then
        echo "DEBUG='$DEBUG'" >> $config_file
    fi
    if [ "$USE_THREAD" != "" ]; then
        echo "USE_THREAD='$USE_THREAD'" >> $config_file
    fi
    if [ "$BINDING_ADDR" != "" ]; then
        echo "BINDING_ADDR='$BINDING_ADDR'" >> $config_file
    fi
    if [ "$USE_RELOADER" != "" ]; then
        echo "USE_RELOADER='$USE_RELOADER'" >> $config_file
    fi
    if [ "$ACL" != "" ]; then
        echo "ACL='$ACL'" >> $config_file
    fi
    if [ "$DOCKER_REGISTRY_URL" != "" ]; then
        echo "DOCKER_REGISTRY_URL='$DOCKER_REGISTRY_URL'" >> $config_file
    fi
}

if ! (check_env_vars); then
    exit 1
fi

update_config_file
python /ido/paas-api/paas-api.pyc

