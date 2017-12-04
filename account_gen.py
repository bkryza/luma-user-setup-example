#!/usr/bin/env python3

import logging as LOG
import requests
from requests.auth import HTTPBasicAuth
from sys import exit


# This is an example script which configures a set of basic auth user accounts
# in Onezone based on a provided UID range [LOW_UID_RANGE, HIGH_UID_RANGE)
# and prefix USER_LOGIN_PREFIX.
#
# Each user is assigned to a data space, specified by SPACE_ID on a storage
# identfied by storage name property STORAGE_NAME.
#
# For each user a mapping is also created in LUMA service, based on consecutive
# itegers from the provided range.
#
# Before running this script modify the following global variables:
#   * ONEZONE_IP
#   * LUMA_IP
#   * PASSWORD
#   * SPACE_ID
#   * DEFAULT_SPACE_GID
#   * STORAGE_NAME
#   * LOW_UID_RANGE
#   * HIGH_UID_RANGE
#   * USER_LOGIN_PREFIX
#   * ONEZONE_PANEL_AUTH
#   * ONEZONE_ADMIN_AUTH


ONEZONE_IP='192.168.1.99'
LUMA_IP='192.168.1.200'

ONEZONE_PANEL='https://{}:9443/api/v3/onepanel'.format(ONEZONE_IP)
ONEZONE_PANEL_AUTH=HTTPBasicAuth('admin', 'password')

ONEZONE='https://{}:8443/api/v3/onezone'.format(ONEZONE_IP)
ONEZONE_ADMIN_AUTH=HTTPBasicAuth('admin', 'password')

LUMA='http://{}:8080/api/v3/luma'.format(LUMA_IP)

# This example assumes a common password for all users. This can be changed.
# The users will never have to login to any Onedata service themselves.
PASSWORD='RANDOM'

# Space Id to which the users should be added, assuming all users
# should share the same data space. The Space Id can be copied from the
# Oneprovider panel interfaces under tab Spaces.
SPACE_ID='Beiqfxp6wquV7rpgNSb4HFNJDnlbLxdjFsfwTX6rrxc'

# A default GID for a data space can be defined, without mapping GID to
# specific groups in Onedata.
DEFAULT_SPACE_GID=2000

# Name of the storage. Mappings in LUMA can be also made based on the storageId
# but name is typically more convenient, however it has to be unique within
# a single provider.
STORAGE_NAME='DESY'
STORAGE_TYPE='posix'
LOW_UID_RANGE=1001
HIGH_UID_RANGE=1004
USER_LOGIN_PREFIX='XX'


def checkResponse(res):
    """
    Generic REST reponse validator
    """
    if res.status_code not in [200, 201, 202, 204]:
        LOG.error(res.text)
        res.raise_for_status()


def generateUserLogins(low_range, high_range, prefix='user'):
    """
    Generates user login names and UID's
    """
    return [(i, prefix+str(i).zfill(5)) for i in range(low_range, high_range)]


def addUsersToOnezone(users):
    """
    Adds basic auth users to Onezone via Onezone Onepanel administrative
    interface. Requires administrator account in Onezone.
    """
    for user in users:
        LOG.info("Adding user: " + user[1])

        r = requests.post(ONEZONE_PANEL+"/users", json = {
            'username': user[1],
            'userRole': 'regular',
            'password': PASSWORD
        }, auth=ONEZONE_PANEL_AUTH, verify=False)

        checkResponse(r)


def getUserIdsAndTokens(user_logins):
    """
    Get user 'onedata' ids from Onezone and generate their access tokens.
    """
    result = []

    for user in user_logins:
        r = requests.get(ONEZONE+"/user",
                         auth=HTTPBasicAuth(user[1], PASSWORD),
                         verify=False)
        checkResponse(r)

        user_id = r.json()['userId']

        LOG.info("Generating user {} access token".format(user[1]))

        r = requests.post(ONEZONE+"/user/client_tokens", json={},
                          auth=HTTPBasicAuth(user[1], PASSWORD),
                          verify=False)
        checkResponse(r)

        user_token = r.json()['token']

        result.append((user[0], user[1], user_id, user_token))

    return result


def addUsersToSpace(space_id, users):
    """
    Adds all users to a specific space. This function requires zone
    administrator rights, however the same can be achieved by a regular user
    with few more steps, by issuing space invite tokens and accepting them by
    each user.
    """
    for user in users:
        endpoint = ONEZONE+"/spaces/{}/users/{}".format(space_id, user[2])

        LOG.info("Adding user {} to space".format(user[1]))

        r = requests.put(endpoint, json={}, auth=ONEZONE_ADMIN_AUTH,
                         verify=False)
        checkResponse(r)


def addUserMappingsToLUMA(storage_name, users, space_id, default_gid):
    """
    Adds user mappings to a LUMA instance.
    """
    # Set default gid for the space on the storage
    endpoint = LUMA+"/admin/spaces/{}/default_group".format(space_id)
    r = requests.put(endpoint, json=[{'gid': default_gid,
                                      'storageName': storage_name}],
                     verify=False)
    checkResponse(r)

    for user in users:
        LOG.info("Adding user {} credentials to LUMA".format(user[1]))
        endpoint = LUMA+"/admin/users"
        r = requests.post(endpoint, json={'id': user[2]})
        checkResponse(r)
        _, luma_id = r.headers['Location'].rsplit('/', 1)

        endpoint = LUMA+"/admin/users/{}/credentials".format(luma_id)
        r = requests.put(endpoint, json=[{'storageName': storage_name,
                                          'type': STORAGE_TYPE,
                                          'uid': user[0],
                                          'gid': user[0]}])
        checkResponse(r)


def writeUserAccounts(prefix, users):
    """
    Writes generated user accounts information into a comma-separated CSV
    file with the following structure:

      UID,LOGIN_NAME,ONEDATA_USER_ID,USER_ACCESS_TOKEN

    If the file with the same name (prefix_accounts.csv) alread exists,
    new users information will be appended.
    """
    filename = prefix+"_accounts.csv"
    with open(filename, "w+") as f:
        for user in users:
            f.write(','.join(map(str, user))+'\n')


def main():
    requests.packages.urllib3.disable_warnings()
    LOG.basicConfig(level=LOG.DEBUG)

    user_logins = generateUserLogins(LOW_UID_RANGE, HIGH_UID_RANGE,
                                     USER_LOGIN_PREFIX)
    addUsersToOnezone(user_logins)
    users = getUserIdsAndTokens(user_logins)
    addUsersToSpace(SPACE_ID, users)
    addUserMappingsToLUMA(STORAGE_NAME, users, SPACE_ID, DEFAULT_SPACE_GID)
    writeUserAccounts(USER_LOGIN_PREFIX, users)


if __name__ == "__main__":
    main()
