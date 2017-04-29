from common import TimeUtils

class InvolvedObject:
    def __init__(self, json_data):
        # NOTICE: no data copy here
        self.json_data = json_data
        self.kind = json_data.get('kind', None)
        self.name = json_data.get('name', None)
        self.namespace = json_data.get('namespace', None)
        self.uid = json_data.get('uid', None)
        self.api_version = json_data.get('apiVersion', None)
        self.resource_version = json_data.get('resourceVersion', None)

class Event:
    def __init__(self, json_data):
        self.json_data = json_data
        self.involved_object = InvolvedObject(json_data.get('involvedObject'))
        self.metadata = json_data.get('metadata')
        self.namespace = self.metadata.get('namespace')
        self.creation_timestamp = TimeUtils.convert_from_go_format(self.metadata.get('creationTimestamp'))
        self.deletion_timeStamp = TimeUtils.convert_from_go_format(self.metadata.get('deletionTimestamp'))
        self.reason = json_data.get('reason', None)
        self.message = self.json_data.get('message', None)
        self.type = self.json_data.get('type', None)
        self.count = self.json_data.get('count')
        self.detailed_reason = self.__get_detailed_reason()

    def __get_detailed_reason(self):
        detailed_reason = None
        if self.reason != 'FailedScheduling':
            return detailed_reason

        lines = self.message.split('\n')
        for line in lines:
            if 'failed to fit in any node' in line:
                continue
            if 'MatchNodeSelector' in line and detailed_reason is None:
                detailed_reason = 'MatchNodeSelector'
            if 'Node didn\'t have enough resource: Memory' in line:
                detailed_reason = 'LackOfMemory'

        return detailed_reason

