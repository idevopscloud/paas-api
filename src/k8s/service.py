import copy
from common import kube_client

class Service:
    def __init__(self, json_data):
        self.json_data = copy.deepcopy(json_data)
        self.name = json_data['metadata']['name']
        self.namespace = json_data['metadata']['namespace']
        self.ports = json_data['spec'].get('ports', None)
        self.selector = json_data['spec'].get('selector', None)
        self.public_addresses = []
        self.external_IPs = json_data['spec'].get('externalIPs', None)
        if self.external_IPs is not None:
            for node_IP in self.external_IPs:
                node_json = kube_client.GetNodeJson(node_IP)
                public_address = node_json['metadata']['labels'].get('idevops.node.public-address', None)
                if public_address is not None:
                    self.public_addresses.append(public_address)
                else:
                    self.public_addresses.append(node_IP)

    def to_dict(self):
        return {
            'name': self.name,
            'namespace': self.namespace,
            'ports': self.ports,
            'selector': self.selector,
            'external_IPs': self.external_IPs,
            'public_addresses': self.public_addresses
        }

