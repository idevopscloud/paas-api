#!/usr/bin/env python

import sys
import urllib2
import json
from copy import deepcopy
import time
import datetime
import re
from log import LOG
import requests
from exception import *

class Image(object):
    def __init__(self, image_name, tag_list):
        self.image_name = image_name
        self.tag_list = tag_list
        self.create_time = time.time()
    
    def is_tag_existed(self, tag):
        if tag in self.tag_list:
            return True
        else:
            return False

    def remove_tag(self, tag):
        try:
            self.tag_list.remove(tag)
        except:
            pass

class ImageCache(object):
    def __init__(self):
        self.registries = dict()

    def add_image(self, server, image_name, tag_list):
        if server not in self.registries:
            self.registries[server] = dict()
        try:
            self.registries[server].pop(image_name)
        except:
            pass
        self.registries[server][image_name] = Image(image_name, tag_list)

    def hit(self, server, image_name, tag):
        if server not in self.registries:
            return False

        image = self.registries[server].get(image_name)
        if image is None:
            return False

        if time.time() - image.create_time > 3600 * 24 * 30:
            self.repositories[server].pop(image_name)
            return False

        return image.is_tag_existed(tag)

    def remove_image(self, server, image_name, tag):
        if server not in self.registries or image_name not in self.registries[server]:
            return

        image = self.registries[server][image_name]
        image.remove(tag)

class DockerRegistry(object):
    servers = {}
    image_cache = ImageCache()

    def __init__(self, server):
        self.server = server
        self.version = "unknown"

        if server in DockerRegistry.servers:
            self.version = DockerRegistry.servers[server]
            return

        try:
            if self.__is_registry_v1():
                self.version = 'v1'
                DockerRegistry.servers[server] = self.version
            elif self.__is_registry_v2():
                self.version = 'v2'
                DockerRegistry.servers[server] = self.version
            else:
                raise Exception("unknown registry version")
        except Exception, e:
            LOG.error(str(e))
            raise Exception("Can not connect to the registry server <%s>" % server)

    def __get_registry_version(self):
        try:
            urllib2.Request('http://{}/v2/'.format(self.server))
        except:
            raise

    def __is_registry_v1(self):
        try:
            req = urllib2.Request('http://{}/'.format(self.server))
            response = urllib2.urlopen(req)
            if "docker-registry server" in response.read():
                return True
            else:
                return False
        except:
            raise

    def __is_registry_v2(self):
        try:
            req = urllib2.Request('http://{}/v2/'.format(self.server))
            response = urllib2.urlopen(req)
            return True
        except:
            return False

    def get_images(self, prefix=None):
        if self.version == 'v1':
            return self.__get_images_v1()
        elif self.version == 'v2':
            return self.__get_images_v2(prefix)

        return None

    def delete_image(self, image_name, tag):
        try:
            digest = self.__get_image_digest(image_name, tag)
        except Exception as e:
            raise e

        url = 'http://{}/v2/{}/manifests/{}'.format(self.server, image_name, digest)
        r = requests.delete(url)
        if r.status_code not in [200, 202]:
            return HttpException(r.status_code)

        DockerRegistry.image_cache.remove_image(self.server, image_name, tag)

    def __get_image_digest(self, image_name, tag):
        try:
            url = 'http://{}/v2/{}/manifests/{}'.format(self.server, image_name, tag)
            r = requests.get(url)
            if r.status_code == 404:
                raise HttpException(404)
            return r.headers['Docker-Content-Digest']
        except Exception as e:
            LOG.error(str(e))
            raise e

    def __get_images_v1(self):
        images = {}
        try:
            # First get all images
            for i in range(3):
                req = urllib2.Request('http://{}/v1/search'.format(self.server))
                response = urllib2.urlopen(req)
                recv_json = json.load(response)
                for item in recv_json['results']:
                    if item['name'] not in images:
                        images[item['name']] = []

            # Get all tags for each image
            for image_name in images:
                tag_list = self.__get_tags_for_image_v1(image_name)
                images[image_name] = tag_list

            return images
        except Exception, e:
            print e

    def __get_images_v2(self, prefix=None):
        images = {}
        try:
            # First get all images
            for i in range(2):
                req = urllib2.Request('http://{}/v2/_catalog?n=10000'.format(self.server))
                response = urllib2.urlopen(req)
                recv_json = json.load(response)
                for image in recv_json['repositories']:
                    if prefix is not None and re.match(prefix, image) is None:
                        continue
                    if image not in images:
                        tag_list = self.__get_tags_for_image_v2(image)
                        if tag_list is not None and len(tag_list) > 0:
                            images[image] = tag_list

            return images
        except Exception, e:
            raise e

    def get_image_names(self):
        if self.version == 'v1':
            return self.__get_image_names_v1()
        elif self.version == 'v2':
            return self.__get_image_names_v2()

    def __get_image_names_v1(self):
        images = {}
        for i in range(3):
            req = urllib2.Request('http://{}/v1/search'.format(self.server))
            response = urllib2.urlopen(req)
            recv_json = json.load(response)
            for item in recv_json['results']:
                if item['name'] not in images:
                    images[item['name']] = None
        return list(images)

    def __get_image_names_v2(self):
        images = {}
        for i in range(2):
            req = urllib2.Request('http://{}/v2/_catalog?n=10000'.format(self.server))
            response = urllib2.urlopen(req)
            recv_json = json.load(response)
            for image in recv_json['repositories']:
                if image not in images:
                    images[image] = None
        return list(images)

    def __get_tags_for_image_v1(self, image_name):
        tag_list = []
        try:
            req = urllib2.Request('http://{}/v1/repositories/{}/tags'.format(self.server, image_name))
            response = urllib2.urlopen(req)

            if response.getcode() == 200:
                recv_json = json.load(response)
                for key, value in recv_json.items():
                    tag_list.append(key)
        except:
            return []

        return tag_list

    def __get_tags_for_image_v2(self, image_name):
        try:
            req = urllib2.Request('http://{}/v2/{}/tags/list'.format(self.server, image_name))
            response = urllib2.urlopen(req)

            if response.getcode() == 200:
                recv_json = json.load(response)
        except:
            return []

        return recv_json['tags']

    def get_tags_for_image(self, image_name):
        tag_list = list()
        if self.version == 'v1':
            tag_list = self.__get_tags_for_image_v1(image_name)
        elif self.version == 'v2':
            tag_list = self.__get_tags_for_image_v2(image_name)

        DockerRegistry.image_cache.add_image(self.server, image_name, tag_list)
        return tag_list
    
    def is_image_exist(self, image_name, tag):
        if DockerRegistry.image_cache.hit(self.server, image_name, tag):
            return True

        tags = self.get_tags_for_image(image_name)
        if len(tags) == 0 or tag not in tags:
            return False

        return True

def main(argv):
    try:
        registry = DockerRegistry(argv[0])
        #print "registry version is " + registry.version

        image_names = registry.get_image_names()
        for image_name in image_names:
            tag_list = registry.get_tags_for_image(image_name)
            if len(tag_list) > 0:
                for tag in tag_list:
                    print "{}/{}:{}".format(argv[0], image_name, tag)
        sys.exit(0)

    except Exception, e:
        print e

if __name__ == '__main__':

    if len(sys.argv) != 2:
        print "Usage: registry <url>"
        print "For example: registry 172.30.10.195:5000"
        sys.exit(1)

    main(sys.argv[1:])

