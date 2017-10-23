# Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not
# use this file except in compliance with the License. A copy of the License is
# located at
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

import os
import socket
import traceback

from AWSIoTPythonSDK.core.protocol.connection.cores import \
    ProgressiveBackOffCore
from AWSIoTPythonSDK.exception.AWSIoTExceptions import \
    DiscoveryInvalidRequestException, DiscoveryFailure
from AWSIoTPythonSDK.exception import operationTimeoutException


def mqtt_connect(mqtt_client, core_info):
    connected = False
    for connectivity_info in core_info.connectivityInfoList:
        core_host = connectivity_info.host
        core_port = connectivity_info.port
        print("Connecting to Core at {0}:{1}".format(core_host, core_port))
        mqtt_client.configureEndpoint(core_host, core_port)
        try:
            mqtt_client.connect()
            connected = True
            break
        except socket.error as se:
            print("SE:{0}".format(se))
        except operationTimeoutException as te:
            print("operationTimeoutException:{0}".format(te.message))
            traceback.print_tb(te, limit=25)
        except Exception as e:
            print("Exception caught:{0}".format(e.message))

    return connected


def ggc_discovery(thing_name, discovery_info_provider, group_ca_path,
                  retry_count=10):
    back_off_core = ProgressiveBackOffCore()
    discovered = False
    discovery_info = None
    group_list = None

    while retry_count != 0:
        try:
            discovery_info = discovery_info_provider.discover(thing_name)
            ca_list = discovery_info.getAllCas()
            core_list = discovery_info.getAllCores()
            group_list = discovery_info.getAllGroups()

            # TODO upgrade logic to support multiple discovered groups
            if len(group_list) > 0:
                raise DiscoveryFailure("Discovery of more groups than expected")

            # Only pick and save the first CA and Core info (currently)
            group_id, ca = ca_list[0]
            core_info = core_list[0]
            print("Discovered Greengrass Core: {0} from Group: {1}".format(
                core_info.coreThingArn, group_id)
            )

            group_ca_file = save_group_ca(ca, group_ca_path, group_id)
            discovered = True
            break
        except DiscoveryFailure as df:
            print("Discovery request failed!")
            print("Error:{0} type: {1}".format(df, str(type(df))))
            print("       message: {0}".format(df.message))
            back_off = True
        except DiscoveryInvalidRequestException as e:
            print("Invalid discovery request detected!")
            print("Error:{0}".format(e))
            print("Stopping...")
            break
        except BaseException as e:
            print("Error in discovery: {0} type: {1}".format(e, str(type(e))))
            print("           message: {0}".format(e.message))
            print("  thing_name: {0}".format(thing_name))
            print("  dip: {0}".format(discovery_info_provider))
            print("  group_ca_path: {0}".format(group_ca_path))
            back_off = True

        if back_off:
            retry_count -= 1
            print("  {0} retries left\n".format(retry_count))
            print("  Backing off...\n")
            back_off_core.backOff()

    return discovered, discovery_info, group_list


def save_group_ca(group_ca, group_ca_path, group_id):
    print("Persist the Core connectivity identity Group CA info...")
    group_ca_file = group_ca_path + '/' + group_id + "_CA.crt"
    if not os.path.exists(group_ca_path):
        os.makedirs(group_ca_path)
    with open(group_ca_file, "w") as crt:
        group_ca_file.write(crt)

    return group_ca_file


def dump_core_info_list(core_connectivity_info_list):

    for cil in core_connectivity_info_list:
        print("  Core {0} has connectivity list".format(cil.coreThingArn, ))
        for ci in cil.connectivityInfoList:
            print("    Connection info: {0} {1} {2} {3}".format(
                ci.id, ci.host, ci.port, ci.metadata))


def get_conn_info(core_connectivity_info_list, match):
    """
    Get core connectivity info objects from the list. Matching any the `match`
    argument.

    :param core_connectivity_info_list: the connectivity info object list
    :param match: the value to match against either the Core Connectivity Info
        `id`, `host`, `port`, or `metadata` values
    :return: the list of zero or more matching connectivity info objects
    """
    conn_info = list()

    if not match:
        return conn_info

    for cil in core_connectivity_info_list:
        for ci in cil.connectivityInfoList:
            if match == ci.id or match == ci.host or match == ci.port or \
                            match == ci.metadata:
                conn_info.append(ci)

    return conn_info