import traceback
from flask import Blueprint, request, render_template, flash, g, session, redirect, url_for
import requests
import flask
import json
from copy import deepcopy
import datetime
import time
import copy
from flask_restful import Resource
import etcd
import re
import timeit
from log import LOG
from common import *
from kubernetes import KubernetesError
from heatclient.exc import *
import acl
from heat import heat_client
from exception import *
import k8s
from settings import settings
from node import *

def timeit_func(f):
    def timed(*args, **kw):
        ts = time.time()
        result = f(*args, **kw)
        te = time.time()
        LOG.debug('func:%r took: %2.4f sec' % (f.__name__, te-ts))
        return result

    return timed

def get_rc_name_in_heat_resource(heat_res):
    rc_names = heat_res.physical_resource_id.split('->')
    if len(rc_names) > 1:
        return rc_names[1]
    else:
        return rc_names[0]

class ReplicationController:
    def __init__(self, stack_resource, rc_json=None):
        self.rc_json = copy.deepcopy(rc_json)
        self.stack_resource = stack_resource

        self.name = get_rc_name_in_heat_resource(stack_resource)
        self.selector = {}

        if rc_json is not None:
            self.component_name = self.rc_json['metadata']['labels']['name']
            self.selector = self.rc_json['spec']['selector']
        else:
            self.component_name = self.name.rsplit('-', 1)[0]

        if rc_json is not None:
            self.replicas = self.rc_json['spec']['replicas']
        else:
            self.replicas = 0
        self.pods = []
        self.svc = None

    def add_pods(self, pod_list):
        self.pods += pod_list

    def add_svc(self, svc):
        self.svc = svc

    def dump_as_dict(self):
        ret = {
            'name': self.name,
            'component_name': self.component_name,
            'replicas': self.replicas,
            'status': self.stack_resource.resource_status,
            'updated_time': self.stack_resource.updated_time,
            'pods': [ pod.dump_as_dict() for pod in self.pods ]
        }
        if self.svc is not None:
            ret['svc'] = self.svc.to_dict()
        return ret

class PaasApplication:
    @timeit_func
    def __init__(self, name, stack_json, stack_resource_list,
                 rc_list_json, pod_list_json, svc_list_json):
        self.rc_list = []
        self.name = name
        self.stack_json = copy.deepcopy(stack_json)

        if stack_resource_list is not None:
            pods = []
            svc_list = []
            
            for pod_json in pod_list_json:
                pod = k8s.Pod(pod_json)
                pods.append(pod)

            if svc_list_json is not None:
                for svc_json in svc_list_json:
                    svc_list.append(k8s.Service(svc_json))

            for stack_resource in stack_resource_list:
                if stack_resource.resource_type != 'GoogleInc::Kubernetes::ReplicationController' \
                    or stack_resource.physical_resource_id == "":
                    continue
                rc_json = self.__find_rc_in_list(rc_list_json, get_rc_name_in_heat_resource(stack_resource))
                rc = ReplicationController(stack_resource, rc_json)
                selected_pods = self.__select_pods_for_rc(rc, pods)
                selected_svc = self.__select_svc_for_rc(rc, svc_list)
                rc.add_pods(selected_pods)
                rc.add_svc(selected_svc)
                self.rc_list.append(rc)

    def __find_rc_in_list(self, rc_list_json, rc_name):
        for rc_json in rc_list_json:
            if rc_name == rc_json['metadata']['name']:
                return rc_json

        return None

    def __match_selector_and_labels(self, selector, labels):
        if len(selector) > len(labels):
            return False

        for key, val in selector.items():
            if val != labels.get(key, None):
                return False

        return True

    def __select_svc_for_rc(self, rc, svc_list):
        if rc is None or rc.rc_json is None or svc_list is None or len(svc_list) == 0:
            return None

        pod_labels = rc.rc_json['spec']['template']['metadata']['labels']
        for svc in svc_list:
            if self.__match_selector_and_labels(svc.selector, pod_labels):
                return svc
        return None

    def __select_pods_for_rc(self, rc, pods):
        selected_pods = []
        is_stack_create = (self.stack_json.get('stack_status')
                     in ['CREATE_COMPLETE', 'CREATE_IN_PROGRESS'])
        for pod in pods:
            if is_stack_create and pod.status == 'Terminating':
                continue 
            if 'name' in pod.labels and 'name' in rc.selector and pod.labels['name'] == rc.selector['name']:
                selected_pods.append(pod)

        for pod in selected_pods:
            pods.remove(pod)

        return selected_pods

    def dump_as_dict(self):
        return {
            'name': self.name,
            'stack_info': self.stack_json,
            'components': [rc.dump_as_dict() for rc in self.rc_list]
        }

