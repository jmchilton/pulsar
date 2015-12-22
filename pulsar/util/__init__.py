""" Pulsar utilities.
"""


def enum(**enums):
    """
    http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python
    """
    return type('Enum', (), enums)
