# vim: tabstop=4 shiftwidth=4 softtabstop=4
'''
Methods and interface objects used to interact with external apis.  

API method calls return objects that are in many cases objects with
attributes that are direct maps to the data returned from the API http call.  
Unfortunately, these objects are also often constructed dynamically, making
it difficult to know what data is available from the API object.  Because of this,
all API calls should wrap their returned object in one defined here, using only
explicitly defined properties and/or methods.  This wrapping also makes testing 
easier.

In other words, django_openstack developers not working on django_openstack.api
shouldn't need to understand the finer details of APIs for Nova/Glance/Swift et
al.

'''

from django.conf import settings

import logging

import glance.client
import httplib
import json
import openstack.compute
import openstackx.admin
import openstackx.extras
import openstackx.auth
from urlparse import urlparse
import json


LOG = logging.getLogger('django_openstack.api')


class APIResourceWrapper(object):
    ''' Simple wrapper for api objects 
    
        Define attrs on the child class and pass in the 
        api object as the only argument to the constructor
    '''
    attrs = []
    def __init__(self, apiresource):
        self.apiresource = apiresource

    def __getattr__(self, attr):
        if attr in self.attrs:
            return self.apiresource.__getattr__(attr)
        else:
            LOG.debug('Attempted to access unknown attribute "%s" on'
                      'APIResource object of type "%s" wrapping resource of'
                      ' type "%s"' % (attr, self.__class__,
                                      self.apiresource.__class__))
            raise AttributeError(attr)

class APIDictWrapper(object):
    ''' Simple wrapper for api dictionaries

        Some api calls return dictionaries.  This class provides identical 
        behavior as APIResourceWrapper, except that it will also 
        behave as a dictionary, in addition to attribute accesses.

        Attribute access is the preferred method of access, to be
        consistent with api resource objects from openstackx
    '''
    def __init__(self, apidict):
        self.apidict = apidict

    def __getattr__(self, attr):
        if attr in self.attrs:
            return self.apidict[attr]
        else:
            LOG.debug('Attempted to access unknown item "%s" on'
                      'APIResource object of type "%s"' 
                      % (attr, self.__class__))
            raise AttributeError(attr)

    def __getitem__(self, item):
        return self.__getattr__(item)

    def get(self, item, default=None):
        try:
            return self.__getattr__(item)
        except AttributeError:
            return default


class Console(APIResourceWrapper):
    '''Simple wrapper around openstackx.extras.consoles.Console'''
    attrs = ['id', 'output', 'type']


class Flavor(APIResourceWrapper):
    '''Simple wrapper around openstackx.admin.flavors.Flavor'''
    attrs = ['disk', 'id', 'links', 'name', 'ram', 'vcpus']


class Image(APIDictWrapper):
    '''Simple wrapper around glance image dictionary'''
    attrs = ['checksum', 'created_at', 'deleted', 'deleted_at', 'disk_format',
             'id', 'is_public', 'location', 'name', 'properties',
             'size', 'status', 'updated_at']

    def __getattr__(self, attrname):
        if attrname == "properties":
            return ImageProperties(super(Image, self).__getattr__(attrname))
        else:
            return super(Image, self).__getattr__(attrname)

class ImageProperties(APIDictWrapper):
    '''Simple wrapper around glance image properties dictionary'''
    attrs = ['architecture', 'image_location', 'image_state', 'kernel_id',
             'project_id', 'ramdisk_id']


class KeyPair(APIResourceWrapper):
    '''Simple wrapper around openstackx.extras.keypairs.Keypair'''
    attrs = ['fingerprint', 'key_name', 'private_key']


class Server(APIResourceWrapper):
    '''Simple wrapper around openstackx.extras.server.Server'''
    attrs = ['addresses', 'attrs', 'hostId', 'id', 'imageRef', 'links',
             'metadata', 'name', 'private_ip', 'public_ip', 'status', 'uuid']


class Services(APIResourceWrapper):
    attrs = ['disabled', 'host', 'id', 'last_update', 'stats', 'type', 'up', 
             'zone']