def get_application_name_list():
    stacks = heat_client.get_stack_list()
    return [ stack.stack_name for stack in stacks ]

@timeit_func
def get_application(application_name, is_summary=False):
    if not is_summary:
        session = requests.session()
        url = 'http://{}:8080/api/v1/namespaces/{}/pods'.format(settings.K8S_IP, application_name)
        reply = session.get(url)
        pod_list_json = reply.json()['items']

        url = 'http://{}:8080/api/v1/namespaces/{}/replicationcontrollers'.format(settings.K8S_IP, application_name)
        reply = session.get(url)
        rc_list_json = reply.json()['items']

        url = 'http://{}:8080/api/v1/namespaces/{}/services'.format(settings.K8S_IP, application_name)
        reply = session.get(url)
        svc_list_json = reply.json()['items']

    try:
        stack = heat_client.get_stack(application_name)
        stack_json = stack.to_dict()
        if not is_summary:
            paas_app = PaasApplication(application_name,
                                       stack_json,
                                       heat_client.get_resource_list(application_name),
                                       rc_list_json,
                                       pod_list_json,
                                       svc_list_json)
        else:
            paas_app = PaasApplication(application_name, stack_json, None, None, None, None)
        return paas_app
    except Exception, e:
        LOG.error(e)
        LOG.error(traceback.format_exc())
        return None

class Application(Resource):
    @check_license
    def get(self, application_name):
        LOG.info('Getting application <%s>' % (application_name))
        is_summary = False
        if 'summary' in request.args and request.args['summary'].upper() == 'Y':
            is_summary = True
        paas_app = get_application(application_name, is_summary)
        if paas_app:
            application_json = paas_app.dump_as_dict()
            application_json['kind'] = 'Application'

            response = flask.make_response(json.dumps(application_json))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        else:
            return make_status_response(404, 'The application <{}> does not exist'.format(application_name))

    @check_license
    def delete(self, application_name):
        if not acl.check_acl('', __name__, 'd'):
            LOG.warning('DELETE application<{}> is rejected'.format(application_name))
            return make_status_response(403, 'Access denied')

        LOG.info('Deleting application <%s>' % (application_name))
        try:
            heat_client.delete_stack(application_name)
        except HTTPNotFound, e:
            LOG.warning(e)
            return make_status_response(404, str(e))
        except Exception, e:
            return make_status_response(500, 'Internal error')
        else:
            return make_status_response(200)

    def options(self, application_name):
        response = flask.make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'DELETE'
        return response

class RCResReq:
    '''
    ReplicationController resource requirement
    '''
    def __init__(self, rc_name, mem_request = None, cpu_request = None, node_selector = None):
        self.rc_name = rc_name
        self.mem_request = mem_request
        self.cpu_request = cpu_request
        self.node_selector = node_selector

