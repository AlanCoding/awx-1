import os
import io
import sys
import runpy
import json
import datetime
from contextlib import redirect_stdout
from unittest import mock

from requests.models import Response

import pytest

import importlib.util

from awx.main.models import Organization

from awx.main.tests.functional.conftest import _request


@pytest.mark.django_db
def test_param_specification(admin_user):
    root_path = os.path.abspath(os.path.join(
        __file__,
        os.pardir, os.pardir, os.pardir, os.pardir, os.pardir, os.pardir,
        'awx_modules'
    ))
    base_path = os.path.abspath(os.path.join(
        __file__,
        os.pardir, os.pardir, os.pardir, os.pardir, os.pardir, os.pardir,
        'awx_modules', 'plugins'
    ))
    #, '__init__.py'
    mods_path = os.path.abspath(os.path.join(base_path, 'modules'))
    mod_path = os.path.abspath(os.path.join(base_path, 'modules', 'tower_organization.py'))

    sys.path.append(root_path)
    # sys.path.append(base_path)

    def new_request(self, method, url, **kwargs):
        # print statements will mess with stdout parsing
        # print('request: {} to {}, kwargs: {}'.format(method, url, kwargs))
        kwargs_copy = kwargs.copy()
        if 'data' in kwargs:
            kwargs_copy['data'] = json.loads(kwargs['data'])

        rf = _request(method.lower())
        django_response = rf(url, user=admin_user, expect=None, **kwargs_copy)
        # requests library response object is different from the Django response, but they are the same concept
        resp = Response()
        py_data = django_response.data
        # sanitize data for internal formats

        def sanitize_dict(din):
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

        sanitize_dict(py_data)

        # import pdb; pdb.set_trace()
        resp._content = bytes(json.dumps(django_response.data), encoding='utf8')
        resp.status_code = django_response.status_code
        return resp

        # return resp

    module_args = {'name': 'foo', 'description': 'barfoo', 'state': 'present'}

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

    print('output:{}'.format(stdout_buffer.getvalue().strip()))
    result = json.loads(stdout_buffer.getvalue().strip())
    assert result == {
        "organization": "foo",
        "state": "present",
        "id": 1,
        "changed": True,
        "invocation": {
            "module_args": module_args
        }
    }

    org = Organization.objects.get(name='foo')
    assert org.description == 'barfoo'

    # mod = runpy.run_path(mod_path)

    # runpy.run_module(
    #     mod_name='%(module_fqn)s',
    #     init_globals=None,
    #     run_name='__main__',
    #     alter_sys=False
    # )
    # mod = runpy.run_path(mod_path)  # attempted relative import with no known parent package

    # res_path = os.path.join(mod_path, 'modules', 'tower_organization.py')
    # spec = importlib.util.spec_from_file_location("tower_organization", res_path)
    # spec = importlib.util.spec_from_file_location("tower_organization", mod_path)
    # mod = importlib.util.module_from_spec(spec)
    # sys.modules[spec.name] = mod
    # spec.loader.exec_module(mod)
    # import pdb; pdb.set_trace()
    # mod.main()
