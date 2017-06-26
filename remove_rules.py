"""
Script to be executed by a cron job
"""

"""
=== IMPORTS ===
"""
import datetime
from app import azure_remove_shell_command
import threading
import time

FILENAME = '/var/www/azure/src/names.txt'
MAXIMUM_TIME = 2  # Maximum hours an IP address should be valid for

"""
=== FUNCTIONS ===
"""


def get_data_from_file():
    """
    Reads file and returns the data it contains
    :return: List of rules
    """
    with open(FILENAME, 'r') as file:
        return [line.rstrip().split(',') for line in file]


def remove_data_from_file(line_indexes_to_delete):
    """
    Removes specified indices from file
    :param line_indexes_to_delete: set of indices
    :return:
    """
    file = open(FILENAME, "r+")

    # Get all lines and go to start
    lines = file.readlines()
    file.seek(0)

    for index, line in enumerate(lines):
        # Only write if we are not deleting and the line is not blank
        if index not in line_indexes_to_delete and line not in ['\n', '\r\n']:
            file.write(line)

    file.truncate()
    file.close()


def remove_expired():
    """
    Removes all expired nsg rules from text file and Azure
    :return: Void
    """
    data = get_data_from_file()
    line_indexes_to_delete = set()

    now = datetime.datetime.now()

    for index, entry in enumerate(data):

        if entry and entry[0] == '':
            continue

        # Time
        time_added = entry[0]

        time_difference = now - datetime.datetime.strptime(time_added, "%Y-%m-%d %H:%M:%S.%f")
        time_difference_in_hours = time_difference.seconds / 3600

        if time_difference_in_hours < MAXIMUM_TIME:
            continue  # Still valid

        # Add to set so we can delete later
        line_indexes_to_delete.add(index)

        name, nsg_name, resource_group = entry[1], entry[2], entry[3]

        # Run executions on separate threads so we can do them successively
        thread = threading.Thread(target=azure_remove_shell_command(name, nsg_name, resource_group))
        thread.start()

        # Azure doesn't allow concurrent deletes
        time.sleep(15)

    remove_data_from_file(line_indexes_to_delete)


"""
=== MAIN ===
"""

if __name__ == '__main__':
    remove_expired()
