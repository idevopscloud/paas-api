FROM index.idevopscloud.com:5000/idevops_base/paas-api-base:1.0
MAINTAINER idevopscloud/Jeff

ADD install.sh /tmp/
ADD paas-api.tar /ido/
ADD start.sh /
ADD python-kubernetes.tar /usr/local/lib/python2.7/dist-packages/
RUN bash /tmp/install.sh
CMD [ "bash", "/start.sh" ]
