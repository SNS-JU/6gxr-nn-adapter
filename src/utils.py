def readFileContents(path):
    """
    Open a file and return its contents.

    Args:
        path (str): The path to the file.

    Returns:
        str: The contents of the file.
    """
    with open(path, "r") as file:
        return file.read()

def calculateBurst(rate):
    """
    Calculate the burst value based on a rate value.
    Formula reference: https://nettools.club/cisco_rlc

    Args:
        rate (int): The policing rate.

    Returns:
        int: The calculated policing burst value.
    """
    return round((rate / 8) * 1.5)