class ApplicationList(Resource):
    def is_heat_template_valid(self, template):
        '''
        Check if a given template is valid or not.
        Currently it only checkes if namespace of all components are the same.
        '''
        return True

    @check_license
    def get(self):
        LOG.info('get ApplicationList')
        is_summary = False
        if 'summary' in request.args and request.args['summary'].upper() == 'Y':
            is_summary = True
        app_json_list = []
        try:
            names = get_application_name_list()
            for name in names:
                app_json_list.append(get_application(name, is_summary).dump_as_dict())
        except Exception as e:
            LOG.error(e)
            return make_status_response(500, 'Internal error')

        response_json = {'kind': 'ApplicationList', 'items': app_json_list}
        response = flask.make_response(json.dumps(response_json))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    @check_license
    def post(self):
        ''' create an application '''
        template = request.get_json()
        if template is None:
            return make_status_response(400, 'Bad application template')

        namespace = None
        try:
            namespace = self.get_namespace_from_template(template)
        except BadAppTemplate as e:
            LOG.warning(e.message)
            return make_status_response(400, e.message)
        except:
            LOG.warning(e.message)
            return make_status_response(400, 'Bad application template')
        finally:
            temp_file = dump_app_json_into_file(namespace, json.dumps(template, indent=2))
            LOG.info('dump template into ' + temp_file)

        try:
            # ops platform may attach a field 'token'
            template.pop('token')
        except:
            pass

        if not self.__is_sys_mem_enough(template):
            return make_status_response(403, 'Memory is not enough')

        LOG.info("Creating application <%s>" % (namespace))

        stack = None
        try:
            stack = heat_client.get_stack(namespace)
        except HTTPNotFound:
            # The stack does not exist
            pass
        except Exception, e:
            return make_status_response(500, 'Internal error')

        if stack is not None:
            if not acl.check_acl('', 'Application', 'u'):
                LOG.warning('UPDATE application<{}> is rejected'.format(namespace))
                make_status_response(403, 'Access denied')
            elif stack.status != 'COMPLETE' and stack.status != 'FAILED':
                LOG.warning('UPDATE application <{}> is rejected'.format(namespace))
                return make_status_response(403, 'UPDATE application <{}> is rejected because its status is {}_{}'.format(namespace, stack.action, stack.status))
            try:
                heat_client.update_stack(namespace, template)
            except Exception as e:
                LOG.error('Failed to update stack <{}>. Error message is: {}'.format(namespace, str(e)))
                message = ''
                if 'CircularDependencyException' in str(e):
                    message = 'found Circulard Dependency'
                return make_status_response(400, message)
        else:
            try:
                heat_client.create_stack(namespace, template)
            except Exception as e:
                LOG.error('Failed to create stack <{}>. Error message is: {}'.format(namespace, str(e)))
                message = ''
                if 'CircularDependencyException' in str(e):
                    message = 'found Circulard Dependency'
                return make_status_response(400, message)
        
        return make_status_response(200)

    def get_namespace_from_template(self, template):
        namespace = None
        for res_name, res_data in template['resources'].items():
            if 'namespace' not in res_data['properties']:
                raise BadAppTemplate('namespace is not specified in resource {}'.format(res_name))
            if namespace is None:
                namespace = res_data['properties']['namespace']
            if res_data['properties']['namespace'] != namespace:
                raise BadAppTemplate('more than one namespaces are specified')
        if namespace is None:
            raise BadAppTemplate('namespace is not specified')

        return namespace

    def __is_res_req_match_node(self, res_req, node):
        if res_req.node_selector is None:
            return False

        if len(res_req.node_selector) <= node.labels:
            keys = res_req.node_selector.keys()
            for key in keys:
                if key not in node.labels or res_req.node_selector[key] != node.labels[key]:
                    return False
            return True
        else:
            return False

    def __is_sys_mem_enough(self, template):
        components_res_req = self.__get_components_res_req(template)
        components_res_req.sort(cmp=lambda x,y: cmp(x.mem_request, y.mem_request))
        no_selector_res_req_list = []

        nodes = get_node_list()
        for res_req in components_res_req:
            schedulable = False
            for node in nodes:
                if self.__is_res_req_match_node(res_req, node):
                    node.mem_request_used += res_req.mem_request
                    if node.mem_request_used <= node.mem['total']:
                        schedulable = True

            if res_req.node_selector is not None and not schedulable:
                return False

            # TODO: check if the res_req has nodeSelector but no node matched
            
            if res_req.node_selector is None:
                no_selector_res_req_list.append(res_req)

        if len(no_selector_res_req_list) == 0:
            return True

        for node in nodes:
            print node.mem_request_used, node.mem['total']-node.mem_request_used, no_selector_res_req_list[-1].mem_request
            if node.mem_request_used + no_selector_res_req_list[-1].mem_request <= node.mem['total']:
                return True

        return False

    def __get_components_res_req(self, template, is_update=False):
        ''' get mem request of all components '''

        components_res_req = list()
        for key, value in template['resources'].items():
            if value['type'] != 'GoogleInc::Kubernetes::ReplicationController':
                continue
            mem_request = None
            mem_limit = None
            node_selector = None
            replicas = 1
            batch_percentage = 50

            try:
                batch_percentage = value['properties']['rolling_updates']['batch_percentage']
            except Exception as e:
                pass

            try:
                mem_request = MemUtils.convert_from_k8s_format(value['properties']['definition']['spec']['template']['spec']['containers'][0]['resources']['requests']['memory'])
            except ValueError as e:
                pass
            try:
                mem_limit = MemUtils.convert_from_k8s_format(value['properties']['definition']['spec']['template']['spec']['containers'][0]['resources']['limits']['memory'])
            except Exception as e:
                pass
            if mem_request is None:
                mem_request = mem_limit

            try:
                node_selector = value['properties']['definition']['spec']['template']['spec']['nodeSelector']
            except Exception as e:
                pass

            try:
                replicas = value['properties']['definition']['spec']['template']['replicas']
            except Exception as e:
                pass

            if is_update:
                step = replicas * batch_percentage / 100
                if step == 0:
                    step = 1

                components_res_req.append(RCResReq(key, mem_request * step, None, node_selector))
            else:
                for i in range(replicas):
                    components_res_req.append(RCResReq(key, mem_request, None, node_selector))

        return components_res_req

