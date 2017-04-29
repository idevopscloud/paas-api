from flask import Blueprint, request, render_template, flash, g, session, redirect, url_for
import requests
import flask
import json
from copy import deepcopy
import datetime
import time
from keystoneclient.v2_0 import client as keystone_client
from heatclient.client import Client as heat_client
from heatclient.exc import *
import heatclient
import copy
from flask_restful import Resource
import re
import timeit
from log import LOG
from common import etcd_client
import etcd
import os

def _is_template_valid(template):
    if 'kind' not in template \
        or 'name' not in template\
        or 'memory_threshold' not in template:
        return False
    if template['kind'] != 'ApplicationController' \
        or template['name'] == '' \
        or type(template['memory_threshold']) is not int\
        or template['memory_threshold'] < 50:
        return False

    return True


class ApplicationControllerList(Resource):
    '''
    {
        "type": "ApplicationControllerList",
        "name": "fb-pmd-01",
        "memory_threshold": 900
    }
    '''
    def post(self):
        template = request.get_json()
        if not _is_template_valid(template):
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 400}))
            return response

        key = '/paas/application_controllers/{}'.format(template['name'])
        value = json.dumps(template)
        etcd_client.write(key, value)

        response = flask.make_response(json.dumps({'kind': 'Status', 'code': 200}))
        return response

    def get(self):
        key = '/paas/application_controllers'
        items = []
        try:
            value = etcd_client.read(key)
            for sub_item in value._children:
                key = sub_item['key']
                value = etcd_client.read(key).value
                items.append(json.loads(value))
        except:
            pass

        reply = {
            'kind': 'ApplicationControllerList',
            'items': items
        }
        response = flask.make_response(json.dumps(reply))
        return response

class ApplicationController(Resource):

    def get(self, name):
        key = '/paas/application_controllers/{}'.format(name)
        try:
            value = etcd_client.read(key).value
            response = flask.make_response(json.dumps(json.loads(value)))
        except etcd.EtcdKeyNotFound, e:
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 404}))

        return response

    def delete(self, name):
        key = '/paas/application_controllers/{}'.format(name)
        try:
            etcd_client.delete(key)
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 200}))
        except etcd.EtcdKeyNotFound, e:
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 404}))

        return response

    def put(self, name):
        template = request.get_json()
        if not _is_template_valid(template):
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 400}))
            return response

        key = '/paas/application_controllers/{}'.format(name)
        try:
            value = etcd_client.read(key).value
        except etcd.EtcdKeyNotFound, e:
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 404}))
            return response

        controller = json.loads(value)
        if controller['name'] != template['name']:
            response = flask.make_response(json.dumps({'kind': 'Status', 'code': 400}))
            return response

        etcd_client.write(key, json.dumps(template))
        response = flask.make_response(json.dumps({'kind': 'Status', 'code': 200}))
        return response

