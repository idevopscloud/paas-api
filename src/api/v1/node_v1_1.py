from flask import request
import flask
from common import *
import etcd
from flask_restful import Resource
import json
import copy
from kubernetes import KubernetesError, ResourceType
from exception import *
from log import LOG
import os


class PaasNode:
    def __init__(self, node_spec, node_status):
        public_addr = node_spec.labels.get('idevops.node.public-address', None)

        self.data = {
            'name': node_spec.name,
            'labels': copy.deepcopy(node_spec.labels),
            'IP': node_status['name'],
            'ready': node_spec.is_ready(),
            'unschedulable': node_spec.spec.unschedulable,
            'public_address': public_addr if public_addr else node_spec.name
        }
        self.data.update(node_status)

    def dump_as_dict(self):
        return self.data


def get_node_list():
    node_list = kube_client.GetNodes()
    node_dict = {node.name: node for node in node_list}

    key = '/paas/nodes/1.1'
    ret = list()
    try:
        value = etcd_client.read(key)
    except etcd.EtcdKeyNotFound as e:
        return ret

    for sub_item in value._children:
        raw = json.loads(sub_item['value'])
        if raw['name'] not in node_dict:
            continue

        paas_node = PaasNode(node_dict[raw['name']], raw)
        ret.append(paas_node)

    return ret


def get_node(name):
    k8s_nodes = kube_client.GetNodes()
    k8s_node = None
    for item in k8s_nodes:
        if item.name == name:
            k8s_node = item
            break
    if k8s_node is None:
       raise NodeNotFound(name)

    key = '/paas/nodes/1.1/{}'.format(name)
    value = etcd_client.read(key).value
    return PaasNode(k8s_node, json.loads(value))

def get_master_list():
    ret = list()
    try:
        value = etcd_client.read('/paas/masters/1.1')
    except etcd.EtcdKeyNotFound as e:
        return ret

    return [json.loads(sub_item['value']) for sub_item in value._children]


def get_master(name):
    key = '/paas/masters/1.1/{}'.format(name)
    value = etcd_client.read(key).value
    return json.loads(value)


class NodeListV1_1(Resource):
    @check_license
    def get(self):
        node_list = get_node_list()
        data = {
            'kind': 'NodeList',
            'items': [n.dump_as_dict() for n in node_list]
        }
        response = flask.make_response(json.dumps(data))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response


class ApiNodeV1_1(Resource):
    @check_license
    def get(self, name):
        try:
            node = get_node(name)
            response_data = node.dump_as_dict()
            response_data['kind'] = 'Node'
            response = flask.make_response(json.dumps(response_data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        except NodeNotFound as e:
            response_json = {'kind': 'Status', 'code': 404, 'message': 'Can not find the node'}
            response = flask.make_response(json.dumps(response_json))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        except Exception as e:
            LOG.error(e)
            response_data = {'kind': 'Status', 'code': 500, 'message': 'internal server error'}
            response = flask.make_response(json.dumps(response_data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

    @check_license
    def patch(self, name):
        LOG.info('Start patching node <{}>'.format(name))
        data = request.get_json(force = True)
        if data is None:
            response_data = {'kind': 'Status', 'code': 400, 'message': 'Nod data or the data format is not a valid json'}
            response = flask.make_response(json.dumps(response_data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        if request.content_type == 'application/json-patch+json':
            return self.__handle_json_patch(name, data)
        elif request.content_type  == 'application/merge-patch+json':
            try:
                kube_client.AddLabel(ResourceType.Node, name)
            except Exception as e:
                LOG.error(str(e))
                response_data = {'kind': 'Status', 'code': 400, 'message': 'Can not add labels for the node'}
                response = flask.make_response(json.dumps(response_data))
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
        elif request.content_type  == 'application/json-patch+json':
            pass
        else:
            response_data = {'kind': 'Status', 'code': 400, 'message': 'Bad http headers'}
            response = flask.make_response(json.dumps(response_data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        response_data = {'kind': 'Status', 'code': 200, 'message': 'ok'}
        response = flask.make_response(json.dumps(response_data))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    def __handle_json_patch(self, name, data):
        response_data = {'kind': 'Status', 'code': 200, 'message': 'ok'}
        add_labels = {}
        remove_labels = []
        for elem in data:
            if elem['op'] not in ['add', 'remove'] or \
               os.path.dirname(elem['path']) != '/labels' or \
               os.path.basename(elem['path']) == '':
                response_data['code'] = 400
                response_data['message'] = 'The resource can not be patched'
                response = flask.make_response(json.dumps(response_data))
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
            if elem['op'] == 'add':
                if 'value' not in elem or \
                    (not isinstance(elem['value'], str) and not isinstance(elem['value'], unicode)):
                    response_data['code'] = 400
                    response_data['message'] = 'The resource can not be patched'
                    response = flask.make_response(json.dumps(response_data))
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    return response
                add_labels[os.path.basename(elem['path'])] = elem['value']
            else:
                remove_labels.append(os.path.basename(elem['path']))

        kube_client.AddLabel(ResourceType.Node, name, add_labels)
        kube_client.RemoveLabel(ResourceType.Node, name, remove_labels)
        response = flask.make_response(json.dumps(response_data))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

class MasterListV1_1(Resource):
    @check_license
    def get(self):
        data = {
            'kind': 'MasterList',
            'items': get_master_list()
        }
        response = flask.make_response(json.dumps(data))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response


class ApiMasterV1_1(Resource):
    @check_license
    def get(self, name):
        try:
            response_data = get_master(name)
            response_data['kind'] = 'Master'
            response = flask.make_response(json.dumps(response_data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        except NodeNotFound as e:
            response_json = {'kind': 'Status', 'code': 404, 'message': 'Can not find the node'}
            response = flask.make_response(json.dumps(response_json))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        except Exception as e:
            LOG.error(e)
            response_data = {'kind': 'Status', 'code': 500, 'message': 'internal server error'}
            response = flask.make_response(json.dumps(response_data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