class ApplicationPod(Resource):
    @check_license
    def delete(self, application_name, pod_name):
        if not acl.check_acl('', __name__, 'd'):
            LOG.warning('DELETE pod<{}> of application<{}> is rejected'.format(pod_name, application_name))
            return make_status_response(403, 'Access denied')

        try:
            kube_client.DeletePods(pod_name, namespace=application_name)
        except KubernetesError, e:
            LOG.error("failed to delete pod <%s> of application <%s>" % (pod_name, application_name))
            return make_status_response(404, e.message)

        return make_status_response(200)

    def options(self, application_name, pod_name):
        response = flask.make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'DELETE'
        return response

class ApiApplicationActions(Resource):
    @check_license
    def post(self, app_name):
        if 'action' not in request.args or request.args['action'] != 'cancel_update':
            return make_status_response(400, 'Invalid action')

        stack = None
        try:
            if not heat_client.is_stack_existed(app_name):
                return make_status_response(404, '{} is not running'.format(app_name))
        except Exception as e:
            LOG.error(str(e))
            return make_status_response(500, 'Internal error')

        try:
            heat_client.cancel_update(app_name)
        except HTTPNotFound:
            return make_status_response(404, '{} is not running'.format(app_name))
        except HTTPBadRequest:
            return make_status_response(400)
        except Exception, e:
            LOG.error(str(e))
            return make_status_response(500, 'Internal error')

        return make_status_response(200)

class ApiApplicationTemplate(Resource):
    @check_license
    def get(self, app_name):
        try:
            template = heat_client.get_stack_template(app_name)

            data = {
                'kind': 'ApplicationTemplate',
                'name': app_name,
                'template': template
            }

            response = flask.make_response(json.dumps(data))
            return response
        except HTTPNotFound as e:
            return make_status_response(404, 'The application <{}> is not running'.format(app_name))
        except Exception as e:
            return make_status_response(500, 'Internal error')

