# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Firebase Remote Config Module.
This module has required APIs for the clients to use Firebase Remote Config with python.
"""

import json
from typing import Dict, Optional
from firebase_admin import App, _http_client, _utils
import firebase_admin

_REMOTE_CONFIG_ATTRIBUTE = '_remoteconfig'

class ServerTemplateData:
    """Represents a Server Template Data class."""
    def __init__(self, headers, response_json):
        self._parameters = response_json['parameters']
        self._conditions = response_json['conditions']
        self._version = response_json['version']
        self._parameter_groups = response_json['parameterGroups']
        self._etag = headers.get('ETag')

    @property
    def parameters(self):
        return self._parameters

    @property
    def etag(self):
        return self._etag

    @property
    def version(self):
        return self._version

    @property
    def conditions(self):
        return self._conditions

    @property
    def parameter_groups(self):
        return self._parameter_groups


class ServerTemplate:
    """Represents a Server Template with implementations for loading and evaluting the tempalte."""
    def __init__(self, app: App = None, default_config: Optional[Dict[str, str]] = None):
        """Initializes a ServerTemplate instance.

        Args:
          app: App instance to be used. This is optional and the default app instance will
                be used if not present.
          default_config: The default config to be used in the evaluated config.
        """
        self._rc_service = _utils.get_app_service(app,
                                                  _REMOTE_CONFIG_ATTRIBUTE, _RemoteConfigService)

        # This gets set when the template is
        # fetched from RC servers via the load API, or via the set API.
        self._cache = None
        if default_config is not None:
            self._stringified_default_config = json.dumps(default_config)
        else:
            self._stringified_default_config = None

    async def load(self):
        """Fetches the server template and caches the data."""
        self._cache = await self._rc_service.getServerTemplate()

    def evaluate(self, context):
        # Logic to process the cached template into a ServerConfig here.
        # TODO: Add Condition evaluator.
        self._evaluator = _ConditionEvaluator(self._cache.conditions, context)
        return ServerConfig(config_values=self._evaluator.evaluate())

    def set(self, template):
        """Updates the cache to store the given template is of type ServerTemplateData.

        Args:
          template: An object of type ServerTemplateData to be cached.
        """
        if isinstance(template, ServerTemplateData):
            self._cache = template


class ServerConfig:
    """Represents a Remote Config Server Side Config."""
    def __init__(self, config_values):
        self._config_values = config_values # dictionary of param key to values

    def get_boolean(self, key):
        return bool(self.get_value(key))

    def get_string(self, key):
        return str(self.get_value(key))

    def get_int(self, key):
        return int(self.get_value(key))

    def get_value(self, key):
        return self._config_values[key]


class _RemoteConfigService:
    """Internal class that facilitates sending requests to the Firebase Remote
        Config backend API.
    """
    def __init__(self, app):
        """Initialize a JsonHttpClient with necessary inputs.

        Args:
            app: App instance to be used for fetching app specific details required
                for initializing the http client.
        """
        remote_config_base_url = 'https://firebaseremoteconfig.googleapis.com'
        self._project_id = app.project_id
        app_credential = app.credential.get_credential()
        rc_headers = {
            'X-FIREBASE-CLIENT': 'fire-admin-python/{0}'.format(firebase_admin.__version__), }
        timeout = app.options.get('httpTimeout', _http_client.DEFAULT_TIMEOUT_SECONDS)

        self._client = _http_client.JsonHttpClient(credential=app_credential,
                                                   base_url=remote_config_base_url,
                                                   headers=rc_headers, timeout=timeout)


    def get_server_template(self):
        """Requests for a server template and converts the response to an instance of
        ServerTemplateData for storing the template parameters and conditions."""
        url_prefix = self._get_url_prefix()
        headers, response_json = self._client.headers_and_body('get',
                                                               url=url_prefix+'/namespaces/ \
                                                               firebase-server/serverRemoteConfig')
        return ServerTemplateData(headers, response_json)

    def _get_url_prefix(self):
        # Returns project prefix for url, in the format of
        # /v1/projects/${projectId}
        return "/v1/projects/{0}".format(self._project_id)


class _ConditionEvaluator:
    """Internal class that facilitates sending requests to the Firebase Remote
    Config backend API."""
    def __init__(self, context, conditions):
        self._context = context
        self._conditions = conditions

    def evaluate(self):
        # TODO: Write evaluator
        return {}


async def get_server_template(app: App = None, default_config: Optional[Dict[str, str]] = None):
    """Initializes a new ServerTemplate instance and fetches the server template.

    Args:
        app: App instance to be used. This is optional and the default app instance will
            be used if not present.
        default_config: The default config to be used in the evaluated config.

    Returns:
        ServerTemplate: An object having the cached server template to be used for evaluation.
    """
    template = init_server_template(app=app, default_config=default_config)
    await template.load()
    return template

def init_server_template(app: App = None, default_config: Optional[Dict[str, str]] = None,
                         template_data: Optional[ServerTemplateData] = None):
    """Initializes a new ServerTemplate instance.

    Args:
        app: App instance to be used. This is optional and the default app instance will
            be used if not present.
        default_config: The default config to be used in the evaluated config.
        template_data: An optional template data to be set on initialization.

    Returns:
        ServerTemplate: A new ServerTemplate instance initialized with an optional
        template and config.
    """
    template = ServerTemplate(app=app, default_config=default_config)
    if template_data is not None:
        template.set(template_data)
    return template