import sys
import json
import requests
import inspect
from FWUtils import FWUtils

objFwUtils = FWUtils()
log = objFwUtils.get_logger(__name__)


def handle_expired_session(method):
    function_name = inspect.currentframe().f_code.co_name

    def method_wrapper(self, *args, **kwargs):
        log.info("Retry logic for API execution with valid token")
        try:
            response = method(self, *args, **kwargs)
            if response.status_code in [401, 402, 403, 404]:
                log.info("*****************  The token has expired!!  *****************")
                self.get_new_token()
                response = method(self, *args, **kwargs)
            else:
                log.info("Token is not expired yet !")
            return response
        except Exception as e:
            log.info(f'{function_name} - API Failed')
            log.exception(e)

    log.info(f'{function_name} - API Executed Successfully')
    return method_wrapper


class PpsRestClient:
    API_VERSION = "/api/v1"
    HEADERS = {'content-type': 'application/json', 'charset': 'utf-8', 'accept': 'application/json'}
    POST = 'post'
    PUT = 'put'
    GET = 'get'
    DELETE = 'delete'
    __token = []
    DEFAULT_TIMEOUT = 10

    def __init__(self, device_name=None, admin_username=None, admin_password=None, device_id=1):
        function_name = inspect.currentframe().f_code.co_name
        if not device_name:
            device_id = 'DEVICE' if device_id == 1 else f'DEVICE_{device_id}'
            log.info(device_id)
            self.device = objFwUtils.get_config('DEVICE')['IP']['MGMT']
            self.admin_username = objFwUtils.get_config(device_id)['REST_ADMIN']['USER']
            self.admin_password = objFwUtils.get_config(device_id)['REST_ADMIN']['PASSWORD']
        else:
            self.device = device_name
            self.admin_username = admin_username
            self.admin_password = admin_password

        self.url = 'https://{}'.format(self.device)
        if not PpsRestClient.__token:
            self.__login_pps_rest()
        else:
            log.info(f"{len(PpsRestClient.__token)} session(s) exists, checking if existing can be returned...")
            log.info("Token exists. Checking validity")
            for obj in PpsRestClient.__token:
                if obj.device == self.device and obj.admin_username == self.admin_username and \
                        obj.admin_password == self.admin_password:
                    log.info(PpsRestClient.__token)
                    if self.is_token_valid(obj.token):
                        log.info("Token is valid")
                        self.token = obj.token
                        log.info("Returning existing token")
                        break
                else:
                    log.info(f"Existing token don't match {self.device}, {self.admin_username} or matching token is "
                             f"invalid, so creating a new token...")
                    self.__login_pps_rest()
                    log.info("Checking if the token in PpsRestClient.__token needs to replaced")
                    for obj in PpsRestClient.__token:
                        if obj.device == self.device and obj.admin_username == self.admin_username and \
                                obj.admin_password == self.admin_password:
                            log.info("Match found! Need to replace the invalid token in PpsRestClient.__token ...")
                            obj.token = self.token
                            log.info("Invalid token replaced!!")
                            break
                    else:
                        log.info(
                            "No session matched! This was not expected. Adding session to PpsRestClient.__token")
                        PpsRestClient.__token.append(self)
        log.info(f'{function_name} - API Executed Successfully')

    def __login_pps_rest(self):
        function_name = inspect.currentframe().f_code.co_name
        pps_ip = self.device
        base_uri_v1 = 'https://' + pps_ip + '/api/v1'
        admin_user_name = self.admin_username
        admin_password = self.admin_password
        payload = dict()
        response: requests.Response = requests.Response()
        try:
            log.info("Rest API Signing In !")
            # api/v1/auth is removed from 22.7R2.1 release and so commenting below config url.
            # url = base_uri_v1 + '/auth'

            # api/v1/realm_auth should be used from 22.7R2.1 with realm data in request body
            url = base_uri_v1 + '/realm_auth'
            # Default Admin Realm is 'Admin Users'
            payload['realm'] = 'Admin Users'

            # the Login is no longer a GET call
            # response = requests.get(url=url, auth=(admin_user_name, admin_password), verify=False)

            log.info("Trying to login to >22.7R3 ICS")
            response = requests.post(url, json=payload, auth=(admin_user_name, admin_password), verify=False)

            self.token = json.loads(response.text)['api_key']
            PpsRestClient.__token.append(self)
            log.info(f"Getting token after signing in. Token = {self.token}")
            log.info(f"API Response = {response}")
            log.info(f'{function_name} - API Executed Successfully')
            return response
        except Exception as e:
            log.error(f'{function_name} - Failed')
            log.error(e)
            log.exception(sys.exc_info())
        return response

    @handle_expired_session
    def execute_request(self, resource_uri=None, method_type=None, payload=None, params=None):
        function_name = inspect.currentframe().f_code.co_name
        request_uri = self.url + resource_uri
        log.info(f"-----------> {request_uri}")
        response = None
        log.info("Request Query: %s", request_uri)
        log.info("Request Method: %s", method_type)
        log.info("---------------------------- REST API CALL -------------------------------")
        try:
            if method_type == self.POST:
                log.info("Executing a POST Request:")
                log.info(f"Url: {request_uri}")
                log.info(f"Payload: {payload}")
                response = requests.post(url=request_uri, auth=(self.token, ''), data=json.dumps(payload),
                                         headers=self.HEADERS, verify=False)
            elif method_type == self.PUT and payload is not None:
                log.info("Executing a PUT Request:")
                log.info(f"Url: {request_uri}")
                log.info(f"Payload: {payload}")
                response = requests.put(url=request_uri, auth=(self.token, ''), data=json.dumps(payload),
                                        headers=self.HEADERS, verify=False)
            elif method_type == self.DELETE:
                log.info("Executing a DELETE Request:")
                log.info(f"Url: {request_uri}")
                response = requests.delete(url=request_uri, auth=(self.token, ''), headers=self.HEADERS, verify=False)
            elif method_type == self.GET:
                log.info("Executing a GET Request:")
                log.info(f"Url: {request_uri}")
                log.info(f"Params: {params}")
                response = requests.get(url=request_uri, auth=(self.token, ''), params=params, headers=self.HEADERS,
                                        verify=False)
            else:
                msg = "Invalid request method type: {}".format(method_type)
                raise Exception(msg)
        except Exception as e:
            log.error(f'{function_name} - API Failed')
            log.error("Failed to execute the %s request with the query %s", method_type, request_uri)
            log.exception(e)
        log.info(f"Status: {response.status_code}")
        log.info(f"Response: {response.text}")
        log.info(f'{function_name} - API Executed Successfully')
        return response

    def is_token_valid(self, token):
        function_name = inspect.currentframe().f_code.co_name
        log.info("Checking token validity")
        uri = self.url + PpsRestClient.API_VERSION + '/configuration/'
        response: requests.Response = requests.Response()
        try:
            response = requests.get(url=uri, auth=(token, ''), headers=self.HEADERS, verify=False)
            log.info(f"Status: {response.status_code}")
            if response.status_code in [200, 204]:
                log.info(f'{function_name} - API Executed Successfully')
                token_validity_check = True
            else:
                log.error(f'{function_name} - API Failed')
                token_validity_check = False

            return token_validity_check
        except Exception as e:
            log.error(f'{function_name} - API Failed')
            log.error(e)
            log.error(f"Error while checking session validity: {response.status_code}, {response.text}")
            token_validity_check = False
            return token_validity_check

    def get_new_token(self):
        function_name = inspect.currentframe().f_code.co_name
        self.__login_pps_rest()
        log.info("Getting new token")
        for obj in PpsRestClient.__token:
            obj.token = self.token
            log.info("Replacing new token !")
            break
        else:
            log.info("Token added!")
            PpsRestClient.__token.append(self)
        log.info(f'{function_name} - API Executed Successfully')
