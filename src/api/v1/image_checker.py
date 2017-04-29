from registry import DockerRegistry
from flask_restful import Resource
from flask import request
import json
import flask
from log import LOG
from common import *

class ImageChecker(Resource):
    def __init__(self):
        self.docker_registries = {}

    @check_license
    def post(self):
        LOG.info('start image_checker')
        params = request.get_json()
        image_list = params['images']
        reply = {}
        for image in image_list:
            docker_hub, repo, tag = self.__split_image_url(image)
            registry = self.docker_registries.get(docker_hub)
            if registry is None:
                registry = DockerRegistry(docker_hub)
                self.docker_registries[docker_hub] = registry
            if registry.is_image_exist(repo, tag):
                reply[image] = 1
            else:
                reply[image] = 0

        response = flask.make_response(json.dumps(reply))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    def __split_image_url(self, image_url):
        image, tag = image_url.rsplit(':', 1)
        docker_hub, repo = image.split('/', 1)
        docker_hub.replace('http://', '')
        docker_hub.replace('https://', '')
        return docker_hub, repo, tag

