#!/usr/bin/env python
#coding=utf-8

from flask import Flask,request,redirect,abort,Response,render_template
import flask
import json
from flask_restful import Resource
from common import *
from log import LOG
from kubernetes import KubernetesError
import k8s

class ApiCaasInstances(Resource):
    @check_license
    def get(self, caas_app_name):
        caas_app = CaasApp(caas_app_name)
        instance_list = caas_app.get_instances()
        json_data = {
            'kind': 'CaasInstanceList',
            'items': [ instance.to_dict() for instance in instance_list ]
        }
        response = flask.make_response(json.dumps(json_data))
        return response

    @check_license
    def post(self, caas_app_name):
        LOG.info('Creating caas instance')

        template = request.get_json()
        if template is None:
            LOG.info('template of caas app <{}> instance is None'.format(caas_app_name))
            return make_status_response(400, 'Bad CaaS instance template') 

        temp_file = dump_app_json_into_file(caas_app_name, json.dumps(template, indent=2))
        LOG.info('dump template into ' + temp_file)

        if not self.__is_template_valid(caas_app_name, template):
            LOG.info('caas_app <{}>: template is invalid'.format(caas_app_name))
            return make_status_response(400, 'Bad CaaS instance template') 

        caas_instance_name = template['rc_template']['definition']['metadata']['name']

        if 'svc_template' in template:
            try:
                kube_client.CreateService(json.dumps(template['svc_template']['definition']), caas_app_name)
            except KubernetesError as e:
                LOG.error('Failed to create service <{}> in namespace <{}>'.format(caas_instance_name, caas_app_name))
                LOG.error(str(e))
                return make_status_response(e.code, e.message)

        try:
            kube_client.CreateReplicationController(json.dumps(template['rc_template']['definition']), caas_app_name)
        except KubernetesError as e:
            LOG.error('Failed to create RC <{}> in namespace <{}>'.format(caas_instance_name, caas_app_name))
            LOG.error(str(e))
            try:
                kube_client.DeleteService(caas_instance_name, caas_app_name)
            except KubernetesError as e:
                LOG.error('Failed to delete service <{}> in namespace <{}>'.format(caas_instance_name, caas_app_name))
                LOG.error(str(e))

            return make_status_response(e.code, e.message)

        return make_status_response(200, 'OK')

    def __is_rc_template_valid(self, caas_app_name, caas_instance_name, rc_template):
        try:
            rc_namespace = rc_template['definition']['metadata']['namespace']    
            if rc_namespace != caas_app_name:
                return False
            rc_name = rc_template['definition']['metadata']['name']
            if rc_name != caas_instance_name:
                return False
        except Exception as e:
            return False

        return True

    def __is_svc_template_valid(self, caas_app_name, caas_instance_name, svc_template):
        try:
            svc_namespace = svc_template['definition']['metadata']['namespace']    
            if svc_namespace != caas_app_name:
                return False
            svc_name = svc_template['definition']['metadata']['name']
            if svc_name != caas_instance_name:
                return False
        except Exception as e:
            return False

        return True

    def __is_template_valid(self, caas_app_name, template):
        if template is None:
            return False
        if template.get('kind') != 'CaasInstance' or 'name' not in template:
            return False
        if 'rc_template' not in template:
            return False

        instance_name = template['name']
        if not self.__is_rc_template_valid(caas_app_name, instance_name, template['rc_template']):
            return False

        if 'svc_template' in template:
            if not self.__is_svc_template_valid(caas_app_name, instance_name, template['svc_template']):
                return False

        return True

class CaasApp(object):
    def __init__(self, name):
        self.name = name

    def is_instance_existed(self, instance_name):
        if kube_client.GetReplicationController(name=instance_name, namespace=self.name) is None:
            return False
        else:
            return True

    def get_instance(self, instance_name):
        if not self.is_instance_existed(instance_name):
            return None

        pod_json_list = kube_client.GetPodsJson(namespace=self.name, selector = { 'name': instance_name})

        pods = [ k8s.Pod(pod) for pod in pod_json_list ]

        svc_json = kube_client.GetServiceJson(name=instance_name, namespace=self.name)
        if svc_json is not None:
            svc = k8s.Service(svc_json)
        else:
            svc = None

        return CaasInstance(self.name, instance_name, pods, svc)

    def get_instances(self):
        instances = []

        rc_list = kube_client.GetReplicationControllers(namespace=self.name)
        for rc in rc_list.Items:
            pod_json_list = kube_client.GetPodsJson(namespace=self.name, selector = { 'name': rc.Name})
            if pod_json_list is None:
                continue

            pods = [ k8s.Pod(pod) for pod in pod_json_list ]
            svc_json = kube_client.GetServiceJson(name=rc.Name, namespace=self.name)
            if svc_json is not None:
                svc = k8s.Service(svc_json)
            else:
                svc = None
            instances.append(CaasInstance(self.name, rc.Name, pods, svc))

        return instances

class CaasInstance(object):
    def __init__(self, caas_app_name, name, pods, svc):
        self.caas_app_name = caas_app_name
        self.name = name
        self.pods = pods
        self.svc = svc

    def to_dict(self):
        ret = {
            'kind': 'CaasInstance',
            'name': self.name,
            'caas_app_name': self.caas_app_name,
            'pods': [ pod.to_dict() for pod in self.pods ],
        }
        if self.svc is not None:
            ret['svc'] = self.svc.to_dict()

        return ret

class ApiCaasInstance(Resource):
    @check_license
    def get(self, caas_app_name,  caas_instance_name):
        caas_app = CaasApp(caas_app_name)
        caas_instance = caas_app.get_instance(caas_instance_name)
        if caas_instance is None:
            return make_status_response(404, 'The instance <{}> does not exist'.format(caas_instance_name))

        response = flask.make_response(json.dumps(caas_instance.to_dict()))
        return response

    @check_license
    def delete(self, caas_app_name, caas_instance_name):
        try:
            kube_client.ResizeReplicationController(name=caas_instance_name,
                    replicas=0,
                    namespace=caas_app_name)
            kube_client.DeleteReplicationController(caas_instance_name, caas_app_name)
        except KubernetesError as e:
            if e.code != 404:
                LOG.error('Failed to delete rc <{}> in namespace <{}>'.format(caas_instance_name, caas_app_name))
                return make_status_response(e.code, e.message)

        try:
            kube_client.DeleteService(caas_instance_name, caas_app_name)
        except KubernetesError as e:
            if e.code != 404:
                LOG.error('Failed to delete service <{}> in namespace <{}>'.format(caas_instance_name, caas_app_name))
                return make_status_response(e.code, e.message)

        return make_status_response(200, "OK")