class Tenant(APIResourceWrapper):
    '''Simple wrapper around openstackx.auth.tokens.Tenant'''
    attrs = ['id', 'description', 'enabled']


class Token(APIResourceWrapper):
    '''Simple wrapper around openstackx.auth.tokens.Token'''
    attrs = ['id', 'serviceCatalog', 'tenant_id', 'username']

class Usage(APIResourceWrapper):
    '''Simple wrapper around openstackx.extras.usage.Usage'''
    attrs = ['begin', 'instances', 'stop', 'tenant_id',
             'total_active_disk_size', 'total_active_instances',
             'total_active_ram_size', 'total_active_vcpus', 'total_cpu_usage',
             'total_disk_usage', 'total_hours', 'total_ram_usage']

class User(APIResourceWrapper):
    '''Simple wrapper around openstackx.extras.users.User'''
    attrs = ['email', 'enabled', 'id', 'tenantId']


def url_for(request, service_name, admin=False):
    catalog = request.session['serviceCatalog']
    if admin:
        rv = catalog[service_name][0]['adminURL']
    else:
        rv = catalog[service_name][0]['internalURL']
    return rv


def compute_api(request):
    compute = openstack.compute.Compute(
        auth_token=request.session['token'],
        management_url=url_for(request, 'nova'))
    # this below hack is necessary to make the jacobian compute client work
    compute.client.auth_token = request.session['token']
    compute.client.management_url = url_for(request, 'nova')
    LOG.debug('compute_api connection created using token "%s"'
                      ' and url "%s"' %
                      (request.session['token'], url_for(request, 'nova')))
    return compute


def account_api(request):
    LOG.debug('account_api connection created using token "%s"'
                      ' and url "%s"' %
                  (request.session['token'],
                   url_for(request, 'keystone', True)))
    return openstackx.extras.Account(
        auth_token=request.session['token'],
        management_url=url_for(request, 'keystone', True))


def glance_api(request):
    o = urlparse(url_for(request, 'glance'))
    LOG.debug('glance_api connection created for host "%s:%d"' %
                     (o.hostname, o.port))
    return glance.client.Client(o.hostname, o.port)


def admin_api(request):
    LOG.debug('admin_api connection created using token "%s"'
                    ' and url "%s"' %
                    (request.session['token'], url_for(request, 'nova', True)))
    return openstackx.admin.Admin(auth_token=request.session['token'],
                                 management_url=url_for(request, 'nova', True))


def extras_api(request):
    LOG.debug('extras_api connection created using token "%s"'
                     ' and url "%s"' %
                    (request.session['token'], url_for(request, 'nova')))
    return openstackx.extras.Extras(auth_token=request.session['token'],
                                   management_url=url_for(request, 'nova'))


def auth_api():
    LOG.debug('auth_api connection created using url "%s"' %
                   settings.OPENSTACK_KEYSTONE_URL)
    return openstackx.auth.Auth(management_url=settings.OPENSTACK_KEYSTONE_URL)


def console_create(request, instance_id, kind=None):
    return Console(extras_api(request).consoles.create(instance_id, kind))


def flavor_create(request, name, memory, vcpu, disk, flavor_id):
    return Flavor(admin_api(request).flavors.create(
            name, int(memory), int(vcpu), int(disk), flavor_id))


def flavor_delete(request, flavor_id, purge=False):
    return admin_api(request).flavors.delete(flavor_id, purge)


def flavor_get(request, flavor_id):
    return Flavor(compute_api(request).flavors.get(flavor_id))


def flavor_list(request):
    return [Flavor(f) for f in extras_api(request).flavors.list()]


def flavor_list_admin(request):
    return [Flavor(f) for f in extras_api(request).flavors.list()]


def image_all_metadata(request):
    images = glance_api(request).get_images_detailed()
    image_dict = {}
    for image in images:
        image_dict[image['id']] = image
    return image_dict


def image_create(request, image_meta, image_file):
    return Image(glance_api(request).add_image(image_meta, image_file))


def image_delete(request, image_id):
    return glance_api(request).delete_image(image_id)


def image_get(request, image_id):
    return Image(glance_api(request).get_image(image_id)[0])


