from flask_restful import Resource
from settings import settings
import flask
import json

class ApiPing(Resource):
    def get(self):
        return flask.make_response('ok')


class ApiKubeAddr(Resource):
    def get(self):
        url = 'http://{}:8080'.format(settings.K8S_IP)
        return flask.make_response(json.dumps({'k8s_addr': url}))

