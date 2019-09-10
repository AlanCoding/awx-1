import io
import json
import datetime
from contextlib import redirect_stdout
from unittest import mock

from requests.models import Response

import pytest

from awx.main.tests.functional.conftest import _request


def sanitize_dict(din):
    '''Sanitize Django response data to purge it of internal types
    so it may be used to cast a requests response object
    '''
    if isinstance(din, (int, str, type(None), bool)):
        return din  # native JSON types, no problem
    elif isinstance(din, datetime.datetime):
        return din.isoformat()
    elif isinstance(din, list):
        for i in range(len(din)):
            din[i] = sanitize_dict(din[i])
        return din
    elif isinstance(din, dict):
        for k in din.copy().keys():
            din[k] = sanitize_dict(din[k])
        return din
    else:
        return str(din)  # translation proxies often not string but stringlike


@pytest.fixture
def run_module():
    def rf(module_args, request_user):

        def new_request(self, method, url, **kwargs):
            kwargs_copy = kwargs.copy()
            if 'data' in kwargs:
                kwargs_copy['data'] = json.loads(kwargs['data'])

            # make request
            rf = _request(method.lower())
            django_response = rf(url, user=request_user, expect=None, **kwargs_copy)

            # requests library response object is different from the Django response, but they are the same concept
            # this converts the Django response object into a requests response object for consumption
            resp = Response()
            py_data = django_response.data
            sanitize_dict(py_data)
            resp._content = bytes(json.dumps(django_response.data), encoding='utf8')
            resp.status_code = django_response.status_code
            return resp

        stdout_buffer = io.StringIO()
        # https://github.com/ansible/ansible/blob/8d167bdaef8469e0998996317023d3906a293485/lib/ansible/module_utils/basic.py#L498
        with mock.patch('ansible.module_utils.basic._load_params') as mock_params:
            mock_params.return_value = module_args
            # https://github.com/ansible/tower-cli/pull/489/files
            with mock.patch('tower_cli.api.Session.request', new=new_request):
                with redirect_stdout(stdout_buffer):
                    try:
                        from plugins.modules import tower_organization
                        tower_organization.main()
                    except SystemExit:
                        # A system exit is what we want for successful execution
                        pass

        module_stdout = stdout_buffer.getvalue().strip()
        result = json.loads(module_stdout)
        return result

    return rf