def image_list_detailed(request):
    return [Image(i) for i in glance_api(request).get_images_detailed()]


def image_update(request, image_id, image_meta=None):
    image_meta = image_meta and image_meta or {}
    return Image(glance_api(request).update_image(image_id, image_meta=image_meta))


def keypair_create(request, name):
    return KeyPair(extras_api(request).keypairs.create(name))


def keypair_delete(request, keypair_id):
    return extras_api(request).keypairs.delete(keypair_id)


def keypair_list(request):
    return [KeyPair(key) for key in extras_api(request).keypairs.list()]


def server_create(request, name, image, flavor, user_data, key_name):
    return Server(extras_api(request).servers.create(
            name, image, flavor, user_data=user_data, key_name=key_name))


def server_delete(request, instance):
    return compute_api(request).servers.delete(instance)


def server_get(request, instance_id):
    return Server(compute_api(request).servers.get(instance_id))


def server_list(request):
    return [Server(s) for s in extras_api(request).servers.list()]


def server_reboot(request,
                  instance_id,
                  hardness=openstack.compute.servers.REBOOT_HARD):
    server = server_get(request, instance_id)
    return server.reboot(hardness)


def service_get(request, name):
    return admin_api(request).services.get(name)


def service_list(request):
    return [Services(s) for s in admin_api(request).services.list()]


def service_update(request, name, enabled):
    return admin_api(request).services.update(name, enabled)


def token_get_tenant(request, tenant_id):
    tenants = auth_api().tenants.for_token(request.session['token'])
    for t in tenants:
        if str(t.id) == str(tenant_id):
            return Tenant(t)

    LOG.warning('Unknown tenant id "%s" requested' % tenant_id)


def token_list_tenants(request, token):
    return [Tenant(t) for t in auth_api().tenants.for_token(token)]


def tenant_create(request, tenant_id, description, enabled):
    return Tenant(account_api(request).tenants.create(tenant_id,
                                                      description,
                                                      enabled))


def tenant_get(request, tenant_id):
    return Tenant(account_api(request).tenants.get(tenant_id))


def tenant_list(request):
    return [Tenant(t) for t in account_api(request).tenants.list()]


def tenant_update(request, tenant_id, description, enabled):
    return Tenant(account_api(request).tenants.update(tenant_id,
                                                      description,
                                                      enabled))


def token_create(request, tenant, username, password):
    return Token(auth_api().tokens.create(tenant, username, password))

def token_info(request, token):
    hdrs = {"Content-type": "application/json",
            "X_AUTH_TOKEN": settings.OPENSTACK_ADMIN_TOKEN,
            "Accept": "text/json"}

    o = urlparse(token.serviceCatalog['keystone'][0]['adminURL'])
    conn = httplib.HTTPConnection(o.hostname, o.port)
    conn.request("GET", "/v2.0/tokens/%s" % token.id, headers=hdrs)
    response = conn.getresponse()
    data = json.loads(response.read())

    admin = False
    for role in data['auth']['user']['roleRefs']:
        if role['roleId'] == 'Admin':
            admin = True

    return {'tenant': data['auth']['user']['tenantId'],
            'user': data['auth']['user']['username'],
            'admin': admin}


def usage_get(request, tenant_id, start, end):
    return Usage(extras_api(request).usage.get(tenant_id, start, end))


def usage_list(request, start, end):
    return [Usage(u) for u in extras_api(request).usage.list(start, end)]


def user_create(request, user_id, email, password, tenant_id):
    return User(account_api(request).users.create(
            user_id, email, password, tenant_id))


def user_delete(request, user_id):
    return account_api(request).users.delete(user_id)


def user_get(request, user_id):
    return User(account_api(request).users.get(user_id))


def user_list(request):
    return [User(u) for u in account_api(request).users.list()]


def user_update_email(request, user_id, email):
    return User(account_api(request).users.update_email(user_id, email))


def user_update_password(request, user_id, password):
    return User(account_api(request).users.update_password(user_id, password))


def user_update_tenant(request, user_id, tenant_id):
    return User(account_api(request).users.update_tenant(user_id, tenant_id))
