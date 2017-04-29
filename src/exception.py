class NodeNotFound(Exception):
    def __init__(self, node_name):
        self.node_name = node_name

class HeatException(Exception):
    pass

class BadAppTemplate(Exception):
    pass

class ImageNotFound(Exception):
    pass

class HttpException(Exception):
    def __init__(self, status_code):
        self.status_code = status_code
