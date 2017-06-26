#!/usr/bin/python
"""
=== IMPORTS ===
"""

# Packages
import subprocess
from flask import Flask, request, abort
from random import randint
import logging
import traceback
from time import strftime, time
import datetime
import threading
import requests

# Files
from config import configuration as conf

"""
=== APP SETUP ===
"""

app = Flask(__name__)

# Logger
logger = logging.getLogger(__name__)

# Constants
SLACK_TOKEN = conf['SLACK_TOKEN']
AWSCLI_LOCATION = conf['AWSCLI_LOCATION']
LOOM_NSG_NAME = conf['LOOM_NSG_NAME']
LOOM_RESOURCE_GROUP = conf['LOOM_RESOURCE_GROUP']

# Error handling and logging
@app.after_request
def after_request(response):
    timestamp = strftime('[%Y-%b-%d %H:%M]')
    logger.info('%s %s %s %s %s %s', timestamp, request.remote_addr, request.method, request.scheme, request.full_path,
                 response.status)
    return response


@app.errorhandler(Exception)
def exceptions(e):
    tb = traceback.format_exc()
    timestamp = strftime('[%Y-%b-%d %H:%M]')
    logger.error('%s %s %s %s %s 5xx INTERNAL SERVER ERROR\n%s', timestamp, request.remote_addr, request.method,
                 request.scheme, request.full_path, tb)
    return str(e)


"""
=== FUNCTIONS ===
"""


def write_rule_to_file(name, nsg_name, resource_group):
    # Current time
    now = "\n" + str(datetime.datetime.now())

    output = now + ",%s,%s,%s" % (name, nsg_name, resource_group)

    with open('names.txt', "a") as file:
        file.write(output)


def execute_shell_command(command, response_url = None):
    # Execute
    print 'excecuting %s' % command
    subprocess.Popen(command, shell=True)

    # Respond to client
    # headers = {'Content-type': 'application/json'}
    # body = {'text': 'all done :)'}
    # requests.post(url=response_url, json=body, headers=headers)


    # Log results
    # app.logger.info(command.stdout.read())


def azure_create_shell_command(name, nsg_name, priority, resource_group, source_address_prefix, description,
                               response_url):
    """ Return the string shell command to add a new rule to a network security group """
    command = AWSCLI_LOCATION + "network nsg rule create --resource-group %s --nsg-name %s --name %s --access Allow " \
                                "--direction Inbound --priority %s --source-address-prefix %s --description '%s' " \
                                "--destination-port-range '%s'" % (
                                    resource_group, nsg_name, name, priority, source_address_prefix, description, '*')

    # Save to file
    write_rule_to_file(name, nsg_name, resource_group)

    print "EXECEUTING SHELL COMMAND : %s" % command
    execute_shell_command(command, response_url)


def azure_remove_shell_command(name, nsg_name, resource_group):
    """
    Remove a rule from a specified nsg
    :param name: name of the rul
    :param nsg_name: network security group
    :param resource_group: Azure resource group
    :param local: debugging only
    :return: Void
    """
    command = AWSCLI_LOCATION + " network nsg rule delete --name %s --nsg-name %s --resource-group %s" % (
        name, nsg_name, resource_group)

    execute_shell_command(command)


def valid_slack_token(token):
    """
    Validates the token sent to ensure it came from slack
    """
    return token == SLACK_TOKEN


def validate_ip(ip):
    """
    Returns true if ip is a theoretically valid ip address
    """
    nums = ip.split('.')
    if len(nums) != 4:
        return False
    for num_string in nums:
        if not num_string.isdigit():
            return False
        num = int(num_string)
        if num < 0 or num > 255:
            return False
    return True


"""
=== ROUTES ===
"""


# Listen for requests
@app.route('/', methods=['POST'])
def parse_and_execute_slash_command():
    print 'POST request received'
    data = request.values

    # Slack token
    token = data['token']

    # Validate to ensure request came from slack
    if not valid_slack_token(token):
        abort(403)

    # Parse other data
    ip_address = data['text']
    response_url = data['response_url']

    # Validate ip address
    if not validate_ip(ip_address):
        abort(400)

    ip_address = '"' + ip_address + '"'

    # Randomize name and priority
    _id = str(randint(100, 4096))
    name = 'temporary-ip-address' + _id
    priority = _id

    # Execute on separate thread so we can send response to client without timing out
    thread = threading.Thread(
        azure_create_shell_command(name=name, nsg_name=LOOM_NSG_NAME, priority=priority,
                                   resource_group=LOOM_RESOURCE_GROUP,
                                   source_address_prefix=ip_address, description='Temporary IP address',
                                   response_url=response_url))
    thread.start()

    # Respond to client
    return 'Adding IP address :)'


@app.route('/', methods=['GET'])
def hello():
    print 'testing print function'
    logger.error("GET retrieved")
    return "Hello, world!"


"""
=== MAIN ===
"""

if __name__ == '__main__':
    # Start application - threading required
    app.run(host='0.0.0.0', threaded=True, debug=True)
