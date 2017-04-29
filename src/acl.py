from settings import settings
from log import LOG

def check_acl(account, resource, action):
    if settings.ACL is None:
        return True

    for rule in settings.ACL:
        if rule['resource'] == '*' or rule['resource'] == resource:
            if 'reject' in rule and action in rule['reject']:
                return False

    return True

