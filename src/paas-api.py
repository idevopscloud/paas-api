from flask import Flask, g
from flask_restful import Resource, Api
import sys
import os
from settings import Settings
import log
import traceback  

def save_pid():
    if not os.path.exists('/var/run/paas'):
        os.mkdir('/var/run/paas')

    PID_FILE_PATH = '/var/run/paas/paas-api.pid'
    f = file(PID_FILE_PATH, 'w')
    f.write(str(os.getpid()))
    f.close()


def load_unversioned_api(restful_api):
    from api.unversioned.ping import ApiPing, ApiKubeAddr
    restful_api.add_resource(ApiPing, '/ping')
    restful_api.add_resource(ApiKubeAddr, '/kubeaddr')

def load_v1_api(restful_api):
    version = 'v1'
    prefix = '/api/' + version
    prefix_1_1 = '/api/v1.1'

    from api.v1.application import ApplicationList as ApplicationList_v1
    from api.v1.application import Application as Application_v1
    from api.v1.application import ApplicationPod as ApplicationPod_v1
    from api.v1.application import ApiApplicationActions as ApiApplicationActions_v1
    from api.v1.application import ApiApplicationTemplate as ApiApplicationTemplate_v1
    restful_api.add_resource(ApplicationList_v1, prefix + '/applications', prefix_1_1 + '/applications')
    path = '/applications/<string:application_name>'
    restful_api.add_resource(Application_v1, prefix + path, prefix_1_1 + path)

    path = '/applications/<string:application_name>/pods/<string:pod_name>'
    restful_api.add_resource(ApplicationPod_v1, prefix + path, prefix_1_1 + path)

    path = '/applications/<string:app_name>/actions'
    restful_api.add_resource(ApiApplicationActions_v1, prefix + path, prefix_1_1 + path)

    path = '/applications/<string:app_name>/template'
    restful_api.add_resource(ApiApplicationTemplate_v1, prefix + path, prefix_1_1 + path)

    from api.v1.application_controller import ApplicationControllerList as ApplicationControllerList_v1
    from api.v1.application_controller import ApplicationController as ApplicationController_v1
    path = '/application_controllers'
    restful_api.add_resource(ApplicationControllerList_v1, prefix + path, prefix_1_1 + path)

    path = '/application_controllers/<string:name>'
    restful_api.add_resource(ApplicationController_v1, prefix + path, prefix_1_1 + path)

    from api.v1.image_checker import ImageChecker as ImageChecker_v1
    path = '/image_checker'
    restful_api.add_resource(ImageChecker_v1, prefix + path, prefix_1_1 + path)

    from api.v1.node import NodeList as NodeList_v1
    from api.v1.node import ApiNode as ApiNode_v1
    path = '/nodes'
    restful_api.add_resource(NodeList_v1, prefix + path, methods=['PATCH', 'GET' ])
    path = '/nodes/<string:name>'
    restful_api.add_resource(ApiNode_v1, prefix + path, methods=['PATCH', 'GET', 'UPDATE'])

    from api.v1.caas import ApiCaasInstances as ApiCaasInstances_v1
    from api.v1.caas import ApiCaasInstance as ApiCaasInstance_v1
    path = '/caas_apps/<string:caas_app_name>/instances'
    restful_api.add_resource(ApiCaasInstances_v1, prefix + path, prefix_1_1 + path, methods=['GET', 'POST' ])
    path = '/caas_apps/<string:caas_app_name>/instances/<string:caas_instance_name>'
    restful_api.add_resource(ApiCaasInstance_v1, prefix + path, prefix_1_1 + path, methods=['GET', 'DELETE'])

    from api.v1.image import ImageList as ImageList_v1
    path = '/images'
    restful_api.add_resource(ImageList_v1, prefix + path, prefix_1_1 + path)

    from api.v1.node_v1_1 import NodeListV1_1, ApiNodeV1_1, MasterListV1_1, ApiMasterV1_1
    restful_api.add_resource(NodeListV1_1, '/api/v1.1/nodes', methods=['PATCH', 'GET'])
    restful_api.add_resource(ApiNodeV1_1, '/api/v1.1/nodes/<string:name>', methods=['PATCH', 'GET', 'UPDATE'])
    restful_api.add_resource(MasterListV1_1, '/api/v1.1/masters', methods=['GET'])
    restful_api.add_resource(ApiMasterV1_1, '/api/v1.1/masters/<string:name>', methods=['GET'])


def main(argv):
    app = Flask(__name__)
    restful_api = Api(app)

    from log import LOG
    from settings import settings

    try:
        save_pid()
        load_unversioned_api(restful_api)
        load_v1_api(restful_api)

    except Exception as e:
        if settings.DEBUG:
            traceback.print_exc()
        LOG.error(str(e))
        LOG.error('exit 1')
        sys.exit(1)

    LOG.info('Started')
    app.run(host=settings.BINDING_ADDR, port=settings.PORT, debug=settings.DEBUG, threaded=settings.USE_THREAD, use_reloader=settings.USE_RELOADER)

if __name__ == '__main__':
    main(sys.argv[1:])

