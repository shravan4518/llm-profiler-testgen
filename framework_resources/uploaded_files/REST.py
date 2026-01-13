import sys, time, re
import base64
import json, inspect
import requests
import requests.auth
import urllib3
from ConfigUtils import ConfigUtils
from Utils import *
from PSRSClient import PSRSClient

psrsclient = PSRSClient()
util = Utils()
config = ConfigUtils.getInstance()
api_type = 'zta_c'
"""
API Type for interacting with different device types
    zta_c : ZTA Controller
    zta_gw : ZTA Gateway
    pcs_gw : PCS Gateway
    pps_gw : PPS Gateway
    9.x    : For Interacting with PCS
"""

class RestClient(object):
    """ REST API Class
    An Instance of this class represents rest connection to an instance.
    """
    host = None
    api_key = None
    host_rest_auth_url = None
    response = None
    response_details = None
    rest_credentials = {}
    return_hash = None
    zta_fqdn = None
    zta_obj = None
    def __init__(self, device_type = None):
        """
        | Creates a rest connection to the host
        Param:
           | Example:
             |   rest_client  =  RestClient() |
        """
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            # Disable SSL Warning
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            RestClient.api_key = None
            RestClient.host_rest_auth_url = None
            RestClient.response = None
            RestClient.host = None
            RestClient.response_details = None
            RestClient.rest_credentials = {}
            RestClient.return_hash = None
        except:
          e = sys.exc_info()[1]
          logging.error("Exception in " + func_name + "(): " + str(e))
          util.FUNC_HEADER_FOOTER('Exit', func_name)
          raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)

    def set_device_type(self, type = 'pcs_gw'):
        global api_type
        api_type = type

    def get_device_type(self):
        return api_type

    def rest_login(self,host=None, credentials=None):
        """
        | :param host: Hostname or IP. Type - String |
        | :param credentials: Contains username and password and certificates details for cert auth. Type - Dictionary |
       |  :return: Output Dictionary |
         | response_details = {'ResponseCode': Contains Rest request status_code,'ResponseContent': Contains the session token/api_key, contains the response message/errors which are returned by REST API call.} |
        Usage:
        | Restlogin_details  =  {
            |         'username': 'admin',
               |      'password': 'password',
               |      'cert'    : 'C:\\pisa\\config\\pem_file.pem',
                |     'cert_key': 'C:\\pisa\\config\\pem_key_file.key'
            |     }
          |   login_response = RESTObj.RestClient.rest_login(host, Restlogin_details)
        """
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('The API type is :'+api_type)
            if api_type in ('zta_c', 'pps_gw', 'pcs_gw', 'zta_gw'):
                #Will pull these varibales from config file later, for now making it user dependent
                resp = self.zta_login({'user':credentials['username'], 'password': credentials['password'], 'hostname': host })
                util.FUNC_HEADER_FOOTER('Exit', func_name)
                return resp
            # Disable SSL Warning
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            if credentials is None:
                RestClient.rest_credentials['username'] = config.device(1).get_ADMIN_USER()
                RestClient.rest_credentials['password'] = config.device(1).get_ADMIN_PASSWORD()
            else:
                RestClient.rest_credentials = credentials
            if host is None:
                RestClient.host = config.device(1).get_HOSTNAME()
            else:
                RestClient.host = host

            RestClient.api_key = ''
            cred_encoded_temp = (RestClient.rest_credentials['username'] + ":" + RestClient.rest_credentials['password']).encode()
            # Split and truncating the "b'" string after string encode.
            cred_encoded = str(base64.b64encode(cred_encoded_temp)).split('b\'')[1][:-1]
            host_rest_auth_url = "https://" + RestClient.host + "/api/v1/auth"
            if 'cert' in RestClient.rest_credentials.keys():
                RestClient.response = requests.get(host_rest_auth_url, verify=False,
                                                   cert=(RestClient.rest_credentials['cert'], RestClient.rest_credentials['cert_key']),
                                                   headers={"Content-Type": "application/json",
                                                            "Authorization": "Basic {}".format(cred_encoded)})
            else:
                RestClient.response = requests.get(host_rest_auth_url, verify=False,
                                                   headers={"Content-Type": "application/json",
                                                            "Authorization": "Basic {}".format(cred_encoded)})
            if RestClient.response.status_code == 200:
                RestClient.api_key = RestClient.response.json()['api_key']
                response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': RestClient.api_key}
            else:
                response_details = {'ResponseCode': RestClient.response.status_code,
                                    'ResponseContent': RestClient.response.reason}
        except:
            response_details = {'ResponseCode': None,
                                'ResponseContent': None}
            e = sys.exc_info()[1]
            logging.debug("Exception in " + func_name + "(): " + str(e))
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details


    def get(self,uri_string=None, session_token=None):
        """
        | Retrieve information. |
        Param:
           |  uri_string - REST URI of the resource. Type - String |
            | session_token - [optional] session token/api_key. Type - String |
       |  Return:Output Dictionary |
      |    response_details = {'ResponseCode': Contains Rest request status_code,'ResponseContent': Contains the REST get output, contains the response message/errors which are returned by REST API call. } |

        """
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            logging.info('The API type is :'+api_type)
            if uri_string is None:
                logging.error("Get: Invalid uri string parameter passed.")
                return_hash = {'error': "Invalid uri string parameter passed"}
                return return_hash

            if api_type in ('pps_gw', 'pcs_gw', 'zta_c', 'zta_gw'):
                current_device = config.getCurrentConfig()['DEVICE']
                logging.info('The current device set is :'+current_device)
                resp = self.zta_get(uri_string)
                util.FUNC_HEADER_FOOTER('Exit', func_name)
                return resp

            if session_token is None:
                session_token = RestClient.api_key

            host_rest_auth_url = "https://" + RestClient.host + self.__prepend_url(uri_string)

            if 'cert' in RestClient.rest_credentials.keys():
                RestClient.response = requests.get(host_rest_auth_url, verify=False, cert=[
                    RestClient.rest_credentials['cert'], RestClient.rest_credentials['cert_key']],
                                                   auth=requests.auth.HTTPBasicAuth(session_token, ''),
                                                   headers={'Content-Type': 'application/json'})
            else:
                RestClient.response = requests.get(host_rest_auth_url, verify=False,
                                                   auth=requests.auth.HTTPBasicAuth(session_token, ''),
                                                   headers={'Content-type': 'application/json'})

            if RestClient.response.status_code == 200:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            else:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code,
                                    'ResponseContent': json_response_data,
                                    'ResponseReason': RestClient.response.reason}

        except:
            response_details = {'ResponseCode': None,
                                'ResponseContent': None}
            e = sys.exc_info()[1]
            logging.debug("Exception in " + func_name + "(): " + str(e))
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def put(self,uri_string=None, request_body=None, session_token=None):
        """
        | Update existing resource
        | Param:
            | uri_string - address path of the resource. Type - String |
            | request_body - data to insert in JSON format. Type - Dictionary |
            | session_token - [optional] session token/api_key. Type - String |
        Return:
        | Output Dictionary
        |  response_details = {'ResponseCode': Contains Rest request status_code, 'ResponseContent': Contains the REST get output, contains the response message/errors which are returned by REST API call.} |
        """
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)
        try:
            if uri_string is None:
                logging.error("post: Invalid uri string parameter passed.")
                return_hash = {'error': "Invalid uri string parameter passed"}
                return return_hash

            if api_type in ('pcs_gw', 'pps_gw', 'zta_c', 'zta_gw'):
                current_device = config.getCurrentConfig()['DEVICE']
                logging.info('The current device set is :' + current_device)
                resp = self.zta_put(uri_string, request_body)
                util.FUNC_HEADER_FOOTER('Exit', func_name)
                return resp

            if session_token is None:
                session_token = RestClient.api_key

            host_rest_auth_url = "https://" + RestClient.host + self.__prepend_url(uri_string)
            json_data = json.dumps(request_body)

            if 'cert' in RestClient.rest_credentials.keys():
                RestClient.response = requests.put(host_rest_auth_url, verify=False, cert=[
                    RestClient.rest_credentials['cert'], RestClient.rest_credentials['cert_key']],
                                                   auth=requests.auth.HTTPBasicAuth(session_token, ''), data=json_data,
                                                   headers={'Content-Type': 'application/json'})
            else:
                RestClient.response = requests.put(host_rest_auth_url, verify=False,
                                                   auth=requests.auth.HTTPBasicAuth(session_token, ''),
                                                   data=json_data, headers={'Content-type': 'application/json'})

            if RestClient.response.status_code == 200:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            else:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code,
                                    'ResponseContent': json_response_data,
                                    'ResponseReason': RestClient.response.reason}
        except:
            response_details = {'ResponseCode': None,
                                'ResponseContent': None}
            e = sys.exc_info()[1]
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def post(self,uri_string=None, request_body=None, session_token=None):
        """
       |  Add new resource
        Param:
          |   uri_string - address path of the resource to be created. Type - String |
           |  RequestBody - data to insert. Type - Dictionary |
           |  session_token - [optional] session token/api_key. Type - String |
            Return:
             | Output Dictionary
         | response_details = {'ResponseCode': Contains Rest request status_code, 'ResponseContent': Contains the REST get output, contains the response message/errors which are returned by REST API call } |
        """
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if uri_string is None:
                logging.error("Get: Invalid uri string parameter passed.")
                return_hash = {'error': "Invalid uri string parameter passed"}
                return return_hash

            if api_type in ('pcs_gw', 'pps_gw', 'zta_c', 'zta_gw'):
                current_device = config.getCurrentConfig()['DEVICE']
                logging.info('The current device set is :' + current_device)
                resp = self.zta_post(uri_string, request_body)
                util.FUNC_HEADER_FOOTER('Exit', func_name)
                return resp

            if session_token is None:
                session_token = RestClient.api_key

            host_rest_auth_url = "https://" + RestClient.host + self.__prepend_url(uri_string)
            json_data = json.dumps(request_body)
            if 'cert' in RestClient.rest_credentials.keys():
                RestClient.response = requests.post(host_rest_auth_url, verify=False, cert=[
                    RestClient.rest_credentials['cert'], RestClient.rest_credentials['cert_key']],
                                                    auth=requests.auth.HTTPBasicAuth(session_token, ''), data=json_data,
                                                    headers={'Content-Type': 'application/json'})
            else:
                RestClient.response = requests.post(host_rest_auth_url, verify=False,
                                                    auth=requests.auth.HTTPBasicAuth(session_token, ''),
                                                    data=json_data, headers={'Content-type': 'application/json'})

            if RestClient.response.status_code == 200:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            else:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code,
                                    'ResponseContent': json_response_data,
                                    'ResponseReason': RestClient.response.reason}
        except:
            response_details = {'ResponseCode': None,
                                'ResponseContent': None}
            e = sys.exc_info()[1]
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def delete(self,uri_string=None, session_token=None):
        """
        | Delete resource
        Param:
            | uri_string - address path of the resource to be created. Type - String |
           |  session_token - [optional] session token/api_key. Type - String |
        Return:
        | Output Dictionary
        |  response_details = {'ResponseCode': Contains Rest request status_code, 'ResponseContent': Contains the REST get output, contains the response message/errors which are returned by REST API call} |
        """
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            if uri_string is None:
                logging.error("Get: Invalid uri string parameter passed.")
                return_hash = {'error': "Invalid uri string parameter passed"}
                return return_hash

            if api_type in ('pps_gw', 'pcs_gw', 'zta_c', 'zta_gw'):
                current_device = config.getCurrentConfig()['DEVICE']
                logging.info('The current device set is :' + current_device)
                resp = self.zta_delete(uri_string)
                util.FUNC_HEADER_FOOTER('Exit', func_name)
                return resp

            if session_token is None:
                session_token = RestClient.api_key

            host_rest_auth_url = "https://" + RestClient.host + self.__prepend_url(uri_string)
            if 'cert' in RestClient.rest_credentials.keys():
                RestClient.response = requests.delete(host_rest_auth_url, verify=False, cert=(
                    RestClient.rest_credentials['cert'], RestClient.rest_credentials['cert_key']),
                                                      auth=requests.auth.HTTPBasicAuth(session_token, ''),
                                                      headers={'Content-Type': 'application/json'})
            else:
                RestClient.response = requests.delete(host_rest_auth_url, verify=False,
                                                      auth=requests.auth.HTTPBasicAuth(session_token, ''),
                                                      headers={'Content-type': 'application/json'})

            if RestClient.response.status_code == 200:
                json_response_data = json.loads(RestClient.response.content)
                response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            else:
                if RestClient.response.content:
                    json_response_data = json.loads(RestClient.response.content)
                else:
                    json_response_data = {}
                response_details = {'ResponseCode': RestClient.response.status_code,
                                    'ResponseContent': json_response_data,
                                    'ResponseReason': RestClient.response.reason}
        except:
            response_details = {'ResponseCode': None,
                                'ResponseContent': None}
            e = sys.exc_info()[1]
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def restRealmLogin(self,host=None, credentials=None, realm = None):
        """
        | :param host: Hostname or IP. Type - String |
       |  :param credentials: Contains username and password and certificates details for cert auth. Type - Dictionary |
        | :param realm: Realm name |
       |  :return: Output Dictionary |
         | response_details = {'ResponseCode': Contains Rest request status_code,'ResponseContent': Contains the session token/api_key, contains the response message/errors which are returned by REST API call. } |
        :usage:
            | Restlogin_details  =  {
             |        'username': 'admin',
             |        'password': 'password',
              |       'cert'    : 'C:\\pisa\\config\\pem_file.pem',
              |       'cert_key': 'C:\\pisa\\config\\pem_key_file.key'
             |    }
            | login_response = RESTObj.RestClient.restRealmLogin(host, Restlogin_details, realm)
        """
        
        func_name = inspect.stack()[0][3]
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            RestClient.api_key = ''
            logging.info("Entered restRealmLogin....")
            
            # Disable SSL Warning
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            if credentials is None:
                RestClient.rest_credentials['username'] = config.device(1).get_ADMIN_USER()
                RestClient.rest_credentials['password'] = config.device(1).get_ADMIN_PASSWORD()
            else:
                RestClient.rest_credentials = credentials
            if host is None:
                RestClient.host = config.device(1).get_ADMIN_HOSTNAME()
            else:
                RestClient.host = host
                
            json_body = {"realm": realm}
            json_data = json.dumps(json_body)
            
            host_rest_realm_auth_url = "https://"+RestClient.host+"/api/v1/realm_auth"

            cred_encoded_temp = (RestClient.rest_credentials['username'] + ":" + RestClient.rest_credentials['password']).encode()
            # Split and truncating the "b'" string after string encode.
            cred_encoded = str(base64.b64encode(cred_encoded_temp)).split('b\'')[1][:-1]
            
            response = requests.post(host_rest_realm_auth_url, verify=False,
                                                    data=json_data, headers={"Content-type": "application/json","Authorization": "Basic {}".format(cred_encoded)})
            if response.status_code == 200:
                RestClient.api_key = response.json()['api_key']
                response_details = {'ResponseCode': response.status_code, 'ResponseContent': RestClient.api_key}
            else:
                response_details = {'ResponseCode': response.status_code,
                                    'ResponseContent': response.reason}
        except:
            response_details = {'ResponseCode': None,
                                'ResponseContent': None}
            e = sys.exc_info()[1]
            logging.debug("Exception in " + func_name + "(): " + str(e))
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            raise Exception(e)

        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def enable_disable_rest(self, input_dict):
        """
        Description:
            | To enable or disable REST API calls|
        Input Param:
            | 1. 'device_num' - Device number where the rest is to be enabled or disabled
              2. 'rest_username' - Username for whom rest is to be enabled/disabled
              3. 'enable_disable' - ON or OFF
            |
        Output:
            | None |
        Usage:
            | rest_client(input_dict)
        """
        func_name = inspect.stack()[0][3]
        return_dict = {'status': 0, 'message': "Failed to enable or disable Rest"}
        try:
            util.FUNC_HEADER_FOOTER('Enter', func_name)
            device_num = input_dict['device_num']
            device_ip = config.getDeviceConfig(device_num, 'HOSTNAME')
            rest_dict = {'username': config.getDeviceConfig(device_num, 'ADMIN_USER'),
                         'password': config.getDeviceConfig(device_num, 'ADMIN_PASSWORD'),
                         'device': device_ip}
            rest_dict['response_code'] = self.rest_login(device_ip, rest_dict)['ResponseCode']
            actual_status = 'ON'
            if rest_dict['response_code'] != 200:
                actual_status = 'OFF'
            if actual_status == input_dict['enable_disable']:
                logging.info("The rest is already in: " + actual_status + " state")
                return_dict['message'] = "The rest is already in: " + actual_status + " state"
                return_dict['status'] = 1
            else:
                input_dict['host'] = device_ip
                psrs_dict = {'api_name': 'enable_disable_rest', 'params': input_dict}
                return_dict = psrsclient.execute_api("POST", psrs_dict)
        except:
            e = sys.exc_info()[1]
            logging.debug("Exception in " + func_name + "(): " + str(e))
            return_dict['message'] = "Exception in " + func_name + "(): " + str(e)
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return return_dict

    def zta_login(self, input):
        """
            Description:
                | To enable or disable REST API calls|
            Input Param:
                | json with:
                'user'     : ZTA Admin user name
                'password' : ZTA Admin password
                'hostname'  : ZTA Host name  or FQDN
            This method is called in constructor to login to tenant as Admin
            :return: True in case of login successful
                     False in case of login failure
            :Usage:
            objRest = RestClient()
            result = objRest.zta_login({'user': 'admin','password': 'dana123', 'hostname': 'auto.rhubarb.pzt.dev.perfsec.com'})
            logging.info(result)
            resp = objRest.zta_get('/api/gateways')
            logging.info(str(resp))
        """
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER("Enter", func_name)
        self.zta_fqdn = input['hostname']
        result = False
        r = requests.Session()
        try:
            resp = r.get('https://'+input['hostname']+'/login/admin',allow_redirects=True)
            if resp.status_code != 200:
                raise Exception
            login_url = resp.url.replace('welcome', 'login')
            login_info = {
                          'username': input['user'],
                          'password': input['password'],
                          'realm': 'ZTA Admin Users',
                          'btnSubmit': 'Submit+Query'
                         }
            resp = r.post(url=login_url, data=login_info, allow_redirects=True)
            if resp.status_code != 200:
                raise Exception
            d = str(resp.content)
            if 'Continue the session' in d:
                formdatastr = xsauth = None
                try:
                    # FormDataStr value
                    p = r'.*name="FormDataStr" value="(.*?)">'
                    x = re.findall(p, d)
                    formdatastr = x[0]
                except IndexError:
                    result = False
                    raise Exception
                try:
                    p = r'.*name="xsauth" value="(.*?)"'
                    x = re.findall(p, d)
                    xsauth = x[0]
                except IndexError:
                    result = False
                    raise Exception
                confirm = {
                            "FormDataStr": formdatastr,
                            "xsauth": xsauth,
                            "btnContinue": "Continue the session"
                          }
                resp = r.post(url=login_url, data=confirm, allow_redirects=True)
                if resp.status_code != 200:
                    raise Exception
            result = True
        except Exception:
            result = False
            logging.error(sys.exc_info()[1])
        finally:
            self.zta_obj = r
        util.FUNC_HEADER_FOOTER("Exit", func_name)
        return result

    def find_device_type(self, fqdn):
        resp = requests.get("http://" + fqdn)
        if "Pulse Zero Trust Access" in resp.text:
            return True
        else:
            return False

    def zta_get(self, uri):
        '''
        :param uri: Just the URI part of URL
        :return: Json with ResponseCode and ResponseContent
        :Usage :
           response =  zta_obj.zta_get('/api/gateways')
        '''
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER("Enter", func_name)
        try:
            uri = self.__prepend_url(uri)
            logging.info('The GET url is :'+'https://'+self.zta_fqdn+uri)
            RestClient.response = self.zta_obj.get('https://'+self.zta_fqdn+uri,verify=False, headers={'Content-type': 'application/json'} )
            logging.info('ZTA GET status code is :'+str(RestClient.response.status_code))
            if RestClient.response.status_code == 200:
                json_response_data = json.loads(RestClient.response.content)
            else:
                json_response_data = RestClient.response.reason
            response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
        except:
            logging.error(sys.exc_info()[1])
            response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': str(RestClient.response.content)}
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def zta_post(self, uri, user_data):
        '''
        :param uri      : Just the URI part of URL
               user_data: What ever post data in dict or json format
        :return: Json with ResponseCode and ResponseContent
        :Usage :
            json_data = {'key1': 'value1', 'key2': 'value2'}
           response =  zta_obj.zta_post('/api/gateways', json_data)
        '''
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER("Enter", func_name)
        try:
            uri = self.__prepend_url(uri)
            logging.info('The POST url is :'+'https://'+self.zta_fqdn+uri)
            RestClient.response = self.zta_obj.post('https://'+self.zta_fqdn+uri, data = user_data, verify=False, headers={'Content-type': 'application/json'})
            logging.info('ZTA POST status code is :' + str(RestClient.response.status_code))
            time.sleep(3)
            if RestClient.response.status_code in (200, 201):
                json_response_data = json.loads(RestClient.response.content)
            else:
                json_response_data = RestClient.response.reason
            response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            #if RestClient.response.status_code in (200, 204):
            #    if api_type in ('pps_gw', 'pcs_gw'):
            #        if "verb" in user_data:
                        # This is executed only for Action & Status API in which verb,path & data is present as keys in
                        # input json body & wherein publish changeset is not needed.
            #            pass
            #        else:
            #            response_details = self.__get_and_publish_changeset()
        except:
            logging.error(sys.exc_info()[1])
            response_details = {'ResponseCode': None, 'ResponseContent': None}
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def zta_put(self, uri, user_data):
        '''
        :param uri      : Just the URI part of URL
               user_data: What ever post data in dict or json format
        :return: Json with ResponseCode and ResponseContent
        :Usage :
            json_data = {'key1': 'value1', 'key2': 'value2'}
           response =  zta_obj.zta_put('/api/gateways', json_data)
        '''
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER("Enter", func_name)
        try:
            uri = self.__prepend_url(uri)
            logging.info('The POST url is :'+'https://'+self.zta_fqdn+uri)
            RestClient.response = self.zta_obj.put('https://'+self.zta_fqdn+uri, data = user_data, verify=False, headers={'Content-type': 'application/json'})
            logging.info('ZTA PUT status code is :' + str(RestClient.response.status_code))
            if RestClient.response.status_code in (200, 201):
                json_response_data = json.loads(RestClient.response.content)
            else:
                json_response_data = RestClient.response.reason
            response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            #if RestClient.response.status_code in (200, 204):
            #    if api_type in ('pps_gw', 'pcs_gw'):
            #        response_details = self.__get_and_publish_changeset()
        except:
            logging.error(sys.exc_info()[1])
            response_details = {'ResponseCode': None, 'ResponseContent': None}
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def zta_delete(self, uri):
        '''
        :uri      : Just the URI part of URL
               user_data: What ever post data in dict or json format
        :return: Json with ResponseCode and ResponseContent
        :Usage :
           response =  zta_obj.zta_delete('/api/gateways')
        '''
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER("Enter", func_name)
        try:
            uri = self.__prepend_url(uri)
            logging.info('The POST url is :'+'https://'+self.zta_fqdn+uri)
            RestClient.response = self.zta_obj.delete('https://'+self.zta_fqdn+uri, verify=False, headers={'Content-type': 'application/json'})
            logging.info('ZTA DELETE status code is :' + str(RestClient.response.status_code))
            if RestClient.response.status_code in (200, 204):
                if RestClient.response.status_code == 204:
                    json_response_data = "Success"
                else:
                    json_response_data = json.loads(RestClient.response.content)
            else:
                json_response_data = None
            response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
            #if RestClient.response.status_code in (200, 204):
            #    if api_type in ('pps_gw', 'pcs_gw'):
            #        response_details = self.__get_and_publish_changeset()
        except:
            logging.error(sys.exc_info()[1])
            response_details = {'ResponseCode': RestClient.response.status_code, 'ResponseContent': json_response_data}
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def __get_and_publish_changeset(self):
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)
        logging.info("Get the pending changeset ID and publish")
        uri = self.__prepend_url('/changesets/pending')
        get_changeset_id = self.zta_get(uri)
        if get_changeset_id['ResponseCode'] in (200, 204):
            logging.info('The changeset version no is : ' + get_changeset_id['ResponseContent']['version'])
            publish_json = '{ "version" : "' + get_changeset_id['ResponseContent']['version'] + '" }'
            uri = self.__prepend_url('/changesets/publishes')
            resp = self.zta_obj.post('https://' + self.zta_fqdn + uri, publish_json, verify=False,
                                     headers={'Content-type': 'application/json'})
            logging.info("ZTA POST status code is : {}".format(resp.status_code))
            if resp.status_code in (200, 204):
                if resp.content:
                    json_response_data = json.loads(resp.content)
                else:
                    json_response_data = None
                response_details = {'ResponseCode': resp.status_code, 'ResponseContent': json_response_data}
            else:
                response_details = {'ResponseCode': None, 'ResponseContent': 'Error in PUBLISHING CHANGESET'}
        else:
            raise Exception("Failed to get changeset ID")
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return response_details

    def __prepend_url(self, uri):
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)

        if api_type in ('pps_gw', 'pcs_gw'):
            current_device = config.getCurrentConfig()['DEVICE']
            gateway_ID = config.getDeviceConfig(current_device, 'GATEWAY_ID')
            logging.debug("Prepending base url /api/pcs-configs based on gateway builds")
            # IF user has passed config url along with /ap1/v1 for zta by mistake, trim those prepend
            uri = re.sub(r'^\/api\/v1', '', uri)
            # If user is passing complete URL return the same
            if re.search(r'^\/api\/pcs-configs\/', uri):
                logging.debug("Gateway url already has /api/pcs-configs prepend, returning")
                uriString = uri
            else:
                uriString = '/api/pcs-configs/' + gateway_ID + uri
        elif api_type == 'zta_c':
            logging.debug("ZTA Controller type, no need to prepend base url, returning")
            uriString = uri
        elif api_type == 'zta_gw':
            # This is another type will be decided later
            pass
        elif api_type == "9.x":
            if re.search(r'^\/api\/', uri):
                logging.debug("9.x url already has /api prepend, returning")
                uriString = uri
            else:
                logging.debug("Prepending base url /api/v1 based on 9.x builds")
                uriString = "/api/v1" + uri
        logging.info("Input URL : {}, Return URL : {}".format(uri,uriString))
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return uriString

    def get_DSID(self, zta_url, username, password):
        '''
        Pre requisite: The username must have gracefully logged out of any other existing session if any.
        :zta_url      : Just the hostname of the ZTA , no protocol or URI should be there Ex: 10.65.43.44 or www.zta_test.com
        :username      : Must be a non admin user of ZTA.
        :password       : pass word of the non admin user
        :return: Json with status and Value , status values = 0(fail) or 1(Pass), Value = DSID
        :Usage :
                objRest =Rest_Client.py
                ret = objRest.get_DSID('10.64.55.99', 'test1', 'test123')
            assert ret['status'] == 1
        '''
        ret = {'status': 0, 'value': 'DSID could not be generated'}
        func_name = inspect.stack()[0][3]
        util.FUNC_HEADER_FOOTER('Enter', func_name)
        logging.debug('The ZTA host name to obtain DSID is '+zta_url)
        login_URL = 'https://'+ zta_url + '/dana-na/auth/url_default/login.cgi'
        data1 = {"tz_offset": "", "clientMAC": "", "username": username, "password": password, "realm": 'Users',
                 "btnSubmit": "Sign In"}
        user_session = requests.session()
        user_session.post(url=login_URL, data=data1, verify=False, allow_redirects=True)
        user_session.get(url='https://'+ zta_url + '/api/v1/enduser/landing-page', verify=False, allow_redirects=True)
        dsid = user_session.cookies.get('DSID')
        if not dsid:
            util.FUNC_HEADER_FOOTER('Exit', func_name)
            return ret
        else:
            ret['status'] = 1
            ret['value'] = dsid
        logging.debug('The DSID generated against user : ' + username + ' is DSID: ' + dsid)
        util.FUNC_HEADER_FOOTER('Exit', func_name)
        return ret
"""
========================================================================================================================
Author-Maheshwara Rao V
Modified by-Jagan shankar,Srinidhi
Modified date- 05/Oct/2020
Bugs Fixed if any-<List Of Bugs>
pylintscore- 6.88
Licence -COPYRIGHT & LICENSE
Copyright 2018, Pulse Secure, LLC, all rights reserved.
This program is free software; you can redistribute it and/or modify it under the same terms as Python itself.
========================================================================================================================
"""
