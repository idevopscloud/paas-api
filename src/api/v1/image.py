import os
from registry import DockerRegistry
from flask_restful import Resource
from flask import request
import json
import flask
from log import LOG
from settings import settings
from common import *
from exception import *

class Image(object):
    def __init__(self, name, tags):
        self.name = name
        self.short_name = os.path.basename(name)
        self.tags = tags

    def to_dict(self):
        reply = {
            'name': self.name,
            'short_name': self.short_name,
            'tags': []
        }
        for tag in self.tags:
            reply['tags'].append({'name': tag})

        return reply

class ImageList(Resource):
    def __init__(self):
        self.registry = DockerRegistry(settings.DOCKER_REGISTRY_URL)

    def is_image_type_valid(self, image_type):
        if (image_type and
                image_type not in ['lib', 'app_base', 'app', 'team_ol']):
            return False
        return True

    @check_license
    def get(self):
        LOG.info('get ImageList')

        prefix = None
        image_type = request.args.get('type', None)
        app_name = request.args.get('app_name', None)

        if (image_type not in ['app_base', 'app', 'team_ol']
                and app_name is not None):
            return make_status_response(400, 'Arguments are not valid')

        if image_type is not None:
            prefix = image_type + '/'
        if app_name is not None:
            prefix += app_name + '/'

        images = self.registry.get_images(prefix)

        reply = {}
        reply['kind'] = 'ImageList'
        reply['images'] = []

        for name, tags in images.items():
            reply['images'].append(Image(name, tags).to_dict())

        response = flask.make_response(json.dumps(reply))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    @check_license
    def delete(self):
        LOG.info('delete ImageList')

        prefix = None

        image_type = request.args.get('type', None)
        if not self.is_image_type_valid(image_type):
            return make_status_response(400, 'Arguments are not valid')

        app_name = request.args.get('app_name', None)
        name = request.args.get('name', None)
        version = request.args.get('version', None)

        if name is None or version is None:
            return make_status_response(400, 'Image name and version must be specified.')
        if image_type != 'lib' and app_name is None:
            return make_status_response(400, 'app_name must be specified')

        if image_type == 'lib':
            image_full_name = 'lib/' + name
        else:
            image_full_name = '{}/{}/{}'.format(image_type, app_name, name)

        try:
            self.registry.delete_image(image_full_name, version)
        except HttpException as e:
            if e.status_code == 404:
                return make_status_response(404, 'image not found')
        except Exception as e:
            return make_status_response(500, '')

        return make_status_response(200, 'OK')

