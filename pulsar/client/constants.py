"""File names and patterns shared by the Pulsar client, server, and Galaxy.

Kept free of imports so Galaxy and Pulsar's server side can use these without
loading the client.
"""

COMMAND_VERSION_FILENAME = "COMMAND_VERSION"
DEFAULT_DYNAMIC_COLLECTION_PATTERN = [
    r"primary_.*|galaxy.json|metadata_.*|dataset_\d+\.dat|__instrument_.*|dataset_\d+_files.+|outputs_populated/.*|tool_stdout|tool_stderr"
]
EXTENDED_METADATA_DYNAMIC_COLLECTION_PATTERN = [
    r"outputs_populated/.*"
]
