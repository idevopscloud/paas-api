import etcd
import kubernetes
import flask
import json
import uuid
import os
import datetime
from settings import settings
import time
import re

etcd_client = etcd.Client(host=settings.ETCD_IP, port=settings.ETCD_PORT)

base_url = 'http://%s:8080/api/v1' % (settings.K8S_IP)
kube_client = kubernetes.Api(base_url=base_url)

def make_status_response(code, message=''):
    response = flask.make_response(json.dumps({'kind': 'Status', 'code': code, 'message': message}), code)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers.pop('Server', None)
    response.status_code = code
    return response

def dump_app_json_into_file(namespace, content):
    DIR = '/tmp/paas'
    if not os.path.exists(DIR):
        os.mkdir(DIR)

    file_name = '{}/{}.{}'.format(DIR, datetime.datetime.now().strftime("%Y%m%d.%H%M%S.%f"), namespace)
    file_obj = file(file_name, 'w')
    file_obj.write(content)
    file_obj.close()
    return file_name

class TimeUtils:
    @staticmethod
    def convert_from_go_format(goTimeStr):
        ''' Convert go time str to python datetime '''
        return datetime.datetime.strptime(goTimeStr, '%Y-%m-%dT%H:%M:%SZ')

class MemUtils:
    @staticmethod
    def convert_from_k8s_format(mem_str):
        ''' unit of retrurned value is Mi '''
        match = re.match('^[0-9]*', mem_str)
        if match is None:
            return 0.0
        value = float(mem_str[match.start():match.end()])
        unit = mem_str[match.end():]
        if unit == 'Gi':
            value = value * 1024.0
        if unit == 'G':
            value = value * pow(10,9) / 1024 / 1024
        if unit == 'M':
            value = value * pow(10,6) / 1024 / 1024
        if unit == 'Mi':
            pass
        if unit == 'K':
            value = value * pow(10,3) / 1024 / 1024
        if unit == 'Ki':
            value = value / 1024

        return round(value,2)

def check_license(f):
    expired_date = datetime.date(2017, 12, 31)

    def wrapper(*args, **kwargs):
        today = datetime.date.today()
        if today > expired_date:
            return make_status_response(403, message='Your license has expried.')
        return f(*args, **kwargs)
    return wrapper

