from log import LOG
from common import etcd_client
import copy
import re
import json
import time
from common import kube_client
from event import Event

class Pod:
    def __init__(self, json_data):
        self.json_data = copy.deepcopy(json_data)
        self.mem_usage = -1          # unit is MBytes
        self.cpu_percentage = -1.0
        self.mem_limit = 0.0
        self.max_mem_limit = 0.0
        self.reason = None
        self.detailed_reason = None
        self.labels = self.json_data['metadata']['labels']
        try:
            mem_limit_str = self.json_data['spec']['containers'][0]['resources']['limits']['memory']
            self.mem_limit = self.get_mem_from_str(mem_limit_str)
            self.max_mem_limit = self.get_mem_from_str(mem_limit_str)
        except Exception, e:
            LOG.info(e)

        try:
            mem_request_str = self.json_data['spec']['containers'][0]['resources']['requests']['memory']
            self.mem_request = self.get_mem_from_str(mem_request_str)
        except Exception, e:
            LOG.info(e)

        try:
            key = '/paas/applications/{}/pods/{}'.format(self.namespace, self.name)
            result = etcd_client.read(key).value
            tmp_json = json.loads(result)
            if int(time.time()) - tmp_json['timestamp'] <= 60:
                self.mem_usage = tmp_json['stats']['memory']['usage'] / 1024 / 1024
                self.cpu_percentage = tmp_json['stats']['cpu']['cpu_percentage']
                if self.cpu_percentage is None:
                    self.cpu_percentage = -1.0
            else:
                LOG.warning('The record <{}>\'s timestamp <{}> is old'.format(key, tmp_json['timestamp']))
        except Exception, e:
            LOG.error(e)

        self.__get_reason()

    def get_mem_from_str(self, mem_str):
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

    @property
    def name(self):
        return self.json_data['metadata']['name']

    @property
    def component_name(self):
        return self.json_data['metadata']['labels']['name']

    @property
    def namespace(self):
        return self.json_data['metadata']['namespace']

    def is_ready(self):
        if self.is_running():
            if self.json_data['status']['conditions'][0]['status'] == 'True':
                return True
            return False
        else:
            return False

    def is_running(self):
        if self.status == "Running":
            return True
        return False
    
    @property
    def status(self):
        phase = self.json_data['status']['phase']
        if 'deletionTimestamp' in self.json_data['metadata']:
            return 'Terminating'
        elif phase == 'Pending' \
            and 'containerStatuses' in self.json_data['status'] \
            and 'waiting' in self.json_data['status']['containerStatuses'][0]['state']:
            return self.json_data['status']['containerStatuses'][0]['state']['waiting']['reason']
        else:
            return self.json_data['status']['phase']

    @property
    def host_IP(self):
        if 'nodeName' in self.json_data['spec']['containers'][0]:
            return self.json_data['spec']['containers']['nodeName']

        if 'hostIP' in  self.json_data['status']:
                return self.json_data['status']['hostIP']

        if 'nodeName' in self.json_data['spec']:
            return self.json_data['spec']['nodeName']

        return ""

    @property
    def pod_IP(self):
        if self.is_running():
            return self.json_data['status']['podIP']
        else:
            return ""

    @property
    def start_time(self):
        if self.is_running():
            return time.strptime(self.json_data['status']['startTime'], '%Y-%m-%dT%H:%M:%SZ')
        else:
            return None

    @property
    def create_time(self):
        return time.strptime(self.json_data['metadata']['creationTimestamp'], '%Y-%m-%dT%H:%M:%SZ')

    @property
    def restart_count(self):
        if self.is_running():
            return self.json_data['status']['containerStatuses'][0]['restartCount']
        else:
            return 0

    @property
    def version(self):
        try:
            return self.json_data['metadata']['labels']['version']
        except:
            return ""

    @property
    def image_ID(self):
        try:
            return self.json_data['status']['containerStatuses'][0]['containerID'][9:]
        except:
            return None

    def to_dict(self):
        return self.dump_as_dict()

    def dump_as_dict(self):
        cur_time = time.gmtime()
        ret = {
            'name': self.name,
            'is_ready': self.is_ready(),
            'is_running': self.is_running(),
            'status': self.status,
            'host_IP': self.host_IP,
            'pod_IP': self.pod_IP,
            'age': self.calc_time_delta(self.create_time, cur_time),
            'version': self.version,
            'restart_count': self.restart_count,
            'mem_limit': self.mem_limit,
            'max_mem_limit': self.max_mem_limit,
            'mem_request': self.mem_request,
            'mem_usage': self.mem_usage,
            'component_name': self.component_name,
            'cpu_percentage': self.cpu_percentage,
        }
        if self.reason is not None:
            ret['reason'] = self.reason
            ret['detailed_reason'] = self.detailed_reason

        return ret

    def calc_time_delta(self, time1, time2):
        str = ""
        delta = int(time.mktime(time2) - time.mktime(time1))
        days = delta / (3600 * 24)
        hours = delta / 3600
        mins = delta / 60
        seconds = delta
        if days > 0:
           str = "{}d".format(days)
        elif hours > 0:
           str = "{}h".format(hours)
        elif mins > 0:
           str = "{}m".format(mins)
        elif seconds > 0:
           str = "{}s".format(seconds)

        return str

    def __get_reason(self):
        if self.status != 'Pending':
            return

        elements = kube_client.GetEventsJson(namespace = self.namespace,
                                             involved_obj_kind = 'Pod',
                                             involved_obj_name = self.name)
        if elements is None:
            return

        event = Event(elements[-1])
        self.reason = event.reason
        self.detailed_reason = event.detailed_reason

